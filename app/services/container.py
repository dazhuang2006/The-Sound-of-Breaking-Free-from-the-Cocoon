"""应用级服务容器：启动时构建一次，进程内复用。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.agents.graph import build_graph
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.db.base import get_session_factory
from app.db.models import KnowledgeDoc
from app.services.asr import ASRProvider, build_asr
from app.services.cache import CacheBackend, build_cache
from app.services.embeddings import Embedder, build_embedder
from app.services.followup import FollowupService
from app.services.knowledge import KnowledgeBase, load_markdown_documents, split_document
from app.services.llm import LLMClient, build_llm
from app.services.training import TrainingService
from app.services.training_judge import TrainingJudge
from app.services.training_world import TrainingWorldService
from app.services.tts import TTSProvider, build_tts
from app.services.vectorstore import VectorStore, build_vector_store

logger = get_logger(__name__)


@dataclass
class Services:
    settings: Settings
    llm: LLMClient
    embedder: Embedder
    store: VectorStore
    kb: KnowledgeBase
    cache: CacheBackend
    training: TrainingService
    followup: FollowupService
    asr: ASRProvider
    tts: TTSProvider
    training_judge: TrainingJudge
    training_world: TrainingWorldService
    graph: Any = None


async def build_services(settings: Settings | None = None) -> Services:
    settings = settings or get_settings()
    llm = build_llm(settings)
    embedder = build_embedder(settings)
    store = build_vector_store(settings, dim=embedder.dim)
    kb = KnowledgeBase(store, embedder, settings)
    cache = await build_cache(settings)
    services = Services(
        settings=settings,
        llm=llm,
        embedder=embedder,
        store=store,
        kb=kb,
        cache=cache,
        training=TrainingService(settings),
        followup=FollowupService(llm, settings),
        asr=build_asr(settings),
        tts=build_tts(settings),
        training_judge=TrainingJudge(llm, settings),
        training_world=TrainingWorldService(),
    )
    services.graph = build_graph()
    await _bootstrap_knowledge(services)
    logger.info(
        "服务就绪｜LLM=%s 嵌入=%s 向量库=%s 缓存=%s ASR=%s TTS=%s 知识块=%d",
        llm.provider,
        embedder.name,
        store.name,
        cache.name,
        services.asr.name,
        services.tts.name,
        await kb.count(),
    )
    return services


async def _bootstrap_knowledge(services: Services) -> None:
    """首次启动时自动把 knowledge/ 下的文档入库，并同步知识文档索引。"""
    settings = services.settings
    documents = load_markdown_documents(settings.kb_dir)
    if not documents:
        return
    if await services.kb.count() == 0:
        report = await services.kb.ingest_documents(documents)
        logger.info("知识库首次入库: %s", report.to_dict())
    await sync_knowledge_docs(services, documents)


async def sync_knowledge_docs(services: Services, documents: list[Any]) -> None:
    settings = services.settings
    factory = get_session_factory()
    async with factory() as db:
        for document in documents:
            chunk_count = len(
                split_document(document, settings.rag_chunk_size, settings.rag_chunk_overlap)
            )
            row = await db.get(KnowledgeDoc, document.doc_id)
            if row is None:
                db.add(
                    KnowledgeDoc(
                        id=document.doc_id,
                        title=document.title,
                        source=document.source,
                        chunk_count=chunk_count,
                        checksum=document.checksum,
                    )
                )
            else:
                row.title = document.title
                row.source = document.source
                row.chunk_count = chunk_count
                row.checksum = document.checksum
        await db.commit()


async def close_services(services: Services | None) -> None:
    if services is None:
        return
    for closer in (services.llm.aclose, services.cache.aclose, services.store.aclose):
        try:
            await closer()
        except Exception as exc:  # pragma: no cover - 关闭阶段的异常不应影响退出
            logger.debug("资源关闭失败: %s", exc)
