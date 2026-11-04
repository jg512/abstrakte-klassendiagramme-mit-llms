from __future__ import annotations

import hashlib
import logging
import pickle
from pathlib import Path

log = logging.getLogger(__name__)

_CACHE_SUBDIR = "parsing"
_PARSER_CACHE_VERSION = 4  # Kantenart nesting und IntelliJ-Modus dazugekommen.


def manifest_hash(
    source_files: list[Path], language: str = "python", variant: str = ""
) -> str:
    """SHA-256 über (Sprache, Pfad, Größe, mtime) jeder Datei.

    Die Sprache gehört in den Schlüssel: Dasselbe Verzeichnis als Python und als
    Java geparst ergibt verschiedene CodeGraphs, und ein gemeinsamer Schlüssel
    würde den falschen liefern.
    """
    h = hashlib.sha256()
    h.update(f"parser:{_PARSER_CACHE_VERSION}\n".encode())
    h.update(f"lang:{language}\n".encode())
    h.update(f"variant:{variant}\n".encode())
    for p in sorted(source_files):
        try:
            stat = p.stat()
            h.update(f"{p}:{stat.st_size}:{stat.st_mtime_ns}\n".encode())
        except OSError:
            h.update(f"{p}:missing\n".encode())
    return h.hexdigest()


def load_cached(
    source_files: list[Path], cache_dir: Path, language: str = "python",
    variant: str = "",
):
    """Gecachten CodeGraph zurückgeben, oder None, wenn nichts da ist."""
    key = manifest_hash(source_files, language, variant)
    cache_path = cache_dir / _CACHE_SUBDIR / f"{key}.pkl"
    if not cache_path.exists():
        log.debug("Parser cache miss: %s", cache_path.name)
        return None
    try:
        graph = pickle.loads(cache_path.read_bytes())
        log.debug("Parser cache hit: %s", cache_path.name)
        return graph
    except Exception as exc:
        log.warning("Parser cache read failed (%s) — ignoring: %s", cache_path.name, exc)
        return None


def save_cached(source_files: list[Path], graph, cache_dir: Path,
                language: str = "python", variant: str = "") -> None:
    """CodeGraph per Pickle in den Cache schreiben."""
    key = manifest_hash(source_files, language, variant)
    cache_subdir = cache_dir / _CACHE_SUBDIR
    cache_subdir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_subdir / f"{key}.pkl"
    try:
        cache_path.write_bytes(pickle.dumps(graph))
        log.debug("Parser cache written: %s", cache_path.name)
    except Exception as exc:
        log.warning("Parser cache write failed: %s", exc)
