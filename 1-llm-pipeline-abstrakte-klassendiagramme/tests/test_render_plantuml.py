from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.tools.render_plantuml import render


def _write_graph(path: Path) -> None:
    data = {
        "repo": "test",
        "target_nodes": 2,
        "packages": [{"name": "test"}],
        "nodes": [
            {"id": "test.Foo", "name": "Foo", "package": "test",
             "stereotype": None, "attributes": [], "methods": []},
        ],
        "edges": [],
    }
    path.write_text(json.dumps(data), encoding="utf-8")


def test_render_creates_puml(tmp_path):
    graph_path = tmp_path / "graph.json"
    _write_graph(graph_path)
    dest = render(graph_path)
    assert dest.exists()
    assert dest.name == "diagram.puml"
    assert "Foo" in dest.read_text()


def test_render_custom_output_path(tmp_path):
    graph_path = tmp_path / "graph.json"
    _write_graph(graph_path)
    out = tmp_path / "out.puml"
    dest = render(graph_path, out)
    assert dest == out
    assert out.exists()


def test_render_plantuml_contains_startuml(tmp_path):
    graph_path = tmp_path / "graph.json"
    _write_graph(graph_path)
    dest = render(graph_path)
    assert "@startuml" in dest.read_text()
