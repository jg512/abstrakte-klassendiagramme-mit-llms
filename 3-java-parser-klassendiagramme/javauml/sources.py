"""Auswahl der Java-Dateien, die gelesen werden.

Übernommen aus ``src/io/filters.py`` der Pipeline (Ordner 1). Die Ausschlüsse
standen dort in ``configs/default.yaml`` und stehen hier als Standardwerte im
Code. Die Python-Muster sind weggefallen, alles andere verhält sich gleich.
"""
from __future__ import annotations

import fnmatch
import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path

log = logging.getLogger(__name__)

# Testordner, Build-Ausgaben und Begleitmaterial. In target/, bin/ und out/
# liegen oft übersetzte oder kopierte Fassungen von src/, die sonst als doppelte
# und meist veraltete Klassen gelesen würden.
DEFAULT_EXCLUDE_DIRS: tuple[str, ...] = (
    "tests", "test", "build", "dist", ".git", "docs", "examples", "benchmarks",
    "target", "bin", "out", ".gradle", ".mvn",
)
DEFAULT_EXCLUDE_FILES: tuple[str, ...] = (
    "*Test.java", "*Tests.java", "*TestCase.java", "*IT.java",
)

_GENERATED_DIRS = {
    "generated", "generated-sources", "generated-test-sources", "src-gen",
    "gen", "apt_generated", "annotationprocessor",
}


def collect_java_files(
    root: Path,
    exclude_dirs: tuple[str, ...] = DEFAULT_EXCLUDE_DIRS,
    exclude_files: tuple[str, ...] = DEFAULT_EXCLUDE_FILES,
    source_sets: str = "auto",
    include_generated: bool = False,
) -> list[Path]:
    """Alle ``.java``-Dateien unter ``root`` suchen, die durch die Filter kommen.

    Args:
        root: Wurzel des Repos.
        exclude_dirs: Muster für Verzeichnisnamen. Ein Muster mit ``**/`` am
            Anfang passt auf jeden Teil des Pfads, wie ohne Präfix auch.
        exclude_files: Muster für Dateinamen.
        source_sets: ``auto`` bevorzugt die main-Verzeichnisse nach Maven/Gradle,
            ``all`` nimmt alles, was nach den Ausschlüssen übrig bleibt.
        include_generated: generierte Quelldateien mitlesen.

    Returns:
        Die sortierte Liste der Dateien.
    """
    if source_sets not in {"auto", "all"}:
        raise ValueError(f"source_sets muss 'auto' oder 'all' sein, nicht {source_sets!r}")
    found = sorted(
        f for f in root.rglob("*.java")
        if f.is_file() and not _is_excluded(f, root, exclude_dirs, exclude_files)
    )
    if source_sets == "all" or not found:
        return found
    return _select_source_sets(root, found, include_generated)


def _select_source_sets(root: Path, files: list[Path], include_generated: bool) -> list[Path]:
    """Aktive Maven-/Gradle-Produktionsverzeichnisse bevorzugen, ohne alte Repos kaputtzumachen.

    Wer rekursiv nach ``*.java`` sucht, bekommt oft ``src/main`` zusammen mit
    generierten Kopien, Android-Tests oder anderen Varianten derselben Klasse.
    Gibt es die üblichen Produktionsverzeichnisse, nimmt der Modus auto nur
    diese. Ein Projekt ohne übliche Struktur bekommt alle gefilterten Java-Dateien.
    """
    def parts(path: Path) -> tuple[str, ...]:
        return tuple(p.lower() for p in path.relative_to(root).parts[:-1])

    def generated(path: Path) -> bool:
        return any(p in _GENERATED_DIRS or p.startswith("generated-") for p in parts(path))

    nongenerated = [p for p in files if include_generated or not generated(p)]
    if not nongenerated:
        nongenerated = files

    configured_roots = _configured_java_roots(root)

    def conventional_main(path: Path) -> bool:
        ps = parts(path)
        for i in range(len(ps) - 2):
            if ps[i] != "src" or ps[i + 2] != "java":
                continue
            source_set = ps[i + 1]
            if source_set == "main" or source_set.endswith("main"):
                return True
        return False

    def configured_main(path: Path) -> bool:
        return any(_is_below(path, source_root) for source_root in configured_roots)

    main = [p for p in nongenerated if conventional_main(p) or configured_main(p)]
    selected = main or nongenerated
    dropped = len(files) - len(selected)
    if dropped:
        log.info(
            "Quellverzeichnisse: %d von %d Dateien gewählt (%d generiert, Test oder Variante)",
            len(selected), len(files), dropped,
        )
    return sorted(selected)


def _configured_java_roots(root: Path) -> set[Path]:
    """Produktionsverzeichnisse für Java zurückgeben, die Maven oder Gradle ausdrücklich angibt.

    Build-Dateien dienen nur als Hinweis. Fehlende oder kaputte Build-Angaben
    verhindern nie, dass der Rückfall auf die übliche Struktur greift.
    """
    roots: set[Path] = set()
    for pom in root.rglob("pom.xml"):
        try:
            tree = ET.parse(pom)
            for build in tree.iter():
                if _xml_name(build.tag) != "build":
                    continue
                for child in build:
                    if _xml_name(child.tag) == "sourceDirectory" and child.text:
                        roots.add((pom.parent / child.text.strip()).resolve())
        except (ET.ParseError, OSError):
            log.debug("Maven-Quellverzeichnisse in %s nicht lesbar", pom)

    for pattern in ("build.gradle", "build.gradle.kts"):
        for build_file in root.rglob(pattern):
            try:
                text = build_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            # Groovy-/Kotlin-Schreibweisen wie sourceSets.main.java.srcDirs = [...].
            for match in re.finditer(
                r"sourceSets\s*\.\s*main\s*\.\s*java\s*\.\s*srcDirs?\s*(?:=|\()(?P<body>[^\n)]*)",
                text,
            ):
                roots.update(_quoted_paths(build_file.parent, match.group("body")))
            # Häufige verschachtelte Form: sourceSets { main { java.srcDir('src/core') } }.
            for block in _main_source_blocks(text):
                for match in re.finditer(r"\bsrcDirs?\s*(?:=|\()(?P<body>[^\n)]*)", block):
                    roots.update(_quoted_paths(build_file.parent, match.group("body")))
    return roots


def _xml_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _quoted_paths(base: Path, text: str) -> set[Path]:
    return {
        (base / value).resolve()
        for _, value in re.findall(r"(['\"])(.+?)\1", text)
        if "$" not in value and not Path(value).is_absolute()
    }


def _main_source_blocks(text: str) -> list[str]:
    """Blöcke ``main { ... }``, ``named(\"main\") { ... }`` oder ``getByName(\"main\") { ... }`` bis zur passenden schließenden Klammer herausholen."""
    starts = re.finditer(
        r"(?:\bmain\s*|\bnamed\s*\(\s*['\"]main['\"]\s*\)\s*|"
        r"\bgetByName\s*\(\s*['\"]main['\"]\s*\)\s*)\{",
        text,
    )
    blocks: list[str] = []
    for start in starts:
        depth = 1
        pos = start.end()
        while pos < len(text) and depth:
            if text[pos] == "{":
                depth += 1
            elif text[pos] == "}":
                depth -= 1
            pos += 1
        if depth == 0:
            blocks.append(text[start.end():pos - 1])
    return blocks


def _is_below(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root)
        return True
    except ValueError:
        return False


def _is_excluded(
    file: Path,
    root: Path,
    exclude_dirs: tuple[str, ...],
    exclude_files: tuple[str, ...],
) -> bool:
    rel = file.relative_to(root)
    for part in rel.parts[:-1]:
        for pat in exclude_dirs:
            name_pat = pat[3:] if pat.startswith("**/") else pat
            if fnmatch.fnmatch(part, name_pat):
                return True
    return any(fnmatch.fnmatch(file.name, pat) for pat in exclude_files)
