"""向量库抽象：内存实现（开发/测试）与 Milvus 实现（生产）。

统一采用 COSINE 相似度；内存实现把向量持久化为 JSON，重启后无需重新嵌入。
"""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class KnowledgeChunk:
    id: str
    doc_id: str
    title: str
    source: str
    section: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SearchHit:
    chunk: KnowledgeChunk
    vector_score: float
    lexical_score: float = 0.0
    score: float = 0.0


class VectorStore(ABC):
    name: str = "base"

    @abstractmethod
    async def upsert(self, chunks: list[KnowledgeChunk], vectors: np.ndarray) -> int: ...

    @abstractmethod
    async def search(self, vector: np.ndarray, top_k: int = 5) -> list[SearchHit]: ...

    @abstractmethod
    async def count(self) -> int: ...

    @abstractmethod
    async def clear(self) -> None: ...

    async def aclose(self) -> None:  # pragma: no cover - 可选资源释放
        return None


class MemoryVectorStore(VectorStore):
    name = "memory"

    def __init__(self, index_path: str | Path | None = None) -> None:
        self.index_path = Path(index_path) if index_path else None
        self._chunks: list[KnowledgeChunk] = []
        self._matrix: np.ndarray | None = None
        self._lock = asyncio.Lock()
        self._load()

    # ------------------------------------------------------------ 持久化
    def _load(self) -> None:
        if not self.index_path or not self.index_path.exists():
            return
        try:
            payload = json.loads(self.index_path.read_text(encoding="utf-8"))
            self._chunks = [KnowledgeChunk(**item["chunk"]) for item in payload["items"]]
            self._matrix = np.asarray([item["vector"] for item in payload["items"]], dtype=np.float32)
            logger.info("已加载向量索引: %s（%d 条）", self.index_path, len(self._chunks))
        except Exception as exc:  # 索引损坏不应阻塞启动
            logger.warning("向量索引加载失败，将以空索引启动: %s", exc)
            self._chunks, self._matrix = [], None

    def _persist(self) -> None:
        if not self.index_path:
            return
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        items = []
        if self._matrix is not None:
            for chunk, vector in zip(self._chunks, self._matrix, strict=True):
                items.append(
                    {"chunk": chunk.to_dict(), "vector": [round(float(x), 6) for x in vector]}
                )
        tmp = self.index_path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"items": items}, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.index_path)

    # ------------------------------------------------------------ 接口
    async def upsert(self, chunks: list[KnowledgeChunk], vectors: np.ndarray) -> int:
        if len(chunks) != len(vectors):
            raise ValueError("chunks 与 vectors 数量不一致")
        async with self._lock:
            existing = {chunk.id: i for i, chunk in enumerate(self._chunks)}
            for chunk, vector in zip(chunks, vectors, strict=True):
                if chunk.id in existing:
                    idx = existing[chunk.id]
                    self._chunks[idx] = chunk
                    assert self._matrix is not None
                    self._matrix[idx] = vector
                else:
                    existing[chunk.id] = len(self._chunks)
                    self._chunks.append(chunk)
                    self._matrix = (
                        vector.reshape(1, -1)
                        if self._matrix is None
                        else np.vstack([self._matrix, vector.reshape(1, -1)])
                    )
            self._persist()
        return len(chunks)

    async def search(self, vector: np.ndarray, top_k: int = 5) -> list[SearchHit]:
        if self._matrix is None or not self._chunks:
            return []
        scores = self._matrix @ vector.astype(np.float32)
        order = np.argsort(-scores)[: max(top_k, 0)]
        return [
            SearchHit(chunk=self._chunks[i], vector_score=float(scores[i]), score=float(scores[i]))
            for i in order
        ]

    async def count(self) -> int:
        return len(self._chunks)

    async def clear(self) -> None:
        async with self._lock:
            self._chunks, self._matrix = [], None
            self._persist()


class MilvusVectorStore(VectorStore):
    """基于 pymilvus MilvusClient 的向量库实现。"""

    name = "milvus"

    def __init__(self, uri: str, collection: str, dim: int, token: str = "") -> None:
        from pymilvus import DataType, MilvusClient

        self.collection = collection
        self.dim = dim
        self.client = MilvusClient(uri=uri, token=token or None)
        if not self.client.has_collection(collection):
            schema = self.client.create_schema(auto_id=False, enable_dynamic_field=True)
            schema.add_field("id", DataType.VARCHAR, is_primary=True, max_length=64)
            schema.add_field("vector", DataType.FLOAT_VECTOR, dim=dim)
            schema.add_field("doc_id", DataType.VARCHAR, max_length=64)
            schema.add_field("title", DataType.VARCHAR, max_length=200)
            schema.add_field("source", DataType.VARCHAR, max_length=400)
            schema.add_field("section", DataType.VARCHAR, max_length=200)
            schema.add_field("content", DataType.VARCHAR, max_length=4000)
            index_params = self.client.prepare_index_params()
            index_params.add_index(
                field_name="vector", index_type="AUTOINDEX", metric_type="COSINE"
            )
            self.client.create_collection(collection, schema=schema, index_params=index_params)
            logger.info("已创建 Milvus collection: %s", collection)
        self.client.load_collection(collection)

    async def upsert(self, chunks: list[KnowledgeChunk], vectors: np.ndarray) -> int:
        rows = [
            {
                "id": chunk.id,
                "vector": vector.tolist(),
                "doc_id": chunk.doc_id,
                "title": chunk.title[:200],
                "source": chunk.source[:400],
                "section": chunk.section[:200],
                "content": chunk.content[:4000],
                "metadata": json.dumps(chunk.metadata, ensure_ascii=False),
            }
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        if not rows:
            return 0
        await asyncio.to_thread(self.client.upsert, self.collection, rows)
        return len(rows)

    async def search(self, vector: np.ndarray, top_k: int = 5) -> list[SearchHit]:
        results = await asyncio.to_thread(
            self.client.search,
            self.collection,
            data=[vector.tolist()],
            limit=top_k,
            output_fields=["doc_id", "title", "source", "section", "content", "metadata"],
            search_params={"metric_type": "COSINE"},
        )
        hits: list[SearchHit] = []
        for row in results[0] if results else []:
            entity = row.get("entity", {})
            metadata: dict[str, Any] = {}
            if entity.get("metadata"):
                try:
                    metadata = json.loads(entity["metadata"])
                except json.JSONDecodeError:
                    metadata = {}
            chunk = KnowledgeChunk(
                id=str(row.get("id")),
                doc_id=entity.get("doc_id", ""),
                title=entity.get("title", ""),
                source=entity.get("source", ""),
                section=entity.get("section", ""),
                content=entity.get("content", ""),
                metadata=metadata,
            )
            score = float(row.get("distance", 0.0))
            hits.append(SearchHit(chunk=chunk, vector_score=score, score=score))
        return hits

    async def count(self) -> int:
        stats = await asyncio.to_thread(self.client.get_collection_stats, self.collection)
        return int(stats.get("row_count", 0))

    async def clear(self) -> None:
        await asyncio.to_thread(self.client.delete, self.collection, filter='id != ""')


def build_vector_store(settings: Settings | None = None, dim: int | None = None) -> VectorStore:
    settings = settings or get_settings()
    dimension = dim or settings.embedding_dim
    if settings.vector_backend == "milvus":
        # 优先用 milvus-lite 的本地单文件（不需要 etcd/minio/Docker）。
        # 注意不能复用 MILVUS_URI：pymilvus 自己也会读这个环境变量做默认连接，
        # 传本地路径会让它在 import 阶段就按远程 URI 解析而报错。
        uri = settings.milvus_lite_path or settings.milvus_uri
        if not uri.startswith(("http://", "https://")):
            # milvus-lite 需要绝对路径；顺带把相对路径按项目根解析
            from pathlib import Path as _Path

            uri = str(_Path(uri).expanduser().resolve())
        try:
            return MilvusVectorStore(uri, settings.milvus_collection, dimension, settings.milvus_token)
        except Exception as exc:  # Milvus 未就绪时降级，避免整个服务不可用
            logger.warning("Milvus 连接失败，降级为内存向量库: %s", exc)
    return MemoryVectorStore(settings.kb_index_path)
