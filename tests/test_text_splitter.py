from app.utils.text_splitter import split_text


def test_short_text_is_one_chunk():
    assert split_text("A short sentence.", chunk_size=100, chunk_overlap=10) == ["A short sentence."]


def test_empty_text_gives_no_chunks():
    assert split_text("", chunk_size=100, chunk_overlap=10) == []


def test_chunks_respect_the_size_limit():
    text = " ".join(f"Sentence number {i} is here." for i in range(200))
    chunks = split_text(text, chunk_size=200, chunk_overlap=20)
    assert len(chunks) > 1
    assert all(len(c) <= 200 + 20 for c in chunks)


def test_no_content_is_lost():
    words = [f"word{i}" for i in range(400)]
    chunks = split_text(" ".join(words), chunk_size=150, chunk_overlap=15)
    joined = " ".join(chunks)
    assert all(w in joined for w in words)


def test_consecutive_chunks_overlap():
    text = " ".join(f"token{i}" for i in range(300))
    chunks = split_text(text, chunk_size=120, chunk_overlap=30)
    assert len(chunks) > 2
    shared = 0
    for a, b in zip(chunks, chunks[1:]):
        if set(a.split()[-3:]) & set(b.split()[:6]):
            shared += 1
    assert shared >= len(chunks) - 2


def test_log_with_no_blank_lines_or_punctuation_is_still_split():
    """Regression: a long run of log lines used to become one giant chunk."""
    log = "\n".join(f"2026-09-2{i % 9} 10:{i % 60:02d}:00 ERROR pump P-{i} vibration high code W{i}" for i in range(400))
    chunks = split_text(log, chunk_size=500, chunk_overlap=50)
    assert len(chunks) > 20
    assert max(len(c) for c in chunks) <= 500 + 50 + 2
    assert all(f"P-{i} " in " ".join(chunks) for i in (0, 199, 399))


def test_text_with_no_whitespace_is_hard_cut():
    chunks = split_text("x" * 2000, chunk_size=500, chunk_overlap=50)
    assert len(chunks) >= 4
    assert max(len(c) for c in chunks) <= 500 + 50 + 2
