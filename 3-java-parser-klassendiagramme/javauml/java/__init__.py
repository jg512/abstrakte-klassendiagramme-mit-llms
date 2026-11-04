"""Der Parser: Syntaxbaum, Typauflösung und die beiden Graphen (wörtlich, IntelliJ)."""
from __future__ import annotations

from javauml.java.graph_builder import build_java_graph
from javauml.java.intellij import IdeEnvironment, build_intellij_graph
from javauml.java.ts_pass import (
    JavaParseResult,
    JavaParserUnavailable,
    analyze_java,
    read_source,
    run_java_pass,
)

__all__ = [
    "IdeEnvironment",
    "JavaParserUnavailable",
    "JavaParseResult",
    "analyze_java",
    "build_intellij_graph",
    "build_java_graph",
    "read_source",
    "run_java_pass",
]
