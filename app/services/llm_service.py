"""
Provider-agnostic LLM client resolution.

Three possible states, checked in this order:

  1. Azure OpenAI  — used when AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY,
                      and AZURE_OPENAI_DEPLOYMENT are all set.
  2. OpenAI         — used when OPENAI_API_KEY is set (and Azure isn't fully
                      configured). This is the original project's behaviour,
                      unchanged.
  3. None           — no LLM backend configured at all. Callers (qa_service,
                      agent_service) fall back to their own offline paths;
                      this module never raises for "no LLM configured", it
                      just reports provider="none" so callers can branch on it.

Both real providers are exposed through the same `openai` Python package
(`OpenAI` and `AzureOpenAI` are both chat-completions-compatible clients),
so the rest of the app talks to one client interface regardless of which
cloud backend is behind it. Semantic Kernel's own Azure/OpenAI connectors
(app/services/agent_service.py) are built from the same resolved config so
there's exactly one place that decides which backend is active.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ResolvedLLM:
    provider: str              # "azure_openai" | "openai" | "none"
    model: str                 # Azure deployment name, or OpenAI model name
    endpoint: Optional[str] = None
    api_key: Optional[str] = None
    api_version: Optional[str] = None


def resolve() -> ResolvedLLM:
    """Decide which LLM backend (if any) is configured, without instantiating a client."""
    if (
        settings.AZURE_OPENAI_ENDPOINT
        and settings.AZURE_OPENAI_API_KEY
        and settings.AZURE_OPENAI_DEPLOYMENT
    ):
        return ResolvedLLM(
            provider="azure_openai",
            model=settings.AZURE_OPENAI_DEPLOYMENT,
            endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_API_KEY,
            api_version=settings.AZURE_OPENAI_API_VERSION,
        )

    if settings.OPENAI_API_KEY:
        return ResolvedLLM(
            provider="openai",
            model=settings.OPENAI_MODEL,
            endpoint=settings.OPENAI_BASE_URL,
            api_key=settings.OPENAI_API_KEY,
        )

    return ResolvedLLM(provider="none", model="")


def get_chat_client():
    """
    Return (client, model_name, provider) for a chat-completions-compatible
    client, or (None, "", "none") when no backend is configured.

    The returned client exposes .chat.completions.create(...) either way —
    AzureOpenAI and OpenAI share that interface — so callers don't need to
    branch on provider except for logging/attribution.
    """
    resolved = resolve()

    if resolved.provider == "azure_openai":
        from openai import AzureOpenAI

        client = AzureOpenAI(
            azure_endpoint=resolved.endpoint,
            api_key=resolved.api_key,
            api_version=resolved.api_version,
        )
        return client, resolved.model, "azure_openai"

    if resolved.provider == "openai":
        from openai import OpenAI

        client = OpenAI(api_key=resolved.api_key, base_url=resolved.endpoint)
        return client, resolved.model, "openai"

    return None, "", "none"


def is_configured() -> bool:
    return resolve().provider != "none"


def get_async_chat_client():
    """
    Async counterpart of get_chat_client(): returns (client, model_name, provider)
    using AsyncOpenAI / AsyncAzureOpenAI, or (None, "", "none") if unconfigured.

    Exists because a real network call (the LLM round-trip) held open inside a sync
    `def` route ties up one of FastAPI's limited threadpool workers for the entire
    wait — under concurrent load that serializes requests behind the pool size
    (measured: bench/before_sync.json, p50 latency 11.6s at 30 concurrent requests
    vs 1.7s at 5). An async client awaited from an `async def` route releases the
    worker back to the event loop while waiting on the network, so concurrent
    requests genuinely overlap instead of queuing for a thread.
    """
    resolved = resolve()

    if resolved.provider == "azure_openai":
        from openai import AsyncAzureOpenAI

        client = AsyncAzureOpenAI(
            azure_endpoint=resolved.endpoint,
            api_key=resolved.api_key,
            api_version=resolved.api_version,
        )
        return client, resolved.model, "azure_openai"

    if resolved.provider == "openai":
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=resolved.api_key, base_url=resolved.endpoint)
        return client, resolved.model, "openai"

    return None, "", "none"
