"""
Split a long text string into overlapping chunks.

Strategy: split on paragraph boundaries first, then bin paragraphs into
chunks of at most CHUNK_SIZE characters with CHUNK_OVERLAP overlap.
This keeps logical units together instead of cutting mid-sentence.
"""
from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


def split_text(
    text: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[str]:
    """
    Return a list of text chunks.

    Args:
        text: cleaned document text
        chunk_size: max characters per chunk (defaults to settings.CHUNK_SIZE)
        chunk_overlap: characters repeated at chunk boundaries (defaults to settings.CHUNK_OVERLAP)
    """
    chunk_size = chunk_size or settings.CHUNK_SIZE
    chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP

    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    # Split on double-newline (paragraph boundary) first
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        # If a single paragraph is longer than chunk_size, break it further
        if len(para) > chunk_size:
            sub_chunks = _split_by_sentence(para, chunk_size, chunk_overlap)
            for sc in sub_chunks:
                chunks.append(sc)
            current = ""
            continue

        candidate = (current + "\n\n" + para).strip() if current else para
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                chunks.append(current)
            # Carry overlap: last `chunk_overlap` characters of the previous chunk
            overlap_text = current[-chunk_overlap:] if chunk_overlap else ""
            current = (overlap_text + "\n\n" + para).strip() if overlap_text else para

    if current:
        chunks.append(current)

    logger.debug("Split text into %d chunks (size=%d, overlap=%d)", len(chunks), chunk_size, chunk_overlap)
    return chunks


def _split_by_sentence(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """
    Fallback splitter for paragraphs that exceed chunk_size.
    Splits on sentence boundaries ('. ', '! ', '? ') with overlap.
    """
    import re
    sentences = [
        piece
        for sentence in re.split(r"(?<=[.!?])\s+", text)
        for piece in _break_long_unit(sentence, chunk_size)
    ]
    chunks: list[str] = []
    current = ""

    for sentence in sentences:
        candidate = (current + " " + sentence).strip() if current else sentence
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                chunks.append(current)
            overlap_text = current[-chunk_overlap:] if chunk_overlap and current else ""
            current = (overlap_text + " " + sentence).strip() if overlap_text else sentence

    if current:
        chunks.append(current)

    return chunks if chunks else [text[:chunk_size]]


def _break_long_unit(unit: str, chunk_size: int) -> list[str]:
    """
    Break a single "sentence" that is still longer than chunk_size.

    Log files and tables often have no sentence punctuation, so a long run of
    lines would otherwise become one giant chunk. Prefer line boundaries, then
    word boundaries, and only cut mid-word when there is no whitespace at all.
    """
    if len(unit) <= chunk_size:
        return [unit]

    pieces: list[str] = []
    current = ""
    for line in unit.split("\n"):
        for word_group in _fit_words(line, chunk_size):
            candidate = (current + "\n" + word_group) if current else word_group
            if len(candidate) <= chunk_size:
                current = candidate
            else:
                if current:
                    pieces.append(current)
                current = word_group
    if current:
        pieces.append(current)
    return pieces


def _fit_words(line: str, chunk_size: int) -> list[str]:
    """Split one line into pieces of at most chunk_size, on spaces where possible."""
    if len(line) <= chunk_size:
        return [line]
    out: list[str] = []
    current = ""
    for word in line.split(" "):
        while len(word) > chunk_size:  # no whitespace to use: hard cut
            if current:
                out.append(current)
                current = ""
            out.append(word[:chunk_size])
            word = word[chunk_size:]
        candidate = (current + " " + word) if current else word
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            out.append(current)
            current = word
    if current:
        out.append(current)
    return out
