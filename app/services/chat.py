"""对话编排：会话生命周期、上下文装载、图执行、落库与缓存。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import ChatMessage, ChatSession, Child, SafetyEvent, User
from app.schemas.chat import ChatMeta, ChatResponse, Citation, SafetyPayload
from app.schemas.training import TrainingTurn
from app.services.cache import session_cache_key
from app.services.followup import age_desc

logger = get_logger(__name__)

DEFAULT_TITLE = "新的对话"


class ChatService:
    async def handle(
        self,
        db: AsyncSession,
        user: User,
        services: Any,
        *,
        message: str,
        session_id: str | None = None,
        child_id: int | None = None,
    ) -> ChatResponse:
        session = await self._resolve_session(db, user, session_id, child_id)
        history = await self._load_history(db, session.id, services.settings.history_window)
        child = await self._resolve_child(db, user, session, child_id)

        profile: dict[str, Any] = {}
        followup_context = ""
        if child is not None:
            profile = {
                "nickname": child.nickname,
                "age_desc": age_desc(child.birth_date),
                "profile_note": child.profile_note or "（无）",
            }
            followup_context = await services.followup.recent_context(db, child.id)

        db.add(ChatMessage(session_id=session.id, role="user", content=message[:4000]))
        await db.flush()

        state = {
            "session_id": session.id,
            "user_id": user.id,
            "child_id": child.id if child else None,
            "user_message": message,
            "history": history,
            "child_profile": profile,
            "followup_context": followup_context,
            "mode": session.mode,
        }
        config = {
            "configurable": {
                "services": services,
                "db": db,
                "user": user,
            },
            "recursion_limit": 15,
        }
        try:
            result = await services.graph.ainvoke(state, config=config)
        except Exception:  # 图执行异常不能吞掉，但需要留下可排查日志
            logger.exception("LangGraph 执行失败 session=%s", session.id)
            raise

        answer = (result.get("answer") or "").strip() or "抱歉，我这边没有生成有效回复，请再试一次。"
        safety = result.get("safety") or {}
        citations = result.get("citations") or []
        intent = result.get("intent") or "qa"
        mode = result.get("mode") or "qa"

        db.add(
            ChatMessage(
                session_id=session.id,
                role="assistant",
                content=answer,
                intent=intent,
                safety_level=safety.get("level", "normal"),
                citations=citations,
            )
        )
        session.mode = "training" if mode == "training" else "qa"
        session.updated_at = datetime.now(UTC)
        if session.title == DEFAULT_TITLE:
            session.title = message.strip().replace("\n", " ")[:24] or DEFAULT_TITLE
        await db.flush()

        await self._log_safety_event(db, user, session, message, safety)
        # 显式提交：保证客户端拿到 session_id 后立刻发起的下一轮请求能读到数据，
        # 不依赖依赖注入 teardown 的提交时机（快速连发时会出现竞态）。
        await db.commit()
        await self._cache_recent(services, session.id, history, message, answer)

        meta = ChatMeta(
            **{
                "llm_provider": "rules",
                "llm_model": "rule-engine",
                "mocked": False,
                "latency_ms": 0,
                "retrieved": len(citations),
                **(result.get("meta") or {}),
            }
        )
        training = result.get("training")
        return ChatResponse(
            session_id=session.id,
            reply=answer,
            intent=intent,
            mode="training" if mode == "training" else "qa",
            safety=SafetyPayload(**safety) if safety else SafetyPayload(),
            citations=[Citation(**item) for item in citations],
            training=TrainingTurn(**training) if training else None,
            meta=meta,
        )

    # ------------------------------------------------------------ 内部
    async def _resolve_session(
        self, db: AsyncSession, user: User, session_id: str | None, child_id: int | None
    ) -> ChatSession:
        if session_id:
            session = await db.get(ChatSession, session_id)
            if session is None or session.user_id != user.id:
                raise LookupError("会话不存在")
            if child_id and session.child_id != child_id:
                session.child_id = child_id
            return session
        session = ChatSession(user_id=user.id, child_id=child_id, title=DEFAULT_TITLE, mode="qa")
        db.add(session)
        await db.flush()
        return session

    async def _resolve_child(
        self, db: AsyncSession, user: User, session: ChatSession, child_id: int | None
    ) -> Child | None:
        target = child_id or session.child_id
        if not target:
            return None
        child = await db.get(Child, target)
        if child is None or child.user_id != user.id:
            raise PermissionError("无权访问该孩子档案")
        if session.child_id != child.id:
            session.child_id = child.id
        return child

    async def _load_history(
        self, db: AsyncSession, session_id: str, limit: int
    ) -> list[dict[str, str]]:
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id, ChatMessage.role.in_(("user", "assistant")))
            .order_by(ChatMessage.id.desc())
            .limit(limit)
        )
        rows = list((await db.execute(stmt)).scalars())
        rows.reverse()
        return [{"role": row.role, "content": row.content[:2000]} for row in rows]

    async def _log_safety_event(
        self,
        db: AsyncSession,
        user: User,
        session: ChatSession,
        message: str,
        safety: dict[str, Any],
    ) -> None:
        """记录安全事件，供事后审计与知识库修订。"""
        level = safety.get("level", "normal")
        if level == "normal":
            return
        categories = safety.get("categories") or ["unspecified"]
        matched = safety.get("matched") or []
        db.add(
            SafetyEvent(
                user_id=user.id,
                session_id=session.id,
                level=level,
                category=",".join(str(item) for item in categories)[:32],
                excerpt=message.strip()[:255],
                matched=",".join(str(item) for item in matched)[:255],
            )
        )

    async def _cache_recent(
        self,
        services: Any,
        session_id: str,
        history: list[dict[str, str]],
        user_message: str,
        answer: str,
    ) -> None:
        try:
            recent = [*history, {"role": "user", "content": user_message[:2000]},
                      {"role": "assistant", "content": answer[:2000]}][-10:]
            await services.cache.set_json(session_cache_key(session_id), recent, ttl=1800)
        except Exception as exc:  # 缓存失败不影响主流程
            logger.warning("会话缓存写入失败: %s", exc)


chat_service = ChatService()
