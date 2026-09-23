import asyncio

from app.core.config import settings
from app.services import safety_service


def test_grounded_answer_passes():
    source = "The coolant pump must be inspected every 500 operating hours and the seals replaced yearly."
    answer = "Inspect the coolant pump every 500 operating hours and replace the seals yearly."
    result = safety_service.check_groundedness(answer, source)
    assert result.grounded is True
    assert result.overlap_ratio >= 0.3


def test_ungrounded_answer_is_flagged():
    source = "The coolant pump must be inspected every 500 operating hours."
    answer = "Quarterly financial statements demonstrate substantial revenue growth across international markets."
    result = safety_service.check_groundedness(answer, source)
    assert result.grounded is False


def test_empty_source_is_never_grounded():
    assert safety_service.check_groundedness("Anything at all here", "").grounded is False


def test_very_short_answers_are_not_penalised():
    assert safety_service.check_groundedness("Yes.", "Some source text about pumps").grounded is True


def test_content_safety_reports_unchecked_when_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "AZURE_CONTENT_SAFETY_ENDPOINT", "")
    monkeypatch.setattr(settings, "AZURE_CONTENT_SAFETY_KEY", "")
    result = safety_service.check_text("hello")
    assert result.checked is False and result.flagged is False
    assert "not configured" in (result.note or "").lower()


def test_async_content_safety_matches_sync_when_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "AZURE_CONTENT_SAFETY_ENDPOINT", "")
    monkeypatch.setattr(settings, "AZURE_CONTENT_SAFETY_KEY", "")
    result = asyncio.run(safety_service.check_text_async("hello"))
    assert result.checked is False and result.flagged is False
