from __future__ import annotations

import atexit
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Iterator


class RepoLoadError(Exception):
    pass


def load_repo(input_str: str) -> Iterator[Path]:
    """Einen oder mehrere Repo-Wurzelpfade aus einer Eingabe liefern.

    Reihenfolge der Erkennung:
    - Endet auf .txt: Batch-Datei. Jede Zeile, die nicht leer und kein
      Kommentar ist, wird wieder aufgelöst.
    - Sieht aus wie eine URL (beginnt mit https:// oder enthält github.com):
      flach in ein temporäres Verzeichnis klonen.
    - Sonst: lokaler Pfad, der existieren muss.
    """
    input_str = input_str.strip()

    if input_str.endswith(".txt"):
        yield from _load_batch(input_str)
    elif _is_url(input_str):
        yield _clone_repo(input_str)
    else:
        path = Path(input_str)
        if not path.exists():
            raise RepoLoadError(f"Path not found: {input_str}")
        yield path


def _is_url(s: str) -> bool:
    return s.startswith("https://") or "github.com" in s


def _load_batch(batch_input: str) -> Iterator[Path]:
    batch_path = Path(batch_input)
    if not batch_path.exists():
        raise RepoLoadError(f"Batch file not found: {batch_input}")
    for line in batch_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            yield from load_repo(line)


def _clone_repo(url: str) -> Path:
    """Repo flach in ein temporäres Verzeichnis klonen und den Pfad zurückgeben."""
    repo_name = url.rstrip("/").split("/")[-1].removesuffix(".git") or "repo"
    tmp_parent = Path(tempfile.mkdtemp())
    atexit.register(shutil.rmtree, tmp_parent, True)
    clone_path = tmp_parent / repo_name
    result = subprocess.run(
        ["git", "clone", "--depth=1", url, str(clone_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RepoLoadError(
            f"git clone failed for {url}:\n{result.stderr.strip()}"
        )
    return clone_path
