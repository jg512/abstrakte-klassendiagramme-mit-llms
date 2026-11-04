from __future__ import annotations

import logging
from collections import defaultdict

from javauml.model import ClassInfo
from javauml.java.resolution import JavaTypeResolver
from javauml.schema.graph import AbstractGraph, Diagnostic, Edge, EdgeEvidence, Node, Package

logger = logging.getLogger(__name__)

# Paket für Obertypen, die das Repo nicht selbst deklariert (JDK, Swing,
# Spring, ...). Es hat einen eigenen Namensraum, damit eine erfundene ID nie mit
# einer echten zusammenfällt. Repo-relative IDs beginnen nie mit diesem Teil.
EXTERNAL_PACKAGE = "external"

# ClassInfo.kind benutzt Java-Begriffe, das Schema hat eine eigene feste Menge
# (siehe VALID_STEREOTYPES in src/schema/validator.py der Pipeline in Ordner 1).
# Was nicht zugeordnet werden kann,
# wird None, statt vom Validator mit einer Warnung verworfen zu werden.
_STEREOTYPE_MAP = {
    "interface": "interface",
    "enum": "enum",
    "abstract": "abstract",
    "record": "dataclass",      # unveränderlicher Datenträger, gleiche Rolle
    "annotation": "interface",  # ein Annotationstyp ist in Java ein Interface
}


def build_java_graph(
    classes: list[ClassInfo],
    repo: str,
    include_external_supertypes: bool = True,
    include_method_dependencies: bool = False,
    diagnostics: list[Diagnostic] | None = None,
    compiler_edges: list[Edge] | None = None,
) -> AbstractGraph:
    """Den vollen wörtlichen Klassengraphen bauen.

    Der Graph bleibt wörtlich: jeder deklarierte Typ, jede Beziehung, die sich
    auf einen anderen deklarierten Typ auflösen lässt. Eine Auswahl der
    wichtigen Klassen trifft diese Funktion nicht. In der LLM-Pipeline (Ordner 1)
    ist das der Startgraph, aus dem das Modell auswählt.

    Externe Typen werden unterschiedlich behandelt:

    * Obertypen bleiben als `<<external>>`-Knoten erhalten. Erst `Hauptfenster
      extends JFrame` macht die Klasse zu einem Swing-Fenster, und
      `KundenListe implements ListModel` macht sie zu einem Modell statt zu einer
      Collection. Weil `plantuml-generator` diese Kanten wegwirft, geht dort der
      ganze Aufbau einer Swing- oder Spring-Anwendung verloren.
    * Externe Ziele von Assoziationen fallen weg. Ein Feld vom Typ `String`,
      `Timer` oder `JButton` ist nebensächliche Infrastruktur. Behielte man sie,
      käme für fast jedes Feld ein Bibliotheksknoten dazu, und die Architektur
      ginge darin unter.
    """
    resolver = JavaTypeResolver(classes)
    declared = {cls.qualified_name for cls in classes}

    nodes = [
        Node(
            id=cls.qualified_name,
            name=cls.name,
            package=cls.module,
            stereotype=_STEREOTYPE_MAP.get(cls.kind or ""),
            attributes=list(cls.attributes),
            methods=list(cls.methods),
            source_file=cls.source_file or str(cls.file),
            source_line=cls.line_start,
        )
        for cls in classes
    ]

    edges: list[Edge] = []
    # Der Rollenname gehört mit zur Identität einer UML-Assoziation. Eine Klasse
    # kann durchaus zwei Felder mit demselben Ziel haben, mit anderen
    # Kardinalitäten oder anderem Besitz (zum Beispiel ``primary`` und ``history``).
    seen: dict[tuple[str, str, str, str | None], Edge] = {}
    external: dict[str, str] = {}   # ID -> Kurzname

    def add(source: str, target: str | None, type_: str,
            target_card: str | None = None, label: str | None = None,
            evidence: EdgeEvidence | None = None) -> None:
        # Rekursive Felder und Singleton-Instanzen sind in UML erlaubte
        # Selbstassoziationen. Nur ein Obertyp, der auf sich selbst zeigt, ist
        # ungültiges Java.
        if target is None or (target == source and type_ in {"inheritance", "realization"}):
            return
        key = (source, target, type_, label)
        if key in seen:
            if evidence is not None:
                known = {
                    (e.kind, e.member, e.declared_type, e.file, e.line, e.resolver)
                    for e in seen[key].evidence
                }
                signature = (
                    evidence.kind, evidence.member, evidence.declared_type,
                    evidence.file, evidence.line, evidence.resolver,
                )
                if signature not in known:
                    seen[key].evidence.append(evidence)
            if label and not seen[key].label:
                seen[key].label = label
            return
        edge = Edge(
            source=source, target=target, type=type_, target_card=target_card,
            label=label, evidence=[evidence] if evidence is not None else [],
        )
        seen[key] = edge
        edges.append(edge)

    def supertype(source: ClassInfo, name: str, type_: str) -> None:
        resolved = resolver.resolve(name, source)
        if resolved is None:
            if (source.qualified_name, name) in resolver.ambiguous:
                return
            if not include_external_supertypes:
                return
            # Die ID behält die volle Qualifizierung, damit zwei verschiedene externe
            # Typen nie zusammenfallen. Das Label zeigt den Kurznamen, sonst liest
            # sich das Diagramm schlecht.
            resolved = f"{EXTERNAL_PACKAGE}.{resolver.external_name(name, source)}"
            external[resolved] = name.rsplit(".", 1)[-1]
        add(
            source.qualified_name, resolved, type_,
            evidence=EdgeEvidence(
                kind="extends" if type_ == "inheritance" else "implements",
                declared_type=name,
                file=source.source_file or str(source.file),
                line=source.line_start,
            ),
        )

    for cls in classes:
        for base in cls.bases:
            supertype(cls, base, "inheritance")
        for iface in cls.interfaces:
            supertype(cls, iface, "realization")
        for ref in cls.field_refs:
            target = resolver.resolve(ref.type_name, cls)
            if target is None or target not in declared:
                continue    # externe Assoziation, siehe Docstring
            add(
                cls.qualified_name,
                target,
                ref.relation_type or ("aggregation" if ref.many else "association"),
                target_card=ref.target_card or ("0..*" if ref.many else None),
                label=ref.field_name,
                evidence=EdgeEvidence(
                    kind="field", member=ref.field_name,
                    declared_type=ref.declared_type or ref.type_name,
                    file=cls.source_file or str(cls.file), line=ref.line,
                ),
            )
        if include_method_dependencies:
            for ref in cls.method_refs:
                target = resolver.resolve(ref.type_name, cls)
                if target is None or target not in declared or target == cls.qualified_name:
                    continue
                add(
                    cls.qualified_name, target, "dependency", label=ref.method_name,
                    evidence=EdgeEvidence(
                        kind="method", member=ref.method_name,
                        declared_type=ref.declared_type,
                        file=cls.source_file or str(cls.file), line=ref.line,
                    ),
                )

    # javac stuft ein Feld, das sein Ziel besitzt, unter Umständen nur als
    # einfache Assoziation ein. Der Compiler löst Symbole auf und weiß nichts über
    # Besitz im Sinne von UML. Deshalb wird zuerst über die Rolle eine schon
    # vorhandene Beziehung aus dem Quelltext gesucht. Die Angaben des Compilers
    # ergänzen diese Beziehung, schwächen aber nie ab, was der Quelltext über sie sagt.
    for edge in compiler_edges or []:
        if edge.source in declared and edge.target in declared:
            for item in edge.evidence:
                item.resolver = "javac"
            existing = next((candidate for candidate in edges if (
                candidate.source == edge.source
                and candidate.target == edge.target
                and candidate.label == edge.label
            )), None)
            if existing is not None:
                known = {
                    (e.kind, e.member, e.declared_type, e.file, e.line, e.resolver)
                    for e in existing.evidence
                }
                existing.evidence.extend(
                    item for item in edge.evidence
                    if (item.kind, item.member, item.declared_type,
                        item.file, item.line, item.resolver) not in known
                )
                continue
            add(
                edge.source, edge.target, edge.type,
                target_card=edge.target_card, label=edge.label,
                evidence=edge.evidence[0] if edge.evidence else EdgeEvidence(kind="compiler", resolver="javac"),
            )

    for node_id, name in sorted(external.items()):
        nodes.append(Node(id=node_id, name=name, package=EXTERNAL_PACKAGE))

    modules = {cls.module for cls in classes}
    if external:
        modules.add(EXTERNAL_PACKAGE)

    graph_diagnostics = list(diagnostics or [])
    by_simple: dict[str, list[str]] = defaultdict(list)
    for cls in classes:
        by_simple[cls.name].append(cls.source_qualified_name or cls.qualified_name)
    for source, reference in sorted(resolver.ambiguous):
        graph_diagnostics.append(Diagnostic(
            code="ambiguous-type",
            message=f"Ambiguous Java type {reference!r}; relationship omitted",
            source=source,
            reference=reference,
            candidates=sorted(by_simple.get(reference.rsplit('.', 1)[-1], [])),
        ))

    graph = AbstractGraph(
        repo=repo,
        target_nodes=None,
        packages=_packages(modules),
        nodes=nodes,
        edges=edges,
        diagnostics=graph_diagnostics,
    )
    logger.debug(
        "Java static graph: %d nodes (%d external), %d edges",
        len(nodes), len(external), len(edges),
    )
    return graph


def _packages(modules: set[str]) -> list[Package]:
    """Alle Pakete samt ihren Vorfahren, jeweils mit Verweis auf das Elternpaket."""
    names: set[str] = set()
    for module in modules:
        if not module:
            continue
        parts = module.split(".")
        for i in range(1, len(parts) + 1):
            names.add(".".join(parts[:i]))
    return [
        Package(name=n, parent=".".join(n.split(".")[:-1]) or None)
        for n in sorted(names)
    ]
