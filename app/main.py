"""
Engineering RAG Assistant — FastAPI application entry point (v3).
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.api.eval_routes import eval_router
from app.api.agent_routes import agent_router
from app.core.config import settings
from app.core.logging_config import get_logger, setup_logging
from app.services import llm_service


# ── Logging setup (must run before anything else) ────────────────────────────────
setup_logging()
logger = get_logger(__name__)


# ── Azure Monitor / Application Insights (optional) ──────────────────────────────
# Gated entirely on APPLICATIONINSIGHTS_CONNECTION_STRING being set. When it
# isn't, telemetry just stays as the local stdout logging that was already
# there -- this doesn't change behavior at all in that case, only adds to it.
# configure_azure_monitor() also auto-instruments the standard `logging`
# module, so every existing logger.info/.warning call in this codebase
# (nothing rewritten for this) starts shipping to App Insights as trace
# entries once this is enabled, in addition to the request/dependency
# tracing FastAPIInstrumentor adds below.
if settings.APPLICATIONINSIGHTS_CONNECTION_STRING:
    from azure.monitor.opentelemetry import configure_azure_monitor

    configure_azure_monitor(connection_string=settings.APPLICATIONINSIGHTS_CONNECTION_STRING)
    logger.info("Azure Monitor telemetry enabled.")
else:
    logger.info("APPLICATIONINSIGHTS_CONNECTION_STRING not set; telemetry stays local (stdout) only.")


# ── Lifespan: warm up models and initialise DB at startup ────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s v%s …", settings.APP_NAME, settings.APP_VERSION)

    # Pre-load the embedding model so the first request isn't slow
    from app.services.embedding_service import get_model
    get_model()

    # Initialise SQLite schema and seed built-in prompt templates
    from app.db.init_db import init_db
    init_db()

    resolved_llm = llm_service.resolve()
    logger.info(
        "Ready. LLM synthesis: %s. Content Safety: %s.",
        f"enabled ({resolved_llm.provider})" if resolved_llm.provider != "none" else "disabled (fallback mode)",
        "enabled" if (settings.AZURE_CONTENT_SAFETY_ENDPOINT and settings.AZURE_CONTENT_SAFETY_KEY) else "disabled (unscreened)",
    )
    yield
    logger.info("Shutting down.")


# ── Application ───────────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "A retrieval-augmented generation (RAG) backend for engineering manuals, "
        "troubleshooting guides, system logs, and internal documents. "
        "v2 adds prompt template management, side-by-side comparison, "
        "answer evaluation, and experiment tracking. v3 adds Azure OpenAI "
        "integration, Semantic Kernel agent orchestration with real function "
        "calling, and responsible AI safeguards (Content Safety + groundedness)."
    ),
    lifespan=lifespan,
)

if settings.APPLICATIONINSIGHTS_CONNECTION_STRING:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(eval_router)
app.include_router(agent_router)

logger.info(
    "Routes registered: %s",
    [r.path for r in app.routes if hasattr(r, "path")],
)
