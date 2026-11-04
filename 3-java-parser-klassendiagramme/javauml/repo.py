"""Repo aus einem lokalen Pfad oder einer Git-URL bereitstellen."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class RepoError(Exception):
    """Das Repo ließ sich nicht finden oder nicht klonen."""


def is_url(text: str) -> bool:
    return (
        text.startswith(("https://", "http://", "git@", "ssh://"))
        or text.endswith(".git")
        or text.startswith("github.com/")
    )


def repo_name(text: str) -> str:
    """Kurzen Namen für ein Repo ableiten, etwa ``orekit`` aus der URL oder dem Pfad."""
    if is_url(text):
        name = text.rstrip("/").rsplit("/", 1)[-1].rsplit(":", 1)[-1]
        return name.removesuffix(".git") or "repo"
    return Path(text).resolve().name or "repo"


@contextmanager
def open_repo(source: str, ref: str | None = None, keep: Path | None = None) -> Iterator[Path]:
    """Repo-Wurzel für die Dauer des ``with``-Blocks liefern.

    Args:
        source: lokaler Pfad oder Git-URL. URLs werden flach geklont.
        ref: Branch oder Tag beim Klonen. Bei lokalen Pfaden nicht erlaubt.
        keep: Zielordner für den Klon. Ohne Angabe wird in ein temporäres
            Verzeichnis geklont und danach gelöscht.

    Der geklonte Code wird nur gelesen, nie gebaut oder ausgeführt.
    """
    if not is_url(source):
        if ref:
            raise RepoError("--ref geht nur zusammen mit einer Git-URL")
        path = Path(source)
        if not path.is_dir():
            raise RepoError(f"Verzeichnis nicht gefunden: {source}")
        yield path.resolve()
        return

    url = f"https://{source}" if source.startswith("github.com/") else source
    if keep is not None:
        target = keep
        if target.exists() and any(target.iterdir()):
            raise RepoError(f"Zielordner für den Klon ist nicht leer: {target}")
        _clone(url, target, ref)
        yield target.resolve()
        return

    tmp = Path(tempfile.mkdtemp(prefix="javauml-"))
    try:
        target = tmp / repo_name(source)
        _clone(url, target, ref)
        yield target
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _clone(url: str, target: Path, ref: str | None) -> None:
    cmd = ["git", "clone", "--depth=1", "--quiet"]
    if ref:
        cmd += ["--branch", ref]
    cmd += [url, str(target)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RepoError("git ist nicht installiert") from exc
    if result.returncode != 0:
        raise RepoError(f"git clone für {url} fehlgeschlagen:\n{result.stderr.strip()}")
