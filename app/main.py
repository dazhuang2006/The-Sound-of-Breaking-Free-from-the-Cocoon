"""应用入口。

启动顺序：日志 → 数据表 → 服务容器（LLM/嵌入/向量库/缓存）→ 知识库自助入库。
所有外部依赖都有降级路径，保证 `uvicorn app.main:app` 在裸机上可以直接跑起来。
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.base import dispose_engine, get_session_factory, init_db
from app.services.container import build_services, close_services

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.debug)
    logger.info("正在启动 %s v%s（env=%s）", settings.app_name, settings.app_version, settings.env)
    await init_db()
    services = await build_services(settings)
    app.state.services = services
    try:
        yield
    finally:
        await close_services(services)
        await dispose_engine()
        logger.info("服务已停止")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.debug)
    app = FastAPI(
        title=f"{settings.app_name} API",
        version=settings.app_version,
        description=(
            "自闭症儿童居家康复与医疗随访 AI 智能助手："
            "RAG 知识检索 + LangGraph 工作流 + 情景训练 + 随访管理。"
            "所有输出仅供居家辅助参考，不构成医疗诊断与治疗方案。"
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/health", tags=["运维"], summary="健康检查")
    async def health() -> dict[str, Any]:
        components: dict[str, Any] = {}
        status = "ok"
        services = getattr(app.state, "services", None)
        if services is None:
            return {"status": "starting", "app": settings.app_name, "components": components}
        components.update(
            {
                "llm": services.llm.provider,
                "embedder": services.embedder.name,
                "vector_store": services.store.name,
                "cache": services.cache.name,
            }
        )
        try:
            components["knowledge_chunks"] = await services.kb.count()
        except Exception as exc:  # pragma: no cover
            components["knowledge_chunks"] = f"error: {exc}"
            status = "degraded"
        try:
            async with get_session_factory()() as db:
                await db.execute(text("SELECT 1"))
            components["database"] = "ok"
        except Exception as exc:  # pragma: no cover
            components["database"] = f"error: {exc}"
            status = "degraded"
        return {
            "status": status,
            "app": settings.app_name,
            "version": settings.app_version,
            "components": components,
        }

    @app.get("/api", include_in_schema=False)
    async def api_info() -> dict[str, str]:
        return {
            "name": settings.app_name,
            "docs": "/docs",
            "health": "/health",
            "api": settings.api_prefix,
        }

    # 前端构建产物存在时直接托管（Docker 单容器部署 / 本地演示）
    web_dist = Path("web/dist")
    if web_dist.exists():
        app.mount("/", StaticFiles(directory=str(web_dist), html=True), name="web")
    else:

        @app.get("/", include_in_schema=False)
        async def root() -> dict[str, str]:
            return {
                "name": settings.app_name,
                "docs": "/docs",
                "health": "/health",
                "api": settings.api_prefix,
                "hint": "前端未构建：cd web && pnpm install && pnpm build",
            }

    return app


app = create_app()
