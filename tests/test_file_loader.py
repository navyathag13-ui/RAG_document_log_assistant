import pytest

from app.utils.file_loader import SUPPORTED_EXTENSIONS, load_file


def test_loads_text_and_reports_type(tmp_path):
    f = tmp_path / "note.txt"
    f.write_text("Pump P-101 vibration limit is 4.5 mm/s.")
    text, kind = load_file(f)
    assert "vibration limit" in text
    assert kind == "txt"


def test_loads_markdown_and_logs(tmp_path):
    for name in ("a.md", "b.log"):
        f = tmp_path / name
        f.write_text("content here for the loader")
        assert load_file(f)[0].startswith("content")


def test_rejects_unsupported_extension(tmp_path):
    f = tmp_path / "data.exe"
    f.write_text("nope")
    with pytest.raises(ValueError, match="Unsupported"):
        load_file(f)


def test_rejects_empty_file(tmp_path):
    f = tmp_path / "empty.txt"
    f.write_text("   \n  ")
    with pytest.raises(ValueError):
        load_file(f)


def test_supported_extension_set():
    assert SUPPORTED_EXTENSIONS == {".txt", ".md", ".log", ".pdf"}
