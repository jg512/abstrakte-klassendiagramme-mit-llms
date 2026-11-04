"""Graph-Modell, JSON und PlantUML. Das JSON hat dasselbe Format wie javagraph.json in Ordner 1."""
from __future__ import annotations

from .graph import AbstractGraph, Diagnostic, Edge, EdgeEvidence, Node, Package
from .json_io import dict_to_graph, graph_to_dict, graph_to_json, json_to_graph
from .plantuml import check_plantuml, to_plantuml

__all__ = [
    "AbstractGraph",
    "Diagnostic",
    "Edge",
    "EdgeEvidence",
    "Node",
    "Package",
    "check_plantuml",
    "dict_to_graph",
    "graph_to_dict",
    "graph_to_json",
    "json_to_graph",
    "to_plantuml",
]
