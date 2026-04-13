"""
Load raw text from supported file types: .txt, .md, .log, .pdf
"""
import re
from pathlib import Path

from app.core.logging_config import get_logger

logger = get_logger(__name__)

SUPPORTED_EXTENSIONS = {".txt", ".md", ".log", ".pdf"}


def load_file(file_path: str | Path) -> tuple[str, str]:
    """
    Load a file and return (raw_text, detected_file_type).

    Raises:
        ValueError: unsupported extension or empty content
        RuntimeError: PDF extraction failure
    """
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{ext}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    logger.info("Loading file: %s (type=%s)", path.name, ext)

    if ext == ".pdf":
        text = _load_pdf(path)
        file_type = "pdf"
    else:
        text = _load_text(path)
        file_type = ext.lstrip(".")   # "txt", "md", "log"

    text = _clean_text(text)

    if not text.strip():
        raise ValueError(f"File '{path.name}' contains no extractable text.")

    logger.info("Loaded %d characters from '%s'", len(text), path.name)
    return text, file_type


def _load_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"Could not decode '{path.name}' with any supported encoding.")


def _load_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise RuntimeError(
            "pypdf is required for PDF support. Install it: pip install pypdf"
        )

    try:
        reader = PdfReader(str(path))
        pages = []
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text() or ""
            if page_text.strip():
                pages.append(f"[Page {i + 1}]\n{page_text}")
        if not pages:
            raise RuntimeError(f"No text could be extracted from '{path.name}'.")
        return "\n\n".join(pages)
    except Exception as exc:
        raise RuntimeError(f"PDF extraction failed for '{path.name}': {exc}") from exc


def _clean_text(text: str) -> str:
    """Normalise whitespace while preserving paragraph structure."""
    # Collapse runs of 3+ blank lines into two newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Remove null bytes and other control characters (keep tab/newline)
    text = re.sub(r"[^\S\n\t ]+", " ", text)
    return text.strip()
