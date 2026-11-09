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
    # configured, then Amazon Bedrock, then plain OpenAI, then the offline fallback.
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

    # ── Amazon Bedrock (optional) ───────────────────────────────────────────────
    # Used when BEDROCK_API_KEY is set and Azure OpenAI isn't fully configured.
    # Calls Bedrock's OpenAI-compatible Chat Completions endpoint
    # (https://bedrock-runtime.<region>.amazonaws.com/openai/v1) with a Bedrock
    # API key, so the same `openai` client code serves all three providers.
    BEDROCK_API_KEY: str = ""
    BEDROCK_REGION: str = "us-west-2"
    BEDROCK_MODEL: str = "openai.gpt-oss-20b-1:0"

    # ── Azure AI Content Safety (optional) ──────────────────────────────────────
    # Both endpoint and key must be set to enable safety checks on /ask and
    # /agent. If unset, requests are NOT screened — this is stated explicitly
    # in the health check and the README, never silently assumed.
    AZURE_CONTENT_SAFETY_ENDPOINT: str = ""
    AZURE_CONTENT_SAFETY_KEY: str = ""
    CONTENT_SAFETY_SEVERITY_THRESHOLD: int = 4   # 0,2,4,6 per Azure's scale; block at >= this

    # ── MongoDB conversation history (optional) ────────────────────────────────
    # When set, every /ask and /agent turn is saved (app/db/conversation_store.py)
    # and GET /history/... is available. Unset = no history, app unchanged.
    MONGODB_URI: str = ""                 # e.g. mongodb://localhost:27017
    MONGODB_DB: str = "rag_assistant"
    MONGODB_TIMEOUT_MS: int = 2000        # fail fast if MongoDB is down; the request still succeeds

    # ── Azure Monitor / Application Insights (optional) ─────────────────────────
    APPLICATIONINSIGHTS_CONNECTION_STRING: str = ""


settings = Settings()
