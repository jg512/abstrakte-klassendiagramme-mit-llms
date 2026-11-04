from __future__ import annotations

import ast
from pathlib import Path

from src.parsing.python.ast_pass import module_name


def build_import_graphs(
    python_files: list[Path],
    root: Path,
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """(module_imports, package_imports) zurückgeben.

    module_imports: Modul -> sortierte Liste der importierten internen Module.
    package_imports: Paket oberster Ebene -> sortierte Liste der importierten Pakete oberster Ebene.
    Beide enthalten nur Kanten zu Modulen, die es in diesem Repo gibt.
    """
    file_to_mod: dict[Path, str] = {f: module_name(f, root) for f in python_files}
    known: set[str] = set(file_to_mod.values())

    module_imports: dict[str, list[str]] = {}
    for f, mod in file_to_mod.items():
        raw = _extract_imports(f, mod)
        internal = sorted({i for i in raw if _is_internal(i, known)})
        module_imports[mod] = internal

    pkg_imports: dict[str, set[str]] = {}
    for mod, imports in module_imports.items():
        src_pkg = mod.split(".")[0] if mod else ""
        if src_pkg not in pkg_imports:
            pkg_imports[src_pkg] = set()
        for imp in imports:
            dst_pkg = imp.split(".")[0] if imp else ""
            if dst_pkg and dst_pkg != src_pkg:
                pkg_imports[src_pkg].add(dst_pkg)

    return module_imports, {k: sorted(v) for k, v in pkg_imports.items()}


def _is_internal(imported: str, known: set[str]) -> bool:
    """True, wenn `imported` (oder ein Präfix davon) ein bekanntes Modul ist."""
    parts = imported.split(".")
    for i in range(len(parts), 0, -1):
        candidate = ".".join(parts[:i])
        if candidate in known:
            return True
    return False


def _extract_imports(file: Path, mod: str) -> list[str]:
    """Alle Modulnamen liefern, die diese Datei importiert."""
    try:
        source = file.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(file))
    except (OSError, SyntaxError):
        return []

    package = ".".join(mod.split(".")[:-1]) if "." in mod else ""
    result: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                result.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            level = node.level or 0
            module_part = node.module or ""
            names = [a.name for a in node.names]

            if level == 0:
                if module_part:
                    result.append(module_part)
                    # Zusätzlich module.name probieren, falls es ein Untermodul ist.
                    for n in names:
                        result.append(f"{module_part}.{n}")
            else:
                # Relativen Import auflösen: `level` Paketebenen nach oben gehen.
                parts = package.split(".") if package else []
                for _ in range(level - 1):
                    if parts:
                        parts.pop()
                base = ".".join(parts + [module_part]) if module_part else ".".join(parts)
                if base:
                    result.append(base)
                    for n in names:
                        result.append(f"{base}.{n}")

    return [r for r in result if r]
