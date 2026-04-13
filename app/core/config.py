from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # ── Application ──────────────────────────────────────────────────────────────
    APP_NAME: str = "Engineering RAG Assistant"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # ── Storage paths ────────────────────────────────────────────────────────────
    DATA_DIR: str = "data"
    CHROMA_DB_PATH: str = "data/chroma_db"
    CHROMA_COLLECTION_NAME: str = "engineering_docs"

    # ── Embedding ────────────────────────────────────────────────────────────────
    # Sentence-transformers model; downloaded automatically on first run (~90 MB).
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # ── Text chunking ────────────────────────────────────────────────────────────
    CHUNK_SIZE: int = 500        # characters per chunk
    CHUNK_OVERLAP: int = 50      # overlap between consecutive chunks

    # ── Retrieval ────────────────────────────────────────────────────────────────
    DEFAULT_TOP_K: int = 5

    # ── LLM (optional) ───────────────────────────────────────────────────────────
    # Leave OPENAI_API_KEY blank to run in retrieval-only (no-LLM) mode.
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-3.5-turbo"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    MAX_CONTEXT_CHARS: int = 6000   # approximate context budget sent to LLM


settings = Settings()
