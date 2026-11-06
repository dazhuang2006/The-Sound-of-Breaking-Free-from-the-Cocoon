"""全局配置。

所有配置均可通过环境变量或 `.env` 覆盖，命名与字段名一致（大小写不敏感）。
默认值刻意选择"零外部依赖即可启动"：SQLite + 内存向量库 + Mock LLM，
方便本地开发、CI 与答辩演示；生产环境通过环境变量切换到 MySQL / Milvus / DeepSeek。
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DEV_SECRET = "dev-only-secret-please-change-32bytes"
WEAK_SECRETS = {
    DEFAULT_DEV_SECRET,
    "please-change-to-a-long-random-string",
    "please-change-this-secret-key-32bytes",
}


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
    secret_key: str = Field(default=DEFAULT_DEV_SECRET, min_length=16)
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
    # 2D 游戏里的儿童回答是否允许 DeepSeek 做语义复判（仅 llm_provider=deepseek 时生效）
    game_llm_judge: bool = True

    # ---------- 语音识别（ASR） ----------
    # disabled = 不启用（接口返回明确错误）；funasr = 本地 FunASR；http = 云端兼容接口
    asr_provider: Literal["disabled", "funasr", "http"] = "disabled"
    asr_model: str = "paraformer-zh"
    asr_vad_model: str = ""
    asr_punc_model: str = ""
    asr_device: str = "cpu"
    asr_language: str = "zh"
    asr_timeout_seconds: float = 120.0
    asr_max_upload_mb: float = 20.0
    asr_max_duration_seconds: float = 120.0
    asr_temp_dir: str = "data/tmp/asr"
    asr_http_url: str = ""
    asr_http_api_key: str = ""
    asr_http_model: str = "whisper-1"
    asr_http_trust_env: bool = False

    # ---------- 语音合成（TTS） ----------
    # disabled = 前端回退浏览器 voice；siliconflow = CosyVoice2 云端音色
    tts_provider: Literal["disabled", "siliconflow"] = "disabled"
    tts_model: str = "FunAudioLLM/CosyVoice2-0.5B"
    tts_voice: str = "FunAudioLLM/CosyVoice2-0.5B:diana"
    tts_speed: float = 1.0
    tts_api_key: str = ""
    tts_base_url: str = "https://api.siliconflow.cn/v1/audio/speech"
    tts_timeout_seconds: float = 60.0
    tts_max_chars: int = 1500
    tts_trust_env: bool = False

    @model_validator(mode="after")
    def _guard_secret_key(self) -> Settings:
        """生产环境禁止使用默认密钥，避免 JWT 可被伪造。"""
        if self.env == "prod" and (
            self.secret_key in WEAK_SECRETS or len(self.secret_key) < 32
        ):
            raise ValueError(
                "生产环境必须通过 SECRET_KEY 配置至少 32 位的随机密钥（不能使用默认值）"
            )
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
