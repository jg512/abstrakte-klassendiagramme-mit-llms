from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Package:
    name: str
    parent: str | None = None


@dataclass
class Node:
    id: str
    name: str
    package: str
    stereotype: str | None = None
    attributes: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)
    source_file: str | None = None
    source_line: int | None = None


@dataclass
class EdgeEvidence:
    """Nachprüfbare Fundstelle im Quelltext, die eine Beziehung im Graphen belegt."""

    # field | extends | implements | method | compiler, im IntelliJ-Modus
    # zusätzlich create | reference | nested
    kind: str
    member: str | None = None
    declared_type: str | None = None
    file: str | None = None
    line: int | None = None
    resolver: str = "source"


@dataclass
class Diagnostic:
    code: str
    message: str
    severity: str = "warning"
    source: str | None = None
    reference: str | None = None
    candidates: list[str] = field(default_factory=list)


@dataclass
class Edge:
    source: str
    target: str
    # "inheritance" | "realization" | "composition" | "aggregation"
    # | "association" | "dependency" | "nesting" (äußere -> innere Klasse)
    type: str
    # Optionale Multiplizitäten, z. B. "1", "*", "0..1". Das Modell legt sie fest.
    source_card: str | None = None
    target_card: str | None = None
    label: str | None = None
    evidence: list[EdgeEvidence] = field(default_factory=list)


@dataclass
class AbstractGraph:
    repo: str
    target_nodes: int | None
    packages: list[Package] = field(default_factory=list)
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
