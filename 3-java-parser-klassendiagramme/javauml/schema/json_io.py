from __future__ import annotations

import json
from typing import Any

from .graph import AbstractGraph, Diagnostic, Edge, EdgeEvidence, Node, Package


def graph_to_dict(graph: AbstractGraph) -> dict[str, Any]:
    return {
        "repo": graph.repo,
        "target_nodes": graph.target_nodes,
        "packages": [{"name": p.name, "parent": p.parent} for p in graph.packages],
        "nodes": [
            {
                "id": n.id,
                "name": n.name,
                "package": n.package,
                "stereotype": n.stereotype,
                "attributes": list(n.attributes),
                "methods": list(n.methods),
                "source_file": n.source_file,
                "source_line": n.source_line,
            }
            for n in graph.nodes
        ],
        "edges": [_edge_to_dict(e) for e in graph.edges],
        "diagnostics": [
            {
                "code": d.code,
                "message": d.message,
                "severity": d.severity,
                "source": d.source,
                "reference": d.reference,
                "candidates": list(d.candidates),
            }
            for d in graph.diagnostics
        ],
    }


def _edge_to_dict(e: Edge) -> dict[str, Any]:
    d: dict[str, Any] = {"source": e.source, "target": e.target, "type": e.type}
    if e.source_card is not None:
        d["source_card"] = e.source_card
    if e.target_card is not None:
        d["target_card"] = e.target_card
    if e.label is not None:
        d["label"] = e.label
    if e.evidence:
        d["evidence"] = [
            {
                "kind": item.kind,
                "member": item.member,
                "declared_type": item.declared_type,
                "file": item.file,
                "line": item.line,
                "resolver": item.resolver,
            }
            for item in e.evidence
        ]
    return d


def dict_to_graph(d: dict[str, Any]) -> AbstractGraph:
    return AbstractGraph(
        repo=str(d["repo"]),
        target_nodes=None if d.get("target_nodes") is None else int(d["target_nodes"]),
        packages=[
            Package(name=p["name"], parent=p.get("parent"))
            for p in d.get("packages", [])
        ],
        nodes=[
            Node(
                id=n["id"],
                name=n["name"],
                package=n["package"],
                stereotype=n.get("stereotype"),
                attributes=list(n.get("attributes", [])),
                methods=list(n.get("methods", [])),
                source_file=n.get("source_file"),
                source_line=n.get("source_line"),
            )
            for n in d.get("nodes", [])
        ],
        edges=[
            Edge(
                source=e["source"], target=e["target"], type=e["type"],
                source_card=e.get("source_card"), target_card=e.get("target_card"),
                label=e.get("label"),
                evidence=[
                    EdgeEvidence(
                        kind=item.get("kind", "source"),
                        member=item.get("member"),
                        declared_type=item.get("declared_type"),
                        file=item.get("file"),
                        line=item.get("line"),
                        resolver=item.get("resolver", "source"),
                    )
                    for item in e.get("evidence", [])
                    if isinstance(item, dict)
                ],
            )
            for e in d.get("edges", [])
        ],
        diagnostics=[
            Diagnostic(
                code=item.get("code", "unknown"),
                message=item.get("message", ""),
                severity=item.get("severity", "warning"),
                source=item.get("source"),
                reference=item.get("reference"),
                candidates=list(item.get("candidates", [])),
            )
            for item in d.get("diagnostics", [])
            if isinstance(item, dict)
        ],
    )


def graph_to_json(graph: AbstractGraph, **kwargs: Any) -> str:
    return json.dumps(graph_to_dict(graph), **kwargs)


def json_to_graph(text: str) -> AbstractGraph:
    return dict_to_graph(json.loads(text))
