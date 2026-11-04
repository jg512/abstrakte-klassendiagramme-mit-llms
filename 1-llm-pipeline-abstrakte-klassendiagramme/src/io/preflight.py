from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

from src.config.models import SizeCapsConfig
from src.parsing.languages import DEFAULT_LANGUAGE, LanguageSpec, resolve_language


@dataclass
class PreflightResult:
    root: Path
    source_files: list[Path]
    loc: int
    class_count: int


class PreflightError(Exception):
    pass


# Grobe Zählung über die Struktur. Der Preflight läuft vor dem eigentlichen
# Parsen und braucht nur die Größenordnung, um die Grenzen durchzusetzen und
# max_nodes zu kappen.
_JAVA_TYPE_RE = re.compile(
    r"^\s*(?:(?:public|protected|private|abstract|final|static|sealed|non-sealed|strictfp)\s+)*"
    r"(?:class|interface|enum|record)\s+\w+",
    re.MULTILINE,
)


def run_preflight(
    root: Path,
    source_files: list[Path],
    caps: SizeCapsConfig,
    language: str | LanguageSpec = DEFAULT_LANGUAGE,
) -> PreflightResult:
    """LOC und Klassen zählen. Wirft PreflightError, wenn das Repo leer ist oder über den Grenzen liegt."""
    spec = language if isinstance(language, LanguageSpec) else resolve_language(language)

    if not source_files:
        raise PreflightError(f"No {spec.name.capitalize()} files found in {root}")

    loc = 0
    class_count = 0

    for f in source_files:
        source = _read(f, spec)
        if source is None:
            continue
        loc += len(source.splitlines())
        class_count += _count_classes(source, spec)

    if loc > caps.max_loc:
        raise PreflightError(
            f"LOC count {loc:,} exceeds max_loc {caps.max_loc:,} in {root}"
        )
    if class_count > caps.max_classes:
        raise PreflightError(
            f"Class count {class_count} exceeds max_classes {caps.max_classes} in {root}"
        )

    return PreflightResult(
        root=root,
        source_files=source_files,
        loc=loc,
        class_count=class_count,
    )


def _read(f: Path, spec: LanguageSpec) -> str | None:
    if spec.name == "java":
        # Alter Java-Code ist oft ISO-8859-1, daher derselbe Rückfall wie im Parser.
        from src.parsing.java.ts_pass import read_source
        try:
            data, _ = read_source(f)
        except OSError:
            return None
        return data.decode("utf-8", "replace")
    try:
        return f.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _count_classes(source: str, spec: LanguageSpec) -> int:
    if spec.name == "java":
        return len(_JAVA_TYPE_RE.findall(source))
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return 0
    return sum(1 for node in ast.walk(tree) if isinstance(node, ast.ClassDef))
