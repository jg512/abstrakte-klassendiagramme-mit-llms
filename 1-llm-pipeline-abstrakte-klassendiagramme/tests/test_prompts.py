from __future__ import annotations

from pathlib import Path

import pytest

from src.prompts.loader import load_prompt


def _write(prompts_dir: Path, name: str, content: str) -> None:
    (prompts_dir / name).write_text(content, encoding="utf-8")


def test_load_strips_version_header(tmp_path):
    _write(tmp_path, "test.txt", "# v1\nHello world\n")
    version, body = load_prompt("test.txt", tmp_path)
    assert version == "v1"
    assert body.strip() == "Hello world"


def test_load_strips_blank_line_after_header(tmp_path):
    _write(tmp_path, "test.txt", "# v2\n\nActual content\n")
    version, body = load_prompt("test.txt", tmp_path)
    assert version == "v2"
    assert body.strip() == "Actual content"


def test_load_no_version_header(tmp_path):
    _write(tmp_path, "test.txt", "No header here\n")
    version, body = load_prompt("test.txt", tmp_path)
    assert version == "v?"
    assert "No header here" in body


def test_load_expands_insert(tmp_path):
    _write(tmp_path, "frag.txt", "# v1\nFragment content\n")
    _write(tmp_path, "main.txt", "# v1\nBefore\n<insert: frag.txt>\nAfter\n")
    _, body = load_prompt("main.txt", tmp_path)
    assert "Fragment content" in body
    assert "Before" in body
    assert "After" in body


def test_load_insert_strips_version_from_fragment(tmp_path):
    _write(tmp_path, "frag.txt", "# v3\nFragment body\n")
    _write(tmp_path, "main.txt", "# v1\n<insert: frag.txt>\n")
    _, body = load_prompt("main.txt", tmp_path)
    assert "v3" not in body
    assert "Fragment body" in body


def test_load_nested_inserts(tmp_path):
    _write(tmp_path, "inner.txt", "# v1\nInner\n")
    _write(tmp_path, "middle.txt", "# v1\nMiddle\n<insert: inner.txt>\n")
    _write(tmp_path, "outer.txt", "# v1\n<insert: middle.txt>\nOuter\n")
    _, body = load_prompt("outer.txt", tmp_path)
    assert "Inner" in body
    assert "Middle" in body
    assert "Outer" in body


def test_load_real_core_definition():
    """Prüft grob, dass die echten Prompt-Dateien ohne Fehler laden."""
    version, body = load_prompt("core_definition.txt")
    assert version.startswith("v")
    assert len(body) > 50


def test_load_real_driver_system_expands_inserts():
    _, body = load_prompt("driver_system.txt")
    # Die Inserts müssen ersetzt sein (die ursprünglichen Tags sind weg)
    assert "<insert:" not in body
    # Der gemeinsame Inhalt muss drinstehen
    assert "Include a class" in body  # aus core_definition.txt
