"""PlantUML-Text als PNG oder SVG rendern.

Gesucht wird PlantUML in dieser Reihenfolge: ausdrücklich übergebene JAR, die
Umgebungsvariable ``PLANTUML_JAR``, ein ``plantuml`` im ``PATH``. Gerendert wird
mit dem eingebauten Layout ``smetana``, damit Graphviz nicht installiert sein
muss.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


class RenderError(Exception):
    """PlantUML fehlt oder hat kein Bild erzeugt."""


def find_plantuml(jar: str | Path | None = None) -> list[str]:
    """Befehl zum Aufruf von PlantUML liefern oder ``RenderError`` werfen."""
    jar = jar or os.environ.get("PLANTUML_JAR")
    if jar:
        jar = Path(jar)
        if not jar.is_file():
            raise RenderError(f"PlantUML-JAR nicht gefunden: {jar}")
        java = shutil.which("java")
        if not java:
            raise RenderError("Zum Rendern mit der PlantUML-JAR wird Java gebraucht")
        return [java, "-Djava.awt.headless=true", "-DPLANTUML_LIMIT_SIZE=16384", "-jar", str(jar)]
    binary = shutil.which("plantuml")
    if binary:
        return [binary]
    raise RenderError("PlantUML nicht gefunden. --plantuml JAR angeben oder PLANTUML_JAR setzen")


def render(puml_file: Path, fmt: str, command: list[str], timeout: int = 600) -> Path:
    """``puml_file`` neben sich als ``.png`` bzw. ``.svg`` rendern und den Pfad zurückgeben."""
    if fmt not in {"png", "svg"}:
        raise ValueError(f"Unbekanntes Bildformat {fmt!r}")
    env = dict(os.environ)
    # Ohne die Grenze schneidet PlantUML große Diagramme bei 4096 Pixeln ab.
    env.setdefault("PLANTUML_LIMIT_SIZE", "16384")
    result = subprocess.run(
        [*command, "-Playout=smetana", f"-t{fmt}", "-charset", "UTF-8", str(puml_file)],
        capture_output=True, text=True, timeout=timeout, env=env,
    )
    out = puml_file.with_suffix(f".{fmt}")
    if result.returncode != 0 or not out.exists():
        raise RenderError(f"PlantUML ist gescheitert ({result.returncode}): "
                          f"{(result.stderr or result.stdout).strip()[:500]}")
    return out
