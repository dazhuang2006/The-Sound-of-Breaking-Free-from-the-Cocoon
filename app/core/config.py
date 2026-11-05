"""全局配置。

所有配置均可通过环境变量或 `.env` 覆盖，命名与字段名一致（大小写不敏感）。
默认值刻意选择"零外部依赖即可启动"：SQLite + 内存向量库 + Mock LLM，
方便本地开发、CI 与答辩演示；生产环境通过环境变量切换到 MySQL / Milvus / DeepSeek。
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---------- 应用 ----------
    app_name: str = "破茧之声"
    app_version: str = "0.1.0"
    env: Literal["dev", "test", "prod"] = "dev"
    debug: bool = False
    api_prefix: str = "/api/v1"
    secret_key: str = Field(default="dev-only-secret-please-change-32bytes", min_length=16)
    access_token_expire_minutes: int = 60 * 24
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ---------- 数据库 ----------
    database_url: str = "sqlite+aiosqlite:///./data/app.db"
    db_echo: bool = False
    auto_create_tables: bool = True

    # ---------- 缓存 ----------
    redis_url: str = "redis://127.0.0.1:6379/0"
    cache_enabled: bool = True
    cache_ttl_seconds: int = 1800

    # ---------- LLM ----------
    llm_provider: Literal["mock", "deepseek"] = "mock"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    llm_temperature: float = 0.5
    llm_timeout_seconds: float = 60.0
    llm_max_tokens: int = 900

    # ---------- 向量化 ----------
    embedding_provider: Literal["hash", "bge-m3", "http"] = "hash"
    embedding_dim: int = 512
    embedding_model_path: str = "BAAI/bge-m3"
    embedding_batch_size: int = 8
    embedding_http_url: str = ""
    embedding_http_api_key: str = ""
    embedding_http_model: str = "bge-m3"

    # ---------- 向量库 ----------
    vector_backend: Literal["memory", "milvus"] = "memory"
    milvus_uri: str = "http://127.0.0.1:19530"
    milvus_token: str = ""
    milvus_collection: str = "pojian_kb"

    # ---------- RAG ----------
    kb_dir: str = "knowledge"
    kb_index_path: str = "data/kb/index.json"
    rag_top_k: int = 4
    rag_min_score: float = 0.3
    rag_chunk_size: int = 320
    rag_chunk_overlap: int = 60
    rag_lexical_weight: float = 0.25
    rag_use_history_query: bool = True

    # ---------- 业务 ----------
    history_window: int = 10
    followup_window_days: int = 7
    training_max_hint_level: int = 2
    safety_llm_check: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
