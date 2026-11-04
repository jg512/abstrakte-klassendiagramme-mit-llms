from __future__ import annotations

import logging

from .graph import AbstractGraph, Edge, Node, Package

logger = logging.getLogger(__name__)

VALID_STEREOTYPES: frozenset[str] = frozenset(
    {"abstract", "interface", "dataclass", "enum", "exception"}
)
VALID_EDGE_TYPES: frozenset[str] = frozenset(
    {"inheritance", "realization", "composition", "aggregation", "association", "dependency", "nesting"}
)


def _ensure_package_chain(
    name: str,
    packages: list[Package],
    pkg_names: set[str],
) -> None:
    if name in pkg_names:
        return
    parts = name.rsplit(".", 1)
    if len(parts) == 2:
        parent_name = parts[0]
        _ensure_package_chain(parent_name, packages, pkg_names)
        packages.append(Package(name=name, parent=parent_name))
    else:
        packages.append(Package(name=name, parent=None))
    pkg_names.add(name)


def validate(
    graph: AbstractGraph,
    target_nodes: int | None = None,
    node_tolerance: float = 0.2,
    max_nodes: int | None = None,
) -> tuple[AbstractGraph, list[str]]:
    """Graphen reparieren und (reparierter_graph, warnungen) zurückgeben. Wirft nie."""
    warnings: list[str] = []

    # Doppelte Knoten entfernen (der erste bleibt)
    seen_ids: set[str] = set()
    deduped: list[Node] = []
    for node in graph.nodes:
        if node.id in seen_ids:
            msg = f"Duplicate node id {node.id!r} — keeping first occurrence"
            warnings.append(msg)
            logger.warning(msg)
        else:
            seen_ids.add(node.id)
            deduped.append(node)

    # Jeden Knoten reparieren
    repaired_nodes: list[Node] = []
    for node in deduped:
        attrs = list(node.attributes)
        methods = list(node.methods)
        stereotype = node.stereotype

        if stereotype is not None and stereotype not in VALID_STEREOTYPES:
            msg = f"Invalid stereotype {stereotype!r} on node {node.id!r} — set to null"
            warnings.append(msg)
            logger.warning(msg)
            stereotype = None

        repaired_nodes.append(
            Node(
                id=node.id,
                name=node.name,
                package=node.package,
                stereotype=stereotype,
                attributes=attrs,
                methods=methods,
                source_file=node.source_file,
                source_line=node.source_line,
            )
        )

    # Sicherstellen, dass alle Pakete der Knoten existieren
    packages: list[Package] = list(graph.packages)
    pkg_names: set[str] = {p.name for p in packages}

    for node in repaired_nodes:
        if node.package not in pkg_names:
            logger.info("Auto-creating package chain for %r (node %r)", node.package, node.id)
            _ensure_package_chain(node.package, packages, pkg_names)

    # Kanten prüfen
    _EDGE_STRENGTH = {
        "inheritance": 6, "realization": 5, "composition": 4,
        "aggregation": 3, "association": 2, "dependency": 1, "nesting": 0,
    }
    node_ids: set[str] = {n.id for n in repaired_nodes}
    raw_edges: list[Edge] = []

    for edge in graph.edges:
        if edge.type not in VALID_EDGE_TYPES:
            msg = f"Invalid edge type {edge.type!r} ({edge.source!r} → {edge.target!r}) — dropped"
            warnings.append(msg)
            logger.warning(msg)
            continue
        if edge.source not in node_ids:
            msg = f"Edge source {edge.source!r} not in nodes — dropped"
            warnings.append(msg)
            logger.warning(msg)
            continue
        if edge.target not in node_ids:
            msg = f"Edge target {edge.target!r} not in nodes — dropped"
            warnings.append(msg)
            logger.warning(msg)
            continue
        raw_edges.append(Edge(
            source=edge.source, target=edge.target, type=edge.type,
            source_card=edge.source_card, target_card=edge.target_card,
            label=edge.label, evidence=list(edge.evidence),
        ))

    # Doppelte (source, target)-Paare entfernen, der stärkste Typ bleibt
    seen_edges: dict[tuple[str, str], Edge] = {}
    for edge in raw_edges:
        key = (edge.source, edge.target)
        if key not in seen_edges or (
            _EDGE_STRENGTH.get(edge.type, 0) > _EDGE_STRENGTH.get(seen_edges[key].type, 0)
        ):
            if key in seen_edges:
                msg = f"Duplicate edge {edge.source!r}→{edge.target!r} — keeping strongest type"
                warnings.append(msg)
                logger.warning(msg)
            seen_edges[key] = edge
        elif edge.type == seen_edges[key].type:
            existing = seen_edges[key]
            known = {
                (e.kind, e.member, e.declared_type, e.file, e.line, e.resolver)
                for e in existing.evidence
            }
            existing.evidence.extend(
                e for e in edge.evidence
                if (e.kind, e.member, e.declared_type, e.file, e.line, e.resolver) not in known
            )
    valid_edges = list(seen_edges.values())

    # Knotenzahl prüfen (nur Warnung)
    if target_nodes is not None:
        n = len(repaired_nodes)
        lo = int(target_nodes * (1 - node_tolerance))
        hi = int(target_nodes * (1 + node_tolerance))
        if not (lo <= n <= hi):
            msg = (
                f"Node count {n} outside target range [{lo}, {hi}] "
                f"(target={target_nodes}, tolerance={node_tolerance:.0%})"
            )
            warnings.append(msg)
            logger.warning(msg)

    if max_nodes is not None and len(repaired_nodes) > max_nodes:
        msg = f"Node count {len(repaired_nodes)} exceeds hard cap {max_nodes}"
        warnings.append(msg)
        logger.warning(msg)

    repaired = AbstractGraph(
        repo=graph.repo,
        target_nodes=graph.target_nodes,
        packages=packages,
        nodes=repaired_nodes,
        edges=valid_edges,
        diagnostics=list(graph.diagnostics),
    )
    return repaired, warnings
