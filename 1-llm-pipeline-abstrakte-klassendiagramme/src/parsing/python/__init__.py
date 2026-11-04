"""Der Python-Parser: Klassen und Funktionen mit dem ast-Modul, Importgraph,
Vererbungstabelle und der volle Klassengraph aus pyreverse. Das Gegenstück für
Java liegt in ``src/parsing/java/``."""
from __future__ import annotations

from src.parsing.python.ast_pass import module_name, run_ast_pass
from src.parsing.python.import_graph import build_import_graphs
from src.parsing.python.inheritance_graph import build_inheritance_graph
from src.parsing.python.pyreverse_adapter import parse_pyreverse_output, run_pyreverse

__all__ = [
    "build_import_graphs",
    "build_inheritance_graph",
    "module_name",
    "parse_pyreverse_output",
    "run_ast_pass",
    "run_pyreverse",
]
