from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FieldRef:
    """Ein deklariertes Feld, dessen Typ auf eine andere Klasse zeigt.

    Der statische Extraktor legt so einen Eintrag für jedes Feld an, dessen
    Typnamen er auflösen kann. Aus denen, die auf Klassen im Repo zeigen, macht
    der Graph-Builder Assoziations- oder Aggregationskanten. `many` deckt
    Collections und Arrays ab, die in UML gleich aussehen (0..* am Zielende).
    """
    field_name: str
    type_name: str          # wie im Quelltext, darf qualifiziert sein (java.util.List)
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
    # Beziehungen und Herkunft
    # Die Felder unten haben Standardwerte, weil das Datenmodell aus der
    # Pipeline in Ordner 1 stammt, wo Python-Klassen sie leer lassen.
    kind: str | None = None                                  # interface | enum | record | annotation | abstract
    interfaces: list[str] = field(default_factory=list)      # Ziele der Realisierung
    field_refs: list[FieldRef] = field(default_factory=list)
    # Die Java-Namen, wie sie vor dem Kürzen des Paketpräfixes lauteten. Die Imports
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
