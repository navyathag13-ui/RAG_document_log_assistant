"""
Responsible AI safeguards: Azure AI Content Safety screening (input and
output) and a word-overlap groundedness check.

Both are explicitly optional and explicitly report their own status —
neither one silently treats "not configured" as "safe" or "grounded":

  - check_text() requires AZURE_CONTENT_SAFETY_ENDPOINT and
    AZURE_CONTENT_SAFETY_KEY. If either is missing, it returns
    checked=False, flagged=False — the caller (and GET /health, via
    content_safety_enabled) can always tell "checked, clean" apart from
    "not checked at all". This is a real API call against Azure's actual
    moderation categories (hate, self-harm, sexual, violence) when
    configured, not a hand-rolled keyword blocklist.

  - check_groundedness() is a word-overlap heuristic: what fraction of the
    answer's "meaningful" words (>=5 characters) also appear in the source
    text it was supposedly grounded in. This is the same category of check
    evaluation_service.py's groundedness_score already applies to every
    /ask response, exposed standalone here so /agent (which doesn't go
    through qa_service) can use equivalent logic without duplicating it
    differently, and expressed as a boolean flag/grounded decision instead
    of just a continuous score — "flag, don't silently allow" needs a
    decision, not just a number.

    This is NOT semantic entailment checking. It will flag some genuinely
    grounded answers that paraphrase heavily instead of reusing source
    vocabulary, and it can miss an unsupported claim that happens to reuse
    the source's words in a different arrangement. That's a real, named
    limitation — stated here and in the README, not hidden.
"""
from __future__ import annotations

import re

from app.core.config import settings
from app.core.logging_config import get_logger
from app.models.schemas import ContentSafetyResult, GroundednessResult

logger = get_logger(__name__)

# Below this many "meaningful" words in the answer, the overlap ratio is too
# noisy to mean much either way (a 3-word answer sharing 1 word with the
# source is a 33% overlap that says nothing) — treat as grounded by default
# rather than flag a trivially short answer as ungrounded.
_MIN_WORDS_FOR_CHECK = 5

# Overlap fraction below which an answer is flagged as not grounded. Chosen
# to be in the same range evaluation_service.py's raw (pre-1.4x-boost)
# groundedness ratio uses before it counts as reasonably supported — not
# independently calibrated against held-out data, since doing that honestly
# would require real LLM-generated answers to measure against, which this
# project doesn't have paid API access to generate at scale. Documented as
# a judgment call, not a measured threshold.
_GROUNDEDNESS_THRESHOLD = 0.30


def check_text(text: str) -> ContentSafetyResult:
    """
    Screen a piece of text (a user query or a generated answer) with Azure
    AI Content Safety, if configured.
    """
    if not (settings.AZURE_CONTENT_SAFETY_ENDPOINT and settings.AZURE_CONTENT_SAFETY_KEY):
        return ContentSafetyResult(
            checked=False,
            flagged=False,
            note="Content Safety not configured (AZURE_CONTENT_SAFETY_ENDPOINT / _KEY unset); text was not screened.",
        )

    if not text or not text.strip():
        return ContentSafetyResult(checked=True, flagged=False, categories={})

    try:
        from azure.ai.contentsafety import ContentSafetyClient
        from azure.ai.contentsafety.models import AnalyzeTextOptions
        from azure.core.credentials import AzureKeyCredential

        client = ContentSafetyClient(
            settings.AZURE_CONTENT_SAFETY_ENDPOINT,
            AzureKeyCredential(settings.AZURE_CONTENT_SAFETY_KEY),
        )
        # Azure Content Safety's text analysis caps input length; truncate
        # defensively rather than let a long answer fail the whole request.
        response = client.analyze_text(AnalyzeTextOptions(text=text[:10000]))

        categories = {item.category: item.severity for item in response.categories_analysis}
        threshold = settings.CONTENT_SAFETY_SEVERITY_THRESHOLD
        flagged = any(sev >= threshold for sev in categories.values())

        if flagged:
            logger.warning("Content Safety flagged text (categories=%s, threshold=%d).", categories, threshold)

        return ContentSafetyResult(
            checked=True,
            flagged=flagged,
            categories=categories,
            note=f"One or more categories >= severity {threshold}." if flagged else None,
        )
    except ImportError:
        logger.warning("azure-ai-contentsafety not installed; skipping content safety check.")
        return ContentSafetyResult(
            checked=False, flagged=False,
            note="azure-ai-contentsafety package not installed. Run: pip install azure-ai-contentsafety",
        )
    except Exception as exc:
        # A Content Safety outage should not silently mean "treat as unsafe"
        # (that would break the app on every request) or "treat as safe"
        # without saying so — report unchecked, with the reason visible.
        logger.warning("Content Safety call failed (%s); treating as unchecked, not as unsafe.", exc)
        return ContentSafetyResult(checked=False, flagged=False, note=f"Content Safety call failed: {exc}")


def check_groundedness(answer: str, source_text: str) -> GroundednessResult:
    """
    Word-overlap groundedness check between a generated answer and the
    source text it was supposedly grounded in (retrieved chunks, or a
    tool's result excerpts).
    """
    if not source_text or not source_text.strip():
        return GroundednessResult(grounded=False, overlap_ratio=0.0)

    answer_words = set(re.findall(r"\b\w{5,}\b", answer.lower()))
    source_words = set(re.findall(r"\b\w{4,}\b", source_text.lower()))

    if len(answer_words) < _MIN_WORDS_FOR_CHECK:
        return GroundednessResult(grounded=True, overlap_ratio=1.0)

    overlap = len(answer_words & source_words) / len(answer_words)
    grounded = overlap >= _GROUNDEDNESS_THRESHOLD

    if not grounded:
        logger.warning(
            "Groundedness check flagged answer: overlap=%.2f < threshold=%.2f",
            overlap, _GROUNDEDNESS_THRESHOLD,
        )

    return GroundednessResult(grounded=grounded, overlap_ratio=round(overlap, 4))
