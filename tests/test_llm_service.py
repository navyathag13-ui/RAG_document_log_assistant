"""Provider resolution in app/services/llm_service.py (no network calls)."""
import pytest

from app.core.config import settings
from app.services import llm_service


@pytest.fixture
def clean_llm_settings(monkeypatch):
    for name in (
        "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_DEPLOYMENT",
        "BEDROCK_API_KEY", "OPENAI_API_KEY",
    ):
        monkeypatch.setattr(settings, name, "")
    monkeypatch.setattr(settings, "BEDROCK_REGION", "us-west-2")
    monkeypatch.setattr(settings, "BEDROCK_MODEL", "openai.gpt-oss-20b-1:0")
    return monkeypatch


def test_bedrock_selected_when_key_set(clean_llm_settings):
    clean_llm_settings.setattr(settings, "BEDROCK_API_KEY", "test-key")
    resolved = llm_service.resolve()
    assert resolved.provider == "bedrock"
    assert resolved.model == "openai.gpt-oss-20b-1:0"
    assert resolved.endpoint == "https://bedrock-runtime.us-west-2.amazonaws.com/openai/v1"


def test_bedrock_region_changes_endpoint(clean_llm_settings):
    clean_llm_settings.setattr(settings, "BEDROCK_API_KEY", "test-key")
    clean_llm_settings.setattr(settings, "BEDROCK_REGION", "us-east-1")
    assert llm_service.resolve().endpoint == "https://bedrock-runtime.us-east-1.amazonaws.com/openai/v1"


def test_azure_takes_precedence_over_bedrock(clean_llm_settings):
    clean_llm_settings.setattr(settings, "BEDROCK_API_KEY", "test-key")
    clean_llm_settings.setattr(settings, "AZURE_OPENAI_ENDPOINT", "https://x.openai.azure.com/")
    clean_llm_settings.setattr(settings, "AZURE_OPENAI_API_KEY", "k")
    clean_llm_settings.setattr(settings, "AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini")
    assert llm_service.resolve().provider == "azure_openai"


def test_bedrock_takes_precedence_over_openai(clean_llm_settings):
    clean_llm_settings.setattr(settings, "BEDROCK_API_KEY", "test-key")
    clean_llm_settings.setattr(settings, "OPENAI_API_KEY", "sk-test")
    assert llm_service.resolve().provider == "bedrock"


def test_bedrock_clients_point_at_bedrock(clean_llm_settings):
    clean_llm_settings.setattr(settings, "BEDROCK_API_KEY", "test-key")
    client, model, provider = llm_service.get_chat_client()
    assert provider == "bedrock" and model == "openai.gpt-oss-20b-1:0"
    assert str(client.base_url).rstrip("/") == "https://bedrock-runtime.us-west-2.amazonaws.com/openai/v1"
    aclient, _, aprovider = llm_service.get_async_chat_client()
    assert aprovider == "bedrock"
    assert str(aclient.base_url).rstrip("/") == "https://bedrock-runtime.us-west-2.amazonaws.com/openai/v1"


def test_no_provider_when_nothing_set(clean_llm_settings):
    assert llm_service.resolve().provider == "none"
    assert llm_service.get_chat_client() == (None, "", "none")
