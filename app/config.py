"""
config.py
=========
Centralised application settings loaded from the ``.env`` file using
``pydantic-settings``.  Every external key, connection string, and tuneable
parameter lives here so the rest of the code-base never touches raw
``os.environ`` directly.

Usage::

    from app.config import settings
    print(settings.DATABASE_URL)
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings — values are read from environment variables and
    the ``.env`` file at the project root.  Pydantic validates types
    automatically; missing required fields cause a startup error.
    """

    # ── MongoDB ─────────────────────────────────────────────────
    MONGO_URL: str 
    DB_NAME: str
    ADMIN_SECRET_KEY: str

    # ── LLM Providers ──────────────────────────────────────────
    GOOGLE_API_KEY: str
    GROQ_API_KEY: str 
    GROQ_MODEL_NAME: str 

    # ── Embedding ───────────────────────────────────────────────
    EMBEDDING_MODEL: str 
    EMBEDDING_DIMENSION: int 

    # ── Reranker (Cohere) ───────────────────────────────────────
    COHERE_API_KEY: str 

    # ── Retrieval tuning ────────────────────────────────────────
    RETRIEVAL_TOP_K: int           # candidates before reranking
    RERANK_TOP_N: int       # chunks after reranking

    # ── Conversation memory ─────────────────────────────────────
    MEMORY_LAST_N_MESSAGES: int 
    SUMMARY_UPDATE_INTERVAL: int    # update rolling summary every N messages

    # ── LLM settings ────────────────────────────────────────────
    LLM_MODEL_NAME: str 
    LLM_TEMPERATURE: float 

    # ── Server ──────────────────────────────────────────────────
    HOST: str 
    PORT: int

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",          # silently ignore extra env vars
    )


# Singleton instance — import ``settings`` everywhere.
settings = Settings()
