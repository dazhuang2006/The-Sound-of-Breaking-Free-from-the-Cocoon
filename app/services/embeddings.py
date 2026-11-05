"""文本向量化。

三种实现，按环境切换：
- `hash`  ：字符 n-gram 特征哈希 + 符号哈希，零依赖、确定性，用于本地开发与 CI；
- `bge-m3`：本地加载 BAAI/bge-m3（稠密向量），生产推荐；
- `http`  ：调用 OpenAI 兼容的 /embeddings 接口（TEI、vLLM、DashScope 等均可）。

统一接口保证 RAG 层与具体模型解耦，切换模型只需改一个环境变量。
"""

from __future__ import annotations

import asyncio
import hashlib
import math
import re
from abc import ABC, abstractmethod
from collections import Counter
from functools import lru_cache

import httpx
import numpy as np

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_CJK = re.compile(r"[\u4e00-\u9fff]+")
_WORD = re.compile(r"[a-z0-9]+")


class Embedder(ABC):
    name: str = "base"
    dim: int = 512

    @abstractmethod
    async def embed_documents(self, texts: list[str]) -> np.ndarray: ...

    async def embed_query(self, text: str) -> np.ndarray:
        vectors = await self.embed_documents([text])
        return vectors[0]

    @staticmethod
    def _normalize(matrix: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return (matrix / norms).astype(np.float32)


class HashEmbedder(Embedder):
    """离线可用的特征哈希向量化。

    对中文按 单字 + 二元组、对英文按词切分，使用带符号的哈希把特征映射到固定维度，
    再做 L2 归一化。它不具备语义泛化能力，但能让检索链路、阈值、混合排序在无模型环境下
    完整跑通，并保持结果可复现（测试友好）。
    """

    name = "hash"

    def __init__(self, dim: int = 512) -> None:
        if dim < 64:
            raise ValueError("embedding_dim 至少为 64")
        self.dim = dim

    @staticmethod
    def _tokens(text: str) -> list[str]:
        text = text.lower()
        tokens: list[str] = []
        for word in _WORD.findall(text):
            tokens.append(word)
        for run in _CJK.findall(text):
            tokens.extend(run)  # 单字
            tokens.extend(run[i : i + 2] for i in range(len(run) - 1))  # 二元组
        return tokens

    def _embed_one(self, text: str) -> np.ndarray:
        vector = np.zeros(self.dim, dtype=np.float32)
        counter = Counter(self._tokens(text))
        for token, tf in counter.items():
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            raw = int.from_bytes(digest, "big")
            index = raw % self.dim
            sign = 1.0 if (raw >> 63) & 1 else -1.0
            vector[index] += sign * (1.0 + math.log(tf))
        return vector

    async def embed_documents(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        matrix = np.vstack([self._embed_one(text) for text in texts])
        return self._normalize(matrix)


class BgeM3Embedder(Embedder):
    """本地 BGE-M3（需要 `pip install -r requirements-rag.txt` 并下载模型）。"""

    name = "bge-m3"

    def __init__(self, model_path: str, batch_size: int = 8) -> None:
        self.dim = 1024
        self.batch_size = batch_size
        from FlagEmbedding import BGEM3FlagModel  # 延迟导入，避免无 GPU 环境启动失败

        logger.info("正在加载 BGE-M3: %s", model_path)
        self._model = BGEM3FlagModel(model_path, use_fp16=True)

    def _encode(self, texts: list[str]) -> np.ndarray:
        output = self._model.encode(
            texts, batch_size=self.batch_size, max_length=512, return_dense=True
        )
        return self._normalize(np.asarray(output["dense_vecs"], dtype=np.float32))

    async def embed_documents(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        return await asyncio.to_thread(self._encode, texts)


class HttpEmbedder(Embedder):
    """OpenAI 兼容嵌入接口。"""

    name = "http"

    def __init__(self, base_url: str, model: str, api_key: str = "", dim: int = 1024) -> None:
        if not base_url:
            raise ValueError("embedding_http_url 未配置")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.dim = dim
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            self._client = httpx.AsyncClient(base_url=self.base_url, headers=headers, timeout=60)
        return self._client

    async def embed_documents(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        response = await self.client.post("/embeddings", json={"model": self.model, "input": texts})
        response.raise_for_status()
        data = response.json()["data"]
        matrix = np.asarray([item["embedding"] for item in data], dtype=np.float32)
        if matrix.shape[0] != len(texts):
            raise RuntimeError("嵌入接口返回数量与输入不一致")
        self.dim = int(matrix.shape[1])
        return self._normalize(matrix)


def build_embedder(settings: Settings | None = None) -> Embedder:
    settings = settings or get_settings()
    provider = settings.embedding_provider
    if provider == "bge-m3":
        try:
            return BgeM3Embedder(settings.embedding_model_path, settings.embedding_batch_size)
        except Exception as exc:  # 模型缺失时降级，保证服务可启动
            logger.warning("BGE-M3 加载失败，降级为 hash 向量: %s", exc)
            return HashEmbedder(settings.embedding_dim)
    if provider == "http":
        try:
            return HttpEmbedder(
                settings.embedding_http_url,
                settings.embedding_http_model,
                settings.embedding_http_api_key,
                settings.embedding_dim,
            )
        except Exception as exc:
            logger.warning("远程嵌入不可用，降级为 hash 向量: %s", exc)
            return HashEmbedder(settings.embedding_dim)
    return HashEmbedder(settings.embedding_dim)


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    return build_embedder()
