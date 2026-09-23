"""Test setup: point storage at a temp dir and switch every cloud service off,
so the suite runs offline and never touches real data or real Azure resources."""
import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="rag_tests_")
os.environ["CHROMA_DB_PATH"] = os.path.join(_TMP, "chroma")
os.environ["EXPERIMENTS_DB_PATH"] = os.path.join(_TMP, "experiments.db")
for key in (
    "OPENAI_API_KEY",
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_DEPLOYMENT",
    "AZURE_CONTENT_SAFETY_ENDPOINT",
    "AZURE_CONTENT_SAFETY_KEY",
    "APPLICATIONINSIGHTS_CONNECTION_STRING",
):
    os.environ[key] = ""
