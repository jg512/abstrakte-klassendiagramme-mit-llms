"""Die Tools, die alle Driver-Varianten gemeinsam benutzen.

Jede Variante hat drei Tools: inspect_class, apply_edits und emit_diagram.
apply_edits ändert den Graphen in einem Aufruf: erst wird entfernt, dann
kommen Knoten dazu, dann Kanten. Früher waren das getrennte Tools. Dann ging
es oft vor, dass das Budget zwischen dem Anlegen der Knoten und dem Anlegen
ihrer Kanten aufgebraucht war, und dem Diagramm fehlten Kanten. Mit einem
einzigen Aufruf kann das nicht mehr passieren.

Die Peek-Varianten bekommen zusätzlich read_file und search_code und dürfen
damit den Quelltext lesen. Das ist der einzige Unterschied bei den Tools.

Die Tools werden in build_tools als innere Funktionen angelegt und ändern
den Arbeitsgraphen und das Flag finished direkt.
"""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from src.llm.tools import Tool, make_tool
from src.parsing.code_graph import CodeGraph
from src.schema.graph import AbstractGraph, Edge, Node
from src.schema.json_io import graph_to_dict

if TYPE_CHECKING:
    from src.runs.research import ResearchWriter

log = logging.getLogger(__name__)

_MAX_REPORTED_ERRORS = 10


def build_tools(
    code_graph: CodeGraph,
    graph: AbstractGraph,
    finished: list[bool],
    *,
    peek: bool,
    read_file_max_lines: int = 200,
    module_scope: set[str] | None = None,
    phase: str = "driver",
    research: ResearchWriter | None = None,
    target_nodes: int | None = None,
    node_tolerance: int | None = None,
    max_nodes: int | None = None,
) -> list[Tool]:
    class_index = {c.qualified_name: c for c in code_graph.classes}

    def _graph_now() -> str:
        """Aktuelle Größe des Graphen, die an jedes Ergebnis von apply_edits angehängt wird.

        Ohne diese Angabe verlieren die Modelle aus dem Blick, wie groß der Graph
        im Vergleich zum Ziel ist, und liegen am Ende darüber oder darunter.
        """
        s = f"{len(graph.nodes)} nodes, {len(graph.edges)} edges"
        if target_nodes is not None:
            tol = f"±{node_tolerance}" if node_tolerance is not None else ""
            s += f" (target {target_nodes}{tol})"
        elif max_nodes is not None:
            s += f" (open size, cap {max_nodes})"
        return s

    def _draft_gate() -> dict | None:
        """Sperrt die Peek-Tools, solange der Graph leer ist.

        Die Peek-Tools sollen einen vorhandenen Entwurf verfeinern. Zum Recherchieren
        sind sie nicht gedacht. Solange der Graph leer ist, liefern sie deshalb nur
        diese Absage. Eine Regel im Prompt ("erst einen Entwurf machen") hat dafür
        nicht zuverlässig gereicht.
        """
        if not graph.nodes:
            return {
                "error": "unavailable while the graph is empty — build a draft "
                         "first (apply_edits with nodes and edges), then read "
                         "to verify it"
            }
        return None

    # Die Docstrings der Tool-Funktionen (inspect_class, read_file, search_code,
    # apply_edits, emit_diagram) gehen über make_tool als Tool-Beschreibung an das
    # LLM. Sie gehören wie die Prompts zum Experiment und bleiben englisch.
    def inspect_class(qualified_name: str) -> dict:
        """Return parser-extracted summary for a class by its qualified name."""
        cls = class_index.get(qualified_name)
        if cls is None:
            # sonst über den unqualifizierten Namen suchen
            candidates = [c for c in code_graph.classes if c.name == qualified_name]
            if len(candidates) == 1:
                cls = candidates[0]
            elif candidates:
                return {
                    "error": f"Ambiguous name {qualified_name!r}",
                    "candidates": [c.qualified_name for c in candidates],
                }
            else:
                return {"error": f"Class not found: {qualified_name!r}"}
        info = {
            "qualified_name": cls.qualified_name,
            "name": cls.name,
            "module": cls.module,
            "file": str(cls.file.relative_to(code_graph.root)),
            "line_start": cls.line_start,
            "line_end": cls.line_end,
            "bases": cls.bases,
            "decorators": cls.decorators,
            "attributes": cls.attributes[:10],
            "methods": cls.methods[:10],
        }
        if module_scope is not None:
            info["in_scope"] = cls.module in module_scope
        return info

    def read_file(path: str, start_line: int = 0, end_line: int = 0) -> dict:
        """Read a file's contents. start_line/end_line are 1-based; 0 means use default."""
        gate = _draft_gate()
        if gate is not None:
            return gate
        target = code_graph.root / path
        if not target.exists():
            return {"error": f"File not found: {path}"}
        if not target.is_file():
            return {"error": f"{path} is not a file"}
        try:
            lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            return {"error": str(exc)}

        total = len(lines)
        lo = max(0, (start_line - 1) if start_line > 0 else 0)
        hi = min(total, end_line if end_line > 0 else total)

        # höchstens read_file_max_lines Zeilen zurückgeben (<= 0 heißt unbegrenzt)
        if read_file_max_lines > 0 and hi - lo > read_file_max_lines:
            hi = lo + read_file_max_lines

        chunk = lines[lo:hi]
        return {
            "path": path,
            "start_line": lo + 1,
            "end_line": lo + len(chunk),
            "total_lines": total,
            "content": "\n".join(chunk),
            "truncated": hi < total,
        }

    def search_code(regex: str) -> dict:
        """Search all source files for a regex. Returns up to 40 matches with file:line:text."""
        gate = _draft_gate()
        if gate is not None:
            return gate
        try:
            pattern = re.compile(regex)
        except re.error as exc:
            return {"error": f"Invalid regex: {exc}"}

        matches = []
        for src_file in code_graph.source_files:
            try:
                for i, line in enumerate(
                    src_file.read_text(encoding="utf-8", errors="replace").splitlines(), 1
                ):
                    if pattern.search(line):
                        rel = src_file.relative_to(code_graph.root)
                        matches.append({"file": str(rel), "line": i, "text": line.strip()})
                        if len(matches) >= 40:
                            return {"matches": matches, "truncated": True}
            except OSError:
                continue
        return {"matches": matches, "truncated": False}

    def apply_edits(
        remove_node_ids: list | None = None,
        add_nodes: list | None = None,
        add_edges: list | None = None,
    ) -> dict:
        """Apply one atomic patch to the working graph: removals, then node
        adds, then edge adds. Results are itemized per section."""
        remove_node_ids = remove_node_ids or []
        add_nodes = add_nodes or []
        add_edges = add_edges or []
        if not (remove_node_ids or add_nodes or add_edges):
            return {
                "ok": False,
                "error": "empty patch — provide remove_node_ids, add_nodes "
                         "and/or add_edges",
            }
        errors: list[dict] = []

        # 1. Entfernen (ihre Kanten gehen mit)
        id_set = {i for i in remove_node_ids if isinstance(i, str)}
        present = {n.id for n in graph.nodes}
        removed = present & id_set
        graph.nodes = [n for n in graph.nodes if n.id not in id_set]
        graph.edges = [e for e in graph.edges if e.source not in id_set and e.target not in id_set]
        for missing_id in sorted(id_set - removed)[:_MAX_REPORTED_ERRORS]:
            errors.append({"remove": missing_id, "error": "node not found"})

        # 2. Knoten hinzufügen
        nodes_added = 0
        for i, node in enumerate(add_nodes):
            if not isinstance(node, dict):
                errors.append({"add_node_index": i, "error": "node must be a JSON object"})
                continue
            node_id = node.get("id", "")
            if not node_id:
                errors.append({"add_node_index": i, "error": "node.id is required"})
                continue
            if any(n.id == node_id for n in graph.nodes):
                errors.append({"id": node_id, "error": "node already exists"})
                continue
            graph.nodes.append(Node(
                id=node_id,
                name=node.get("name") or node_id.split(".")[-1],
                package=node.get("package") or "",
                stereotype=node.get("stereotype"),
                attributes=list(node.get("attributes") or []),
                methods=list(node.get("methods") or []),
            ))
            nodes_added += 1

        # 3. Kanten hinzufügen (Endpunkte dürfen Knoten aus Schritt 2 sein)
        valid_types = {
            "inheritance", "realization", "composition",
            "aggregation", "association", "dependency",
        }
        edges_added = 0
        for i, edge in enumerate(add_edges):
            if not isinstance(edge, dict):
                errors.append({"add_edge_index": i, "error": "edge must be a JSON object"})
                continue
            src = edge.get("source", "")
            tgt = edge.get("target", "")
            etype = edge.get("type", "dependency")
            if not src or not tgt:
                errors.append({
                    "add_edge_index": i,
                    "error": "edge.source and edge.target are required",
                })
                continue
            if etype not in valid_types:
                errors.append({
                    "add_edge_index": i,
                    "error": f"edge.type must be one of {sorted(valid_types)}",
                })
                continue
            node_ids = {n.id for n in graph.nodes}
            missing = [x for x in (src, tgt) if x not in node_ids]
            if missing:
                errors.append({
                    "add_edge_index": i,
                    "error": f"edge endpoints not in graph: {missing} — include "
                             "them in add_nodes of the same patch",
                })
                continue
            src_card = edge.get("source_card")
            tgt_card = edge.get("target_card")
            graph.edges.append(Edge(
                source=src, target=tgt, type=etype,
                source_card=str(src_card) if src_card else None,
                target_card=str(tgt_card) if tgt_card else None,
            ))
            edges_added += 1

        applied = bool(removed) or nodes_added > 0 or edges_added > 0
        result = {
            "ok": applied,
            "removed": len(removed),
            "nodes_added": nodes_added,
            "edges_added": edges_added,
            "graph_now": _graph_now(),
        }
        if errors:
            result["errors"] = errors[:_MAX_REPORTED_ERRORS]
        return result

    def emit_diagram(reason: str) -> dict:
        """Emit the current diagram immediately and end the run. Call when satisfied with the graph."""
        if research:
            research.save_snapshot(f"{phase}_emit_diagram.json", graph, also_puml=True)
        finished[0] = True
        log.info("[%s] emit_diagram: %s", phase, reason)
        return {"ok": True, "final_node_count": len(graph.nodes)}

    tools = [
        make_tool(inspect_class),
    ]
    if peek:
        tools += [
            make_tool(read_file),
            make_tool(search_code),
        ]
    tools += [
        make_tool(
            apply_edits,
            parameters={
                "type": "object",
                "properties": {
                    "remove_node_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Node ids to remove (their edges go with them). "
                                       "Applied first.",
                    },
                    "add_nodes": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Nodes to add. Each needs an id (qualified name); "
                                       "name, package, stereotype, attributes, methods "
                                       "are optional. Applied second.",
                    },
                    "add_edges": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Relations to add. Each needs source, target "
                                       "(node ids present after this patch's adds) and "
                                       "type (inheritance | realization | composition | "
                                       "aggregation | association | dependency); "
                                       "source_card/target_card multiplicities "
                                       "(e.g. \"1\", \"*\", \"0..1\") are optional. "
                                       "Applied last.",
                    },
                },
                "required": [],
            },
        ),
        make_tool(emit_diagram),
    ]
    return tools
