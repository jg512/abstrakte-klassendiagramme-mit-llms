from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.cleanup.cleanup import CleanupPass, _parse_graph
from src.llm.client import LLMResponse
from src.schema.graph import AbstractGraph, Edge, Node, Package

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _make_llm_response(obj: Any) -> LLMResponse:
    return LLMResponse(
        text=json.dumps(obj) if obj is not None else None,
        tool_calls=[],
        tokens_in=10,
        tokens_out=10,
        elapsed_ms=1,
    )


def test_cleanup_basic():
    client = MagicMock()
    # Liefert gültiges Graph-JSON
    client.chat_json.return_value = _make_llm_response({
        "repo": "test-repo",
        "target_nodes": 1,
        "packages": [{"name": "pkg", "parent": None}],
        "nodes": [
            {
                "id": "pkg.A",
                "name": "A",
                "package": "pkg",
                "stereotype": None,
                "attributes": [],
                "methods": [],
            }
        ],
        "edges": [],
    })

    cp = CleanupPass(client, prompts_dir=PROMPTS_DIR)
    graph = AbstractGraph("test-repo", 1, [], [], [])
    result = cp.run(graph, target_nodes=1)

    assert len(result.nodes) == 1
    assert result.nodes[0].id == "pkg.A"


def test_cleanup_skips_when_prompt_too_large():
    client = MagicMock()
    cp = CleanupPass(client, prompts_dir=PROMPTS_DIR, context_budget=0)
    original = AbstractGraph("r", 5, [], [Node("A", "A", "")], [])
    result = cp.run(original, target_nodes=5)
    assert result is original
    client.chat_json.assert_not_called()


def test_cleanup_llm_failure_returns_original():
    client = MagicMock()
    client.chat_json.return_value = _make_llm_response(None)

    cp = CleanupPass(client, prompts_dir=PROMPTS_DIR)
    original = AbstractGraph("test-repo", 1, [], [Node("A", "A", "")], [])
    result = cp.run(original, target_nodes=1)

    assert result == original


def test_cleanup_parse_error_returns_original():
    client = MagicMock()
    # Liefert etwas, das kein dict ist
    client.chat_json.return_value = _make_llm_response(["not", "a", "dict"])

    cp = CleanupPass(client, prompts_dir=PROMPTS_DIR)
    original = AbstractGraph("test-repo", 1, [], [Node("A", "A", "")], [])
    result = cp.run(original, target_nodes=1)

    assert result == original


def test_cleanup_validator_repairs_output():
    client = MagicMock()
    client.chat_json.return_value = _make_llm_response({
        "repo": "test-repo",
        "target_nodes": 1,
        "nodes": [
            {
                "id": "A",
                "name": "A",
                "package": "pkg",
                "attributes": ["a1", "a2", "a3", "a4", "a5", "a6"],
            }
        ],
    })

    cp = CleanupPass(client, prompts_dir=PROMPTS_DIR)
    graph = AbstractGraph("test-repo", 1, [], [], [])
    result = cp.run(graph, target_nodes=1)

    assert len(result.nodes) == 1
    assert len(result.nodes[0].attributes) == 6  # Member werden nicht gekürzt


def test_cleanup_target_nodes_injection():
    client = MagicMock()
    client.chat_json.return_value = _make_llm_response({"nodes": []})

    cp = CleanupPass(client, prompts_dir=PROMPTS_DIR)
    graph = AbstractGraph("test-repo", 5, [], [], [])
    cp.run(graph, target_nodes=20)

    # Prüfen, dass target_nodes=20 in der User-Nachricht stand
    args, _ = client.chat_json.call_args
    user_msg = args[0][1]["content"]
    assert "Target node count: 20" in user_msg


def test_cleanup_strips_invalid_edges_during_parse():
    client = MagicMock()
    client.chat_json.return_value = _make_llm_response({
        "nodes": [{"id": "A", "name": "A", "package": ""}],
        "edges": [
            {"source": "A", "target": "B"},  # B gibt es nicht
        ],
    })

    cp = CleanupPass(client, prompts_dir=PROMPTS_DIR)
    graph = AbstractGraph("r", 1, [], [], [])
    result = cp.run(graph, target_nodes=1)
    assert result.edges == []


# Hilfsfunktion _parse_graph

def test_parse_graph_basic():
    obj = {
        "nodes": [{"id": "a.B", "name": "B", "package": "a"}],
        "edges": [],
        "packages": [{"name": "a", "parent": None}],
    }
    g = _parse_graph(obj, repo="r", target_nodes=1)
    assert len(g.nodes) == 1
    assert g.nodes[0].id == "a.B"
    assert g.repo == "r"
    assert g.target_nodes == 1


def test_parse_graph_skips_bad_nodes():
    obj = {
        "nodes": [
            {"id": "a.Good", "name": "Good", "package": "a"},
            "not a dict",
            {"name": "NoId", "package": "a"},  # id fehlt
        ],
        "edges": [],
    }
    g = _parse_graph(obj, repo="r", target_nodes=1)
    assert len(g.nodes) == 1
    assert g.nodes[0].id == "a.Good"


def test_parse_graph_skips_bad_edges():
    obj = {
        "nodes": [
            {"id": "a.A", "name": "A", "package": "a"},
            {"id": "a.B", "name": "B", "package": "a"},
        ],
        "edges": [
            {"source": "a.A", "target": "a.B", "type": "dependency"},
            {"source": "a.A"},  # target fehlt
            "not a dict",
        ],
    }
    g = _parse_graph(obj, repo="r", target_nodes=2)
    assert len(g.edges) == 1


def test_parse_graph_handles_missing_packages_key():
    obj = {"nodes": [{"id": "x.Y", "name": "Y", "package": "x"}], "edges": []}
    g = _parse_graph(obj, repo="r", target_nodes=1)
    assert g.packages == []


def test_parse_graph_defaults_edge_type_to_dependency():
    obj = {
        "nodes": [
            {"id": "a.A", "name": "A", "package": "a"},
            {"id": "a.B", "name": "B", "package": "a"},
        ],
        "edges": [{"source": "a.A", "target": "a.B"}],  # kein type
    }
    g = _parse_graph(obj, repo="r", target_nodes=2)
    assert g.edges[0].type == "dependency"
