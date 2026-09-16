from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # ── Application ──────────────────────────────────────────────────────────────
    APP_NAME: str = "Engineering RAG Assistant"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False

    # ── Storage paths ────────────────────────────────────────────────────────────
    DATA_DIR: str = "data"
    CHROMA_DB_PATH: str = "data/chroma_db"
    CHROMA_COLLECTION_NAME: str = "engineering_docs"
    EXPERIMENTS_DB_PATH: str = "data/experiments.db"  # SQLite for experiment tracking

    # ── Embedding ────────────────────────────────────────────────────────────────
    # Sentence-transformers model; downloaded automatically on first run (~90 MB).
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # ── Text chunking ────────────────────────────────────────────────────────────
    CHUNK_SIZE: int = 500        # characters per chunk
    CHUNK_OVERLAP: int = 50      # overlap between consecutive chunks

    # ── Retrieval ────────────────────────────────────────────────────────────────
    DEFAULT_TOP_K: int = 5
    HYBRID_ALPHA: float = 0.7    # weight for semantic vs BM25 (1.0 = pure semantic)

    # ── LLM (optional) ───────────────────────────────────────────────────────────
    # Leave both OpenAI and Azure OpenAI settings blank to run in
    # retrieval-only (no-LLM) mode. See app/services/llm_service.py for the
    # exact resolution order: Azure OpenAI is tried first if fully
    # configured, then plain OpenAI, then the offline fallback.
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-3.5-turbo"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    MAX_CONTEXT_CHARS: int = 6000   # approximate context budget sent to LLM

    # ── Azure OpenAI Service (optional, preferred over plain OpenAI) ───────────
    # All three of endpoint/key/deployment must be set for Azure OpenAI to be
    # used. Get these from an Azure OpenAI resource + a model deployment in
    # Azure AI Foundry / the Azure Portal — see README "Azure setup" section.
    AZURE_OPENAI_ENDPOINT: str = ""       # e.g. https://<resource>.openai.azure.com/
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_DEPLOYMENT: str = ""     # deployment name, e.g. "gpt-4o-mini"
    AZURE_OPENAI_API_VERSION: str = "2024-10-21"

    # ── Azure AI Content Safety (optional) ──────────────────────────────────────
    # Both endpoint and key must be set to enable safety checks on /ask and
    # /agent. If unset, requests are NOT screened — this is stated explicitly
    # in the health check and the README, never silently assumed.
    AZURE_CONTENT_SAFETY_ENDPOINT: str = ""
    AZURE_CONTENT_SAFETY_KEY: str = ""
    CONTENT_SAFETY_SEVERITY_THRESHOLD: int = 4   # 0,2,4,6 per Azure's scale; block at >= this

    # ── Azure Monitor / Application Insights (optional) ─────────────────────────
    APPLICATIONINSIGHTS_CONNECTION_STRING: str = ""


settings = Settings()
