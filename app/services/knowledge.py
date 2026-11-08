"""知识库构建与混合检索。

流程：Markdown 解析 → 按标题分节 → 定长滑窗切块 → 向量化 → 入库。
检索：向量召回 + 字符 n-gram 词法打分加权融合，再按阈值过滤，输出可引用的片段。

之所以保留词法分数：医疗康复语料里大量专有名词（如"感觉统合""辅助沟通"），
纯向量在低资源 embedding 下容易漏召回，混合检索更稳。
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter, OrderedDict
from dataclasses import dataclass, field
from datetime import UTC
from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.embeddings import Embedder
from app.services.vectorstore import KnowledgeChunk, SearchHit, VectorStore

logger = get_logger(__name__)

# 查询向量缓存：演示时同一句话会被反复问，省掉每次都调 embedding 接口
_QUERY_VECTOR_CACHE: OrderedDict[tuple[str, str], Any] = OrderedDict()
_QUERY_VECTOR_CACHE_MAX = 256

_HEADING = re.compile(r"^(#{1,3})\s+(.*)$")
_SENTENCE = re.compile(r"(?<=[。！？!?；;])|\n+")
_CJK_RUN = re.compile(r"[\u4e00-\u9fff]+")
_LATIN = re.compile(r"[a-z0-9]+")

# 家长口语与知识库书面语之间的差距，用领域同义词表补一部分（生产环境应由
# 语义模型 + 人工维护的术语表共同解决，这里保证离线模式也能召回关键内容）。
_SYNONYMS: dict[str, tuple[str, ...]] = {
    "睡觉": ("睡眠", "入睡", "睡前"),
    "睡眠": ("睡觉", "入睡"),
    "不肯": ("拒绝", "不愿"),
    "不肯睡": ("入睡困难", "睡前"),
    "怕吵": ("听觉敏感", "声音"),
    "捂耳朵": ("听觉敏感", "声音"),
    "理发": ("剪头发", "头发"),
    "剪头发": ("理发", "头发"),
    "挑食": ("偏食", "只吃"),
    "打自己": ("自伤",),
    "打头": ("自伤", "撞墙"),
    "道谢": ("谢谢", "感谢"),
    "说谢谢": ("道谢", "感谢"),
    "和小朋友玩": ("同伴", "社交"),
    "不会说话": ("语言", "口语"),
    "躺地上": ("情绪", "崩溃"),
    "发脾气": ("情绪", "崩溃"),
}


def _grams(value: str) -> set[str]:
    value = value.lower()
    tokens: set[str] = set()
    for run in _CJK_RUN.findall(value):
        tokens.update(run[i : i + 2] for i in range(len(run) - 1))
    tokens.update(_LATIN.findall(value))
    return tokens


def expand_query(query: str) -> str:
    extra: list[str] = []
    for phrase, synonyms in _SYNONYMS.items():
        if phrase in query:
            extra.extend(synonyms)
    return f"{query} {' '.join(extra)}" if extra else query


@dataclass
class Document:
    doc_id: str
    title: str
    source: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    path: str = ""
    checksum: str = ""


@dataclass
class IngestReport:
    documents: int = 0
    chunks: int = 0
    skipped: int = 0
    embedder: str = ""
    backend: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "documents": self.documents,
            "chunks": self.chunks,
            "skipped": self.skipped,
            "embedder": self.embedder,
            "backend": self.backend,
        }


def _parse_front_matter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    meta: dict[str, Any] = {}
    for line in parts[1].strip().splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if not key:
            continue
        meta[key] = [item.strip() for item in value.split(",")] if "," in value else value
    return meta, parts[2].lstrip("\n")


def load_markdown_documents(directory: str | Path) -> list[Document]:
    root = Path(directory)
    if not root.exists():
        logger.warning("知识库目录不存在: %s", root)
        return []
    documents: list[Document] = []
    for path in sorted(root.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        meta, body = _parse_front_matter(text)
        title = str(meta.get("title") or "").strip()
        lines = body.splitlines()
        if not title:
            for line in lines:
                match = _HEADING.match(line)
                if match and len(match.group(1)) == 1:
                    title = match.group(2).strip()
                    break
        title = title or path.stem
        source = str(meta.get("source") or "").strip()
        checksum = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
        documents.append(
            Document(
                doc_id=hashlib.sha1(f"{path.name}:{title}".encode()).hexdigest()[:12],
                title=title,
                source=source,
                content=body,
                metadata={k: v for k, v in meta.items() if k not in ("title", "source")},
                path=str(path),
                checksum=checksum,
            )
        )
    logger.info("已读取知识文档 %d 篇: %s", len(documents), root)
    return documents


def _split_sentences(text: str) -> list[str]:
    return [piece.strip() for piece in _SENTENCE.split(text) if piece and piece.strip()]


def _window(text: str, size: int, overlap: int) -> list[str]:
    """按句子边界做滑窗，避免把一句话切断。"""
    sentences = _split_sentences(text)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        while len(sentence) > size:  # 超长句硬切
            head, sentence = sentence[:size], sentence[size:]
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.append(head)
        if len(current) + len(sentence) <= size:
            current += sentence
        else:
            if current:
                chunks.append(current.strip())
            tail = current[-overlap:] if overlap and current else ""
            current = tail + sentence
    if current.strip():
        chunks.append(current.strip())
    return [chunk for chunk in chunks if chunk]


def split_document(document: Document, chunk_size: int = 420, overlap: int = 60) -> list[KnowledgeChunk]:
    """按二级/三级标题分节，再在节内滑窗切块。"""
    sections: list[tuple[str, list[str]]] = [("", [])]
    for line in document.content.splitlines():
        heading = _HEADING.match(line)
        if heading and len(heading.group(1)) >= 2:
            sections.append((heading.group(2).strip(), []))
        else:
            sections[-1][1].append(line)

    chunks: list[KnowledgeChunk] = []
    index = 0
    for section_title, lines in sections:
        body = "\n".join(lines).strip()
        if not body and section_title:
            continue
        for piece in _window(body, chunk_size, overlap):
            chunks.append(
                KnowledgeChunk(
                    id=f"{document.doc_id}-{index:03d}",
                    doc_id=document.doc_id,
                    title=document.title,
                    source=document.source,
                    section=section_title,
                    content=piece,
                    metadata={
                        **(document.metadata or {}),
                        "path": document.path,
                        "checksum": document.checksum,
                        "ingested_at": _now_iso(),
                    },
                )
            )
            index += 1
    return chunks


def _now_iso() -> str:
    from datetime import datetime

    return datetime.now(UTC).isoformat(timespec="seconds")


def lexical_score(query: str, text: str) -> float:
    """查询词在文本中的覆盖率（未加权），保留作为工具函数与兼容入口。"""
    left, right = _grams(query), _grams(text)
    if not left:
        return 0.0
    return len(left & right) / len(left)


def _idf_weighted_coverage(query: str, candidates: list[SearchHit]) -> list[float]:
    """在候选集内计算 IDF 加权的查询覆盖率。

    IDF 只用当前候选集统计：不依赖全局语料状态，Memory/Milvus 两种实现都能用。
    IDF 上限 2.2，避免只在个别片段出现的罕见词把分数拉满。
    """
    query_grams = _grams(expand_query(query))
    if not query_grams or not candidates:
        return [0.0] * len(candidates)

    candidate_grams = [
        _grams(f"{hit.chunk.title} {hit.chunk.section} {hit.chunk.content}") for hit in candidates
    ]
    total = len(candidates)
    df: Counter[str] = Counter()
    for item in candidate_grams:
        df.update(item)
    idf = {
        gram: min(math.log((total + 1) / (df.get(gram, 0) + 1)) + 1.0, 2.2)
        for gram in query_grams
    }
    denominator = sum(idf.values()) or 1.0
    return [
        sum(weight for gram, weight in idf.items() if gram in item) / denominator
        for item in candidate_grams
    ]


class KnowledgeBase:
    def __init__(
        self,
        store: VectorStore,
        embedder: Embedder,
        settings: Settings | None = None,
    ) -> None:
        self.store = store
        self.embedder = embedder
        self.settings = settings or get_settings()

    async def ingest_documents(self, documents: list[Document], replace: bool = False) -> IngestReport:
        report = IngestReport(embedder=self.embedder.name, backend=self.store.name)
        if replace:
            await self.store.clear()
        for document in documents:
            chunks = split_document(
                document, self.settings.rag_chunk_size, self.settings.rag_chunk_overlap
            )
            if not chunks:
                report.skipped += 1
                continue
            texts = [f"{chunk.title} {chunk.section} {chunk.content}" for chunk in chunks]
            vectors = await self.embedder.embed_documents(texts)
            await self.store.upsert(chunks, vectors)
            report.documents += 1
            report.chunks += len(chunks)
        logger.info("知识库入库完成: %s", report.to_dict())
        return report

    async def ingest_directory(self, directory: str | Path, replace: bool = False) -> IngestReport:
        return await self.ingest_documents(load_markdown_documents(directory), replace=replace)

    async def _query_vector(self, query: str) -> Any:
        """查询向量带缓存；调用方负责处理异常降级。"""
        key = (self.embedder.name, query)
        cached = _QUERY_VECTOR_CACHE.get(key)
        if cached is not None:
            _QUERY_VECTOR_CACHE.move_to_end(key)
            return cached
        vector = await self.embedder.embed_query(query)
        _QUERY_VECTOR_CACHE[key] = vector
        while len(_QUERY_VECTOR_CACHE) > _QUERY_VECTOR_CACHE_MAX:
            _QUERY_VECTOR_CACHE.popitem(last=False)
        return vector

    async def search(
        self,
        query: str,
        top_k: int | None = None,
        min_score: float | None = None,
    ) -> list[SearchHit]:
        query = query.strip()
        if not query:
            return []
        top_k = top_k or self.settings.rag_top_k
        min_score = self.settings.rag_min_score if min_score is None else min_score
        try:
            vector = await self._query_vector(query)
        except Exception as exc:
            # 云端 embedding 抖动时宁可「本次无知识库依据」，也不要把问答整个打断
            logger.warning("查询向量化失败，本次按无检索结果处理: %s", exc)
            return []
        # 多召回一些，融合后再截断
        hits = await self.store.search(vector, top_k=max(top_k * 3, 10))
        if not hits:
            return []

        lexical_scores = _idf_weighted_coverage(query, hits)
        # hash 向量只有字面区分度，融合时以词法为主；语义模型则以向量为主。
        lexical_weight = (
            max(self.settings.rag_lexical_weight, 0.8)
            if self.embedder.name == "hash"
            else self.settings.rag_lexical_weight
        )
        semantic = self.embedder.name != "hash"
        top_vector = max(hit.vector_score for hit in hits) or 1.0
        for hit, lexical in zip(hits, lexical_scores, strict=True):
            hit.lexical_score = lexical
            vector_part = hit.vector_score if semantic else hit.vector_score / top_vector
            hit.score = (1 - lexical_weight) * vector_part + lexical_weight * lexical

        hits.sort(key=lambda item: item.score, reverse=True)
        # 不做"兜底返回最佳一条"：医疗场景下给不相关引用比明确说"没检索到"更危险。
        return [hit for hit in hits if hit.score >= min_score][:top_k]

    async def count(self) -> int:
        return await self.store.count()


def format_context(hits: list[SearchHit]) -> str:
    if not hits:
        return "（本次未检索到相关知识库内容）"
    blocks = []
    for index, hit in enumerate(hits, start=1):
        label = f"[{index}] 《{hit.chunk.title}》"
        if hit.chunk.section:
            label += f" · {hit.chunk.section}"
        if hit.chunk.source:
            label += f"（来源：{hit.chunk.source}）"
        blocks.append(f"{label}\n{hit.chunk.content}")
    return "\n\n".join(blocks)


def build_citations(hits: list[SearchHit]) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, hit in enumerate(hits, start=1):
        key = f"{hit.chunk.doc_id}:{hit.chunk.section}"
        if key in seen:
            continue
        seen.add(key)
        citations.append(
            {
                "index": index,
                "doc_id": hit.chunk.doc_id,
                "title": hit.chunk.title,
                "section": hit.chunk.section,
                "source": hit.chunk.source,
                "snippet": hit.chunk.content[:160],
                "score": round(hit.score, 4),
            }
        )
    return citations
