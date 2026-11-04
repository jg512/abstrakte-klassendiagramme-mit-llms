from __future__ import annotations

import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"
_INSERT_RE = re.compile(r"<insert:\s*(\S+)\s*>")


def load_prompt(name: str, prompts_dir: Path | None = None) -> tuple[str, str]:
    """Lädt eine Prompt-Datei und gibt (Versions-Tag, Inhalt) zurück.

    Die erste Zeile `# vN` mit der Version wird entfernt, `<insert: dateiname>`
    wird durch den Dateiinhalt ersetzt. Der Inhalt kann direkt als Prompt benutzt
    werden. Platzhalter ({name}) bleiben stehen. Der Aufrufer füllt sie mit
    str.replace (siehe die _fill-Helfer) und nicht mit str.format, damit
    geschweifte Klammern im Prompttext keinen Fehler auslösen.
    """
    dir_ = prompts_dir or _PROMPTS_DIR
    path = dir_ / name
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    version = "v?"
    start = 0
    if lines and lines[0].startswith("#"):
        version = lines[0].strip().lstrip("#").strip()
        start = 1
        if len(lines) > 1 and not lines[1].strip():
            start = 2

    body = "".join(lines[start:])
    body = _expand_inserts(body, dir_)
    log.debug("Loaded prompt %s (%s)", name, version)
    return version, body


def _expand_inserts(text: str, prompts_dir: Path) -> str:
    def _replace(m: re.Match) -> str:
        _, frag = load_prompt(m.group(1), prompts_dir)
        return frag.rstrip("\n")

    return _INSERT_RE.sub(_replace, text)
