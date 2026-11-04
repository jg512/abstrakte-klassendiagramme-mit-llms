from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FieldRef:
    """Ein deklariertes Feld, dessen Typ auf eine andere Klasse zeigt.

    Der statische Extraktor erzeugt so etwas für jedes Feld, dessen Typnamen er
    auflösen kann. Der Graph-Builder macht aus den internen davon Assoziations-
    oder Aggregationskanten. `many` deckt Collections und Arrays ab, die in UML
    gleich aussehen (0..* am Zielende).
    """
    field_name: str
    type_name: str          # so wie im Quelltext, darf qualifiziert sein (java.util.List)
    many: bool = False
    declared_type: str | None = None
    line: int | None = None
    relation_type: str | None = None
    target_card: str | None = None


@dataclass
class MethodRef:
    method_name: str
    type_name: str
    declared_type: str
    line: int | None = None


@dataclass
class ClassInfo:
    name: str
    qualified_name: str
    module: str
    bases: list[str]
    decorators: list[str]
    attributes: list[str]
    methods: list[str]
    file: Path
    line_start: int
    line_end: int
    # Optional, je nach Sprache.
    # Python lässt diese Felder leer, weil der Klassengraph dort von pyreverse
    # kommt und die Beziehungen schon mitbringt. Java füllt sie, weil der
    # tree-sitter-Extraktor dort die einzige Quelle für Beziehungen ist.
    kind: str | None = None                                  # interface | enum | record | annotation | abstract
    interfaces: list[str] = field(default_factory=list)      # Ziele der Realisierung
    field_refs: list[FieldRef] = field(default_factory=list)
    # Java-Identitäten vor dem Kürzen des Paketpräfixes festhalten. Die Imports
    # braucht man, um gleichnamige Projekt- und Bibliothekstypen zu unterscheiden.
    source_qualified_name: str = ""
    source_package: str = ""
    imports: list[str] = field(default_factory=list)
    type_parameters: list[str] = field(default_factory=list)
    method_refs: list[MethodRef] = field(default_factory=list)
    build_module: str = ""
    source_file: str = ""


@dataclass
class FunctionInfo:
    name: str
    qualified_name: str
    module: str
    file: Path
    line_start: int
    line_end: int
