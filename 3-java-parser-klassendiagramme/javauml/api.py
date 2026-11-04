"""Einstiegspunkt als Bibliothek: Repo rein, Klassengraph raus.

Setzt die Schritte so zusammen wie ``_build_java`` in
``src/parsing/code_graph.py`` der Pipeline (Ordner 1), ohne den Rest, den nur
die LLM-Varianten brauchen (Paketgraph, Vererbungstabelle, Cache).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from javauml.java.graph_builder import build_java_graph
from javauml.java.intellij import IdeEnvironment, build_intellij_graph
from javauml.java.ts_pass import analyze_java
from javauml.schema.graph import AbstractGraph, Diagnostic
from javauml.schema.json_io import graph_to_json
from javauml.schema.plantuml import to_plantuml
from javauml.sources import DEFAULT_EXCLUDE_DIRS, DEFAULT_EXCLUDE_FILES, collect_java_files

MODES = ("literal", "intellij")
MEMBER_PROFILES = ("structure", "summary", "public-api", "full")


@dataclass(frozen=True)
class Options:
    """Einstellungen für einen Lauf.

    Attributes:
        mode: ``literal`` liest Felder, ``extends`` und ``implements``.
            ``intellij`` bildet das Klassendiagramm von IntelliJ IDEA nach, mit
            Abhängigkeiten aus den Methodenrümpfen und ``«create»``.
        member_profile: wie viele Attribute und Methoden in den Knoten stehen
            (``structure``, ``summary``, ``public-api``, ``full``). Gilt nur im
            Modus ``literal``. Der IntelliJ-Modus liest immer alles.
        source_sets: ``auto`` oder ``all``, siehe ``collect_java_files``.
        include_generated: generierte Quelldateien mitlesen.
        exclude_dirs: Muster für Verzeichnisse, die übersprungen werden.
        exclude_files: Muster für Dateinamen, die übersprungen werden.
        external_supertypes: externe Obertypen wie ``JFrame`` als Knoten
            behalten (nur ``literal``).
        method_dependencies: Abhängigkeiten aus Methodensignaturen (nur
            ``literal``).
        javac: zusätzlich den JDK-Compiler fragen (nur ``literal``).
        classpath: JARs oder Verzeichnisse für ``javac``.
        diagram_classes: voll qualifizierte Namen der Klassen im Diagramm (nur
            ``intellij``). Leer heißt: alle Klassen des Projekts.
        ide_jdk: IntelliJ hatte ein JDK eingerichtet (nur ``intellij``).
        ide_same_package: IntelliJ fand Klassen aus demselben Paket ohne
            ``import`` (nur ``intellij``).
    """

    mode: str = "literal"
    member_profile: str = "summary"
    source_sets: str = "auto"
    include_generated: bool = False
    exclude_dirs: tuple[str, ...] = DEFAULT_EXCLUDE_DIRS
    exclude_files: tuple[str, ...] = DEFAULT_EXCLUDE_FILES
    external_supertypes: bool = True
    method_dependencies: bool = False
    javac: bool = False
    classpath: tuple[str, ...] = ()
    diagram_classes: tuple[str, ...] = ()
    ide_jdk: bool = True
    ide_same_package: bool = True

    def check(self) -> None:
        """Widersprüchliche oder unbekannte Einstellungen mit ``ValueError`` melden."""
        if self.mode not in MODES:
            raise ValueError(f"Unbekannter Modus {self.mode!r}, erlaubt: {', '.join(MODES)}")
        if self.member_profile not in MEMBER_PROFILES:
            raise ValueError(f"Unbekanntes member_profile {self.member_profile!r}")
        if self.mode == "literal" and (self.diagram_classes or not self.ide_jdk
                                       or not self.ide_same_package):
            raise ValueError("Klassenauswahl und IDE-Umgebung gehen nur im Modus intellij")
        if self.mode == "intellij" and (self.javac or self.classpath or self.method_dependencies
                                        or not self.external_supertypes):
            raise ValueError("javac, Classpath, Methodenabhängigkeiten und das Weglassen externer "
                             "Obertypen gehen nur im Modus literal")


@dataclass
class Result:
    """Ergebnis eines Laufs."""

    repo: str
    root: Path
    files: list[Path]
    graph: AbstractGraph
    options: Options
    diagnostics: list[Diagnostic] = field(default_factory=list)

    def plantuml(self) -> str:
        return to_plantuml(self.graph)

    def json(self) -> str:
        return graph_to_json(self.graph, indent=2)

    def diagnostics_json(self) -> str:
        return json.dumps([
            {
                "code": d.code,
                "severity": d.severity,
                "message": d.message,
                "source": d.source,
                "reference": d.reference,
                "candidates": d.candidates,
            }
            for d in self.diagnostics
        ], indent=2, ensure_ascii=False) + "\n"


def extract(root: str | Path, options: Options | None = None, repo: str | None = None,
            files: list[Path] | None = None) -> Result:
    """Klassengraph für das Java-Projekt unter ``root`` bauen.

    Args:
        root: Wurzel eines lokalen Repos. Für Git-URLs vorher
            ``javauml.repo.open_repo`` benutzen.
        options: Einstellungen, Standard ist der wörtliche Modus.
        repo: Name im Graphen, Standard ist der Ordnername.
        files: Dateiliste statt der eigenen Auswahl, etwa um einen Benchmark
            mit genau denselben Dateien nachzustellen.

    Returns:
        Ein ``Result`` mit Graph, gelesenen Dateien und Diagnosen.

    Raises:
        ValueError: bei widersprüchlichen Optionen.
        javauml.java.ts_pass.JavaParserUnavailable: wenn tree-sitter fehlt.
    """
    options = options or Options()
    options.check()
    root = Path(root).resolve()
    repo = repo or root.name
    if files is None:
        files = collect_java_files(
            root, options.exclude_dirs, options.exclude_files,
            options.source_sets, options.include_generated,
        )

    if options.mode == "intellij":
        graph = build_intellij_graph(
            files, root, repo,
            IdeEnvironment(jdk=options.ide_jdk, same_package=options.ide_same_package),
            list(options.diagram_classes) or None,
        )
        return Result(repo, root, files, graph, options, list(graph.diagnostics))

    analysis = analyze_java(files, root, options.member_profile)
    compiler_edges = []
    if options.javac:
        from javauml.java.javac_solver import resolve_with_javac
        compiler_edges, compiler_diagnostics = resolve_with_javac(
            files, root, analysis.classes, options.classpath,
        )
        analysis.diagnostics.extend(compiler_diagnostics)
    graph = build_java_graph(
        analysis.classes,
        repo,
        include_external_supertypes=options.external_supertypes,
        include_method_dependencies=options.method_dependencies,
        diagnostics=analysis.diagnostics,
        compiler_edges=compiler_edges,
    )
    return Result(repo, root, files, graph, options, list(graph.diagnostics))
