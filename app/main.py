"""
Engineering RAG Assistant — FastAPI application entry point.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings
from app.core.logging_config import get_logger, setup_logging


# ── Logging setup (must run before anything else) ────────────────────────────────
setup_logging()
logger = get_logger(__name__)


# ── Lifespan: warm up the embedding model at startup ─────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s v%s …", settings.APP_NAME, settings.APP_VERSION)
    # Pre-load the embedding model so the first request isn't slow
    from app.services.embedding_service import get_model
    get_model()
    logger.info("Ready. LLM synthesis: %s", "enabled" if settings.OPENAI_API_KEY else "disabled (fallback mode)")
    yield
    logger.info("Shutting down.")


# ── Application ───────────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "A retrieval-augmented generation (RAG) backend for engineering manuals, "
        "troubleshooting guides, system logs, and internal documents."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

logger.info("Routes registered: %s", [r.path for r in app.routes])
