from __future__ import annotations

import ast
import logging
from pathlib import Path

from src.parsing.models import ClassInfo, FunctionInfo

logger = logging.getLogger(__name__)

__all__ = ["ClassInfo", "FunctionInfo", "run_ast_pass", "module_name"]

_USEFUL_DUNDERS = frozenset({
    "__init__", "__call__", "__str__", "__repr__",
    "__len__", "__iter__", "__next__", "__contains__",
    "__enter__", "__exit__", "__getitem__", "__setitem__",
    "__delitem__", "__getattr__", "__setattr__", "__aenter__", "__aexit__",
})


def run_ast_pass(
    python_files: list[Path],
    root: Path,
) -> tuple[list[ClassInfo], list[FunctionInfo]]:
    """ClassInfo für Klassen auf oberster Ebene und FunctionInfo für Modulfunktionen aus allen Dateien holen."""
    classes: list[ClassInfo] = []
    functions: list[FunctionInfo] = []

    for f in python_files:
        module = module_name(f, root)
        try:
            source = f.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(f))
        except (OSError, SyntaxError) as exc:
            logger.warning("Skipping %s: %s", f, exc)
            continue
        _extract_module(tree, module, f, classes, functions)

    return classes, functions


def module_name(file: Path, root: Path) -> str:
    """Repo-relativen Dateipfad in einen Modulnamen mit Punkten umwandeln."""
    rel = file.relative_to(root)
    parts = list(rel.parts)
    parts[-1] = parts[-1][:-3]  # ".py" abschneiden
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts) if parts else ""


def _extract_module(
    tree: ast.Module,
    module: str,
    file: Path,
    classes: list[ClassInfo],
    functions: list[FunctionInfo],
) -> None:
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            classes.append(_extract_class(node, module, file))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(_extract_function(node, module, file))


def _extract_class(node: ast.ClassDef, module: str, file: Path) -> ClassInfo:
    qualified = f"{module}.{node.name}" if module else node.name
    bases = [_unparse(b) for b in node.bases]
    decorators = [_unparse(d) for d in node.decorator_list]
    attributes = _extract_attributes(node)
    methods = _extract_methods(node)

    return ClassInfo(
        name=node.name,
        qualified_name=qualified,
        module=module,
        bases=[b for b in bases if b],
        decorators=[d for d in decorators if d],
        attributes=attributes[:15],
        methods=methods[:15],
        file=file,
        line_start=node.lineno,
        line_end=node.end_lineno or node.lineno,
    )


def _extract_attributes(cls_node: ast.ClassDef) -> list[str]:
    seen: dict[str, str] = {}  # name -> "name: typ" oder "name"

    for child in ast.iter_child_nodes(cls_node):
        if isinstance(child, ast.AnnAssign):
            name = _unparse(child.target)
            if name and not name.startswith("_"):
                ann = _unparse(child.annotation)
                seen[name] = f"{name}: {ann}" if ann else name
        elif isinstance(child, ast.Assign):
            for t in child.targets:
                name = _unparse(t)
                if name and not name.startswith("_") and name not in seen:
                    seen[name] = name

    for child in ast.iter_child_nodes(cls_node):
        if (
            isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            and child.name == "__init__"
        ):
            for stmt in ast.walk(child):
                if isinstance(stmt, ast.AnnAssign):
                    if (
                        isinstance(stmt.target, ast.Attribute)
                        and isinstance(stmt.target.value, ast.Name)
                        and stmt.target.value.id == "self"
                    ):
                        name = stmt.target.attr
                        if not name.startswith("_") and name not in seen:
                            ann = _unparse(stmt.annotation)
                            seen[name] = f"{name}: {ann}" if ann else name
                elif isinstance(stmt, ast.Assign):
                    for t in stmt.targets:
                        if (
                            isinstance(t, ast.Attribute)
                            and isinstance(t.value, ast.Name)
                            and t.value.id == "self"
                        ):
                            name = t.attr
                            if name and not name.startswith("_") and name not in seen:
                                seen[name] = name

    return list(seen.values())


def _extract_methods(cls_node: ast.ClassDef) -> list[str]:
    methods = []
    for child in ast.iter_child_nodes(cls_node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            n = child.name
            if not n.startswith("_") or n in _USEFUL_DUNDERS:
                methods.append(_method_sig(child))
    return methods


def _method_sig(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    skip = {"self", "cls"}
    args = node.args
    params: list[str] = []
    for a in (*args.posonlyargs, *args.args):
        if a.arg not in skip:
            params.append(a.arg)
    if args.vararg:
        params.append(f"*{args.vararg.arg}")
    for a in args.kwonlyargs:
        params.append(a.arg)
    if args.kwarg:
        params.append(f"**{args.kwarg.arg}")
    return f"{node.name}({', '.join(params)})"


def _extract_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    module: str,
    file: Path,
) -> FunctionInfo:
    qualified = f"{module}.{node.name}" if module else node.name
    return FunctionInfo(
        name=node.name,
        qualified_name=qualified,
        module=module,
        file=file,
        line_start=node.lineno,
        line_end=node.end_lineno or node.lineno,
    )


def _unparse(node: ast.expr) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return ""
