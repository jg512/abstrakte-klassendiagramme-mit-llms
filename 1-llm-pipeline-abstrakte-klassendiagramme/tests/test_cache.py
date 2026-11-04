from __future__ import annotations

from pathlib import Path

import pytest

from src.parsing.cache import load_cached, manifest_hash, save_cached
from src.parsing.code_graph import CodeGraph
from src.schema.graph import AbstractGraph


# manifest_hash

def test_manifest_hash_empty_list():
    h = manifest_hash([])
    assert isinstance(h, str)
    assert len(h) == 64  # SHA-256 als Hex


def test_manifest_hash_stable(tmp_path):
    f = tmp_path / "a.py"
    f.write_text("x = 1")
    h1 = manifest_hash([f])
    h2 = manifest_hash([f])
    assert h1 == h2


def test_manifest_hash_changes_on_content(tmp_path):
    f = tmp_path / "a.py"
    f.write_text("x = 1")
    h1 = manifest_hash([f])
    # Andere Länge, damit sich die Größe auch dann ändert, wenn das Dateisystem
    # die mtime nur grob auflöst
    f.write_text("x = 1  # longer content changes size")
    h2 = manifest_hash([f])
    assert h1 != h2


def test_manifest_hash_order_independent(tmp_path):
    a = tmp_path / "a.py"
    b = tmp_path / "b.py"
    a.write_text("a")
    b.write_text("b")
    assert manifest_hash([a, b]) == manifest_hash([b, a])


def test_manifest_hash_missing_file_does_not_crash(tmp_path):
    missing = tmp_path / "ghost.py"
    h = manifest_hash([missing])
    assert len(h) == 64


# load_cached / save_cached: speichern und wieder laden

def _minimal_code_graph(root: Path) -> CodeGraph:
    return CodeGraph(
        repo="test",
        root=root,
        source_files=[],
        classes=[],
        functions=[],
        module_imports={},
        package_imports={},
        inheritance={},
        static_graph=None,
    )


def test_load_cached_miss_returns_none(tmp_path):
    result = load_cached([], tmp_path / "cache")
    assert result is None


def test_save_and_load_round_trip(tmp_path):
    cache_dir = tmp_path / "cache"
    graph = _minimal_code_graph(tmp_path)
    save_cached([], graph, cache_dir)
    loaded = load_cached([], cache_dir)
    assert loaded is not None
    assert loaded.repo == "test"


def test_cache_creates_subdirectory(tmp_path):
    cache_dir = tmp_path / "cache"
    graph = _minimal_code_graph(tmp_path)
    save_cached([], graph, cache_dir)
    assert (cache_dir / "parsing").is_dir()


def test_cache_files_different_for_different_inputs(tmp_path):
    cache_dir = tmp_path / "cache"
    f1 = tmp_path / "a.py"
    f2 = tmp_path / "b.py"
    f1.write_text("x = 1")
    f2.write_text("y = 2")

    g1 = _minimal_code_graph(tmp_path)
    g1 = CodeGraph(**{**g1.__dict__, "repo": "repo1"})  # type: ignore[arg-type]
    g2 = CodeGraph(**{**g1.__dict__, "repo": "repo2"})

    save_cached([f1], g1, cache_dir)
    save_cached([f2], g2, cache_dir)

    loaded1 = load_cached([f1], cache_dir)
    loaded2 = load_cached([f2], cache_dir)
    assert loaded1 is not None
    assert loaded2 is not None
    assert loaded1.repo == "repo1"
    assert loaded2.repo == "repo2"


def test_load_cached_corrupt_file_returns_none(tmp_path):
    cache_dir = tmp_path / "cache"
    # Müll an den erwarteten Cache-Pfad schreiben
    from src.parsing.cache import manifest_hash, _CACHE_SUBDIR
    key = manifest_hash([])
    pkl_path = cache_dir / _CACHE_SUBDIR / f"{key}.pkl"
    pkl_path.parent.mkdir(parents=True, exist_ok=True)
    pkl_path.write_bytes(b"not valid pickle data")
    result = load_cached([], cache_dir)
    assert result is None
