from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.llm.client import LLMResponse
from src.llm.tools import ToolCall
from src.methods.driver import Driver
from src.methods.toolbox import build_tools
from src.methods.variants import resolve
from src.parsing.code_graph import CodeGraph
from src.schema.graph import AbstractGraph, Edge, Node

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


# Hilfsfunktionen

def _make_tool_response(*calls: tuple[str, dict]) -> LLMResponse:
    tcs = [ToolCall(id=f"tc{i}", name=name, arguments=args) for i, (name, args) in enumerate(calls)]
    return LLMResponse(text="", tool_calls=tcs, tokens_in=10, tokens_out=10, elapsed_ms=1)


def _empty_response() -> LLMResponse:
    return LLMResponse(text="done", tool_calls=[], tokens_in=5, tokens_out=5, elapsed_ms=1)


def _make_code_graph(classes=None, pyreverse_graph=None) -> CodeGraph:
    return CodeGraph(
        repo="testrepo",
        root=Path("/fake/repo"),
        source_files=[],
        classes=classes or [],
        functions=[],
        module_imports={},
        package_imports={},
        inheritance={},
        static_graph=pyreverse_graph,
    )


def _pyreverse_graph(n: int = 3) -> AbstractGraph:
    g = AbstractGraph(repo="testrepo", target_nodes=n)
    for i in range(n):
        g.nodes.append(Node(id=f"pkg.C{i}", name=f"C{i}", package="pkg"))
    g.edges.append(Edge(source="pkg.C0", target="pkg.C1", type="dependency"))
    return g


def _driver(client, variant_name: str, **kwargs) -> Driver:
    return Driver(client, resolve(variant_name), prompts_dir=PROMPTS_DIR, **kwargs)


def _sent_tool_names(client) -> set[str]:
    _, tools = client.chat_tools.call_args[0]
    return {t.name for t in tools}


# Grundlegende Tool-Schleife (für alle Varianten gleich)

def test_tool_loop_add_then_emit():
    cg = _make_code_graph()
    client = MagicMock()
    client.chat_tools.side_effect = [
        _make_tool_response(("inspect_class", {"qualified_name": "pkg.A"})),
        _make_tool_response(
            ("apply_edits", {"add_nodes": [{"id": "pkg.A", "name": "A", "package": "pkg"}]})
        ),
        _make_tool_response(("emit_diagram", {"reason": "done"})),
    ]
    result = _driver(client, "overview-peek").run(cg, target_nodes=1)
    assert {n.id for n in result.nodes} == {"pkg.A"}
    assert client.chat_tools.call_count == 3


def test_apply_edits_nodes_and_edges_one_patch():
    cg = _make_code_graph()
    client = MagicMock()
    client.chat_tools.side_effect = [
        _make_tool_response(("apply_edits", {
            "add_nodes": [
                {"id": "pkg.A", "name": "A", "package": "pkg"},
                {"id": "pkg.B", "name": "B", "package": "pkg"},
            ],
            "add_edges": [
                {"source": "pkg.A", "target": "pkg.B", "type": "dependency"},
            ],
        })),
        _make_tool_response(("emit_diagram", {"reason": "done"})),
    ]
    result = _driver(client, "overview").run(cg, target_nodes=2)
    assert len(result.nodes) == 2
    assert len(result.edges) == 1
    assert result.edges[0].source == "pkg.A"


def test_tool_call_budget_terminates():
    cg = _make_code_graph()
    client = MagicMock()
    client.chat_tools.return_value = _make_tool_response(
        ("inspect_class", {"qualified_name": "pkg.X"})
    )
    result = _driver(client, "overview-peek", max_tool_calls=3).run(cg, target_nodes=5)
    assert client.chat_tools.call_count == 3
    assert result.nodes == []


def test_token_budget_terminates():
    cg = _make_code_graph()
    client = MagicMock()
    client.chat_tools.return_value = _make_tool_response(
        ("inspect_class", {"qualified_name": "pkg.X"})
    )
    _driver(client, "overview-peek", max_tokens=15).run(cg, target_nodes=5)
    # 20 Token pro Aufruf >= Budget 15, also genau eine Runde
    assert client.chat_tools.call_count == 1


def test_no_tool_calls_stops_loop_after_one_retry():
    cg = _make_code_graph()
    client = MagicMock()
    client.chat_tools.return_value = _empty_response()
    _driver(client, "overview-peek").run(cg, target_nodes=1)
    # chat_tools_with_retry fragt einmal nach, dann hört die Schleife auf
    assert client.chat_tools.call_count == 2


def test_unknown_tool_triggers_retry_and_continues():
    cg = _make_code_graph()
    client = MagicMock()
    client.chat_tools.side_effect = [
        _make_tool_response(("nonexistent_tool_xyz", {})),  # ungültig, wird wiederholt
        _make_tool_response(("emit_diagram", {"reason": "done"})),
    ]
    _driver(client, "overview-peek").run(cg, target_nodes=1)
    assert client.chat_tools.call_count == 2


def test_run_stats_accumulate_tokens_and_tool_calls():
    cg = _make_code_graph()
    client = MagicMock()
    client.chat_tools.side_effect = [
        _make_tool_response(("apply_edits", {"add_nodes": [{"id": "pkg.A", "name": "A", "package": "pkg"}]})),
        _make_tool_response(("emit_diagram", {"reason": "done"})),
    ]
    driver = _driver(client, "overview")
    driver.run(cg, target_nodes=1)
    assert driver.stats.tool_calls == 2
    assert driver.stats.tokens_in == 20   # 10 pro Antwort
    assert driver.stats.tokens_out == 20


def test_duplicate_node_returns_error_message():
    cg = _make_code_graph()
    tool_results: list[str] = []

    def fake_chat(msgs, tools):
        for m in reversed(msgs):
            if m.get("role") == "tool":
                tool_results.append(m["content"])
                break
        n = len(tool_results)
        if n <= 1:
            return _make_tool_response(("apply_edits", {"add_nodes": [{"id": "pkg.A", "name": "A", "package": "pkg"}]}))
        return _make_tool_response(("emit_diagram", {"reason": "done"}))

    client = MagicMock()
    client.chat_tools.side_effect = fake_chat
    result = _driver(client, "overview").run(cg, target_nodes=2)
    assert len([n for n in result.nodes if n.id == "pkg.A"]) == 1
    second_result = json.loads(tool_results[1])
    assert second_result.get("ok") is False
    assert second_result["errors"][0]["error"] == "node already exists"


def test_validator_applied_to_output():
    cg = _make_code_graph()
    client = MagicMock()
    client.chat_tools.side_effect = [
        _make_tool_response(("apply_edits", {"add_nodes": [{
            "id": "pkg.X", "name": "X", "package": "pkg",
            "attributes": ["a1", "a2", "a3", "a4", "a5", "a6"],
        }]})),
        _make_tool_response(("emit_diagram", {"reason": "done"})),
    ]
    result = _driver(client, "overview-peek").run(cg, target_nodes=1)
    if result.nodes:
        assert len(result.nodes[0].attributes) == 6  # Member werden nicht gekürzt


# Achse Peek: einziger Unterschied ist, welche Tools verfügbar sind

def test_peek_on_exposes_code_tools():
    cg = _make_code_graph()
    client = MagicMock()
    client.chat_tools.return_value = _make_tool_response(("emit_diagram", {"reason": "done"}))
    _driver(client, "overview-peek").run(cg, target_nodes=1)
    names = _sent_tool_names(client)
    assert {"read_file", "search_code"} <= names
    assert "list_dir" not in names


def test_read_file_limit_zero_disables_cap(tmp_path):
    (tmp_path / "big.py").write_text("\n".join(f"line{i}" for i in range(500)))
    cg = _make_code_graph()
    cg.root = tmp_path

    def _read(max_lines):
        graph = AbstractGraph(repo="t", target_nodes=1)
        graph.nodes.append(Node(id="pkg.A", name="A", package="pkg"))
        tools = build_tools(cg, graph, [False],
                            peek=True, read_file_max_lines=max_lines)
        fn = next(t.fn for t in tools if t.name == "read_file")
        return fn("big.py")

    capped = _read(200)
    assert capped["end_line"] == 200 and capped["truncated"]

    full = _read(0)
    assert full["end_line"] == 500 and not full["truncated"]
    assert full["content"].splitlines()[-1] == "line499"


def test_peek_off_hides_code_tools():
    cg = _make_code_graph()
    client = MagicMock()
    client.chat_tools.return_value = _make_tool_response(("emit_diagram", {"reason": "done"}))
    _driver(client, "overview").run(cg, target_nodes=1)
    names = _sent_tool_names(client)
    assert not ({"read_file", "search_code"} & names)
    # die drei Kern-Tools, in beiden Fällen gleich
    assert names == {"inspect_class", "apply_edits", "emit_diagram"}


# Achse Seed: die prune-Varianten starten mit dem pyreverse-Graphen

def test_prune_seeds_working_graph_from_pyreverse():
    cg = _make_code_graph(pyreverse_graph=_pyreverse_graph(3))
    client = MagicMock()
    client.chat_tools.side_effect = [
        _make_tool_response(("apply_edits", {"remove_node_ids": ["pkg.C2"]})),
        _make_tool_response(("emit_diagram", {"reason": "done"})),
    ]
    result = _driver(client, "prune").run(cg, target_nodes=2)
    assert {n.id for n in result.nodes} == {"pkg.C0", "pkg.C1"}


def test_apply_edits_bulk_removal():
    cg = _make_code_graph(pyreverse_graph=_pyreverse_graph(4))
    client = MagicMock()
    client.chat_tools.side_effect = [
        _make_tool_response(("apply_edits", {"remove_node_ids": ["pkg.C2", "pkg.C3", "pkg.Ghost"]})),
        _make_tool_response(("emit_diagram", {"reason": "done"})),
    ]
    result = _driver(client, "prune").run(cg, target_nodes=2)
    assert {n.id for n in result.nodes} == {"pkg.C0", "pkg.C1"}


def test_apply_edits_reports_missing_removals():
    cg = _make_code_graph(pyreverse_graph=_pyreverse_graph(2))
    tool_results: list[str] = []

    def fake_chat(msgs, tools):
        for m in reversed(msgs):
            if m.get("role") == "tool":
                tool_results.append(m["content"])
                break
        if not tool_results:
            return _make_tool_response(("apply_edits", {"remove_node_ids": ["pkg.C1", "pkg.Nope"]}))
        return _make_tool_response(("emit_diagram", {"reason": "done"}))

    client = MagicMock()
    client.chat_tools.side_effect = fake_chat
    _driver(client, "prune").run(cg, target_nodes=1)
    first = json.loads(tool_results[0])
    assert first["removed"] == 1
    assert first["errors"][0] == {"remove": "pkg.Nope", "error": "node not found"}


def test_apply_edits_dangling_endpoint_rejected():
    cg = _make_code_graph()
    tool_results: list[str] = []

    def fake_chat(msgs, tools):
        for m in reversed(msgs):
            if m.get("role") == "tool":
                tool_results.append(m["content"])
                break
        n = len(tool_results)
        if n == 0:
            return _make_tool_response(("apply_edits", {"add_nodes": [{"id": "pkg.A", "name": "A", "package": "pkg"}]}))
        if n == 1:
            return _make_tool_response(("apply_edits", {"add_edges": [
                {"source": "pkg.A", "target": "pkg.Missing", "type": "dependency"},
            ]}))
        return _make_tool_response(("emit_diagram", {"reason": "done"}))

    client = MagicMock()
    client.chat_tools.side_effect = fake_chat
    result = _driver(client, "overview").run(cg, target_nodes=1)
    assert result.edges == []
    edge_result = json.loads(tool_results[1])
    assert edge_result["ok"] is False
    assert "pkg.Missing" in edge_result["errors"][0]["error"]


def test_prune_does_not_mutate_source_pyreverse_graph():
    pg = _pyreverse_graph(3)
    cg = _make_code_graph(pyreverse_graph=pg)
    client = MagicMock()
    client.chat_tools.side_effect = [
        _make_tool_response(("apply_edits", {"remove_node_ids": ["pkg.C2"]})),
        _make_tool_response(("emit_diagram", {"reason": "done"})),
    ]
    _driver(client, "prune").run(cg, target_nodes=2)
    assert len(pg.nodes) == 3  # vorbefüllte Kopie, nicht das Original


def test_pyreverse_variants_bail_without_graph():
    cg = _make_code_graph(pyreverse_graph=None)
    client = MagicMock()
    for name in ("catalog", "catalog-peek", "prune", "prune-peek"):
        result = _driver(client, name).run(cg, target_nodes=5)
        assert result.nodes == []
    client.chat_tools.assert_not_called()


# Achse Kontext: was in der ersten User-Nachricht landet

def _first_user_message(client) -> str:
    messages, _ = client.chat_tools.call_args[0]
    return next(m["content"] for m in messages if m["role"] == "user")


def test_catalog_context_contains_full_graph():
    cg = _make_code_graph(pyreverse_graph=_pyreverse_graph(3))
    client = MagicMock()
    client.chat_tools.return_value = _make_tool_response(("emit_diagram", {"reason": "done"}))
    _driver(client, "catalog").run(cg, target_nodes=2)
    user_msg = _first_user_message(client)
    assert "pkg.C0" in user_msg and "pkg.C2" in user_msg


def test_overview_context_contains_package_summary():
    cg = _make_code_graph()
    client = MagicMock()
    client.chat_tools.return_value = _make_tool_response(("emit_diagram", {"reason": "done"}))
    _driver(client, "overview").run(cg, target_nodes=2)
    user_msg = _first_user_message(client)
    assert "package overview" in user_msg
    assert "total_classes" in user_msg


def test_overview_context_lists_qualified_class_names():
    from src.parsing.python.ast_pass import ClassInfo

    cls = ClassInfo(
        name="Core", qualified_name="mypkg.core.Core", module="mypkg.core",
        bases=[], decorators=[], attributes=[], methods=[],
        file=Path("/fake/repo/mypkg/core.py"), line_start=1, line_end=3,
    )
    cg = _make_code_graph(classes=[cls])
    client = MagicMock()
    client.chat_tools.return_value = _make_tool_response(("emit_diagram", {"reason": "done"}))
    _driver(client, "overview").run(cg, target_nodes=2)
    user_msg = _first_user_message(client)
    assert "classes_by_package" in user_msg
    assert "mypkg.core.Core" in user_msg


# Achse Zerlegung: Läufe pro Cluster plus Synthese über dieselbe Schleife

def test_clustered_runs_per_cluster_then_synthesis():
    cg = _make_code_graph()
    client = MagicMock()
    client.chat_tools.side_effect = [
        # Teillauf für Cluster 0
        _make_tool_response(("apply_edits", {"add_nodes": [{"id": "pkg.A", "name": "A", "package": "pkg"}]})),
        _make_tool_response(("emit_diagram", {"reason": "cluster done"})),
        # Synthese-Lauf (Arbeitsgraph = zusammengeführte Teilgraphen)
        _make_tool_response(("emit_diagram", {"reason": "synthesis done"})),
    ]
    with patch("src.methods.driver.cluster_modules", return_value=[{"pkg"}]):
        result = _driver(client, "cluster-peek").run(cg, target_nodes=2)
    assert {n.id for n in result.nodes} == {"pkg.A"}
    assert client.chat_tools.call_count == 3


def test_clustered_synthesis_can_prune_merged_graph():
    cg = _make_code_graph()
    client = MagicMock()
    client.chat_tools.side_effect = [
        _make_tool_response(("apply_edits", {"add_nodes": [
            {"id": "pkg.A", "name": "A", "package": "pkg"},
            {"id": "pkg.B", "name": "B", "package": "pkg"},
        ]})),
        _make_tool_response(("emit_diagram", {"reason": "cluster done"})),
        # die Synthese entfernt einen der zusammengeführten Knoten
        _make_tool_response(("apply_edits", {"remove_node_ids": ["pkg.B"]})),
        _make_tool_response(("emit_diagram", {"reason": "synthesis done"})),
    ]
    with patch("src.methods.driver.cluster_modules", return_value=[{"pkg"}]):
        result = _driver(client, "cluster").run(cg, target_nodes=1)
    assert {n.id for n in result.nodes} == {"pkg.A"}


def test_cluster_context_includes_repo_overview():
    from src.parsing.python.ast_pass import ClassInfo

    cls = ClassInfo(
        name="Core", qualified_name="pkg.core.Core", module="pkg.core",
        bases=[], decorators=[], attributes=[], methods=[],
        file=Path("/fake/repo/pkg/core.py"), line_start=1, line_end=3,
    )
    cg = _make_code_graph(classes=[cls])
    first_user_msgs: list[str] = []

    def fake_chat(msgs, tools):
        first_user_msgs.append(next(m["content"] for m in msgs if m["role"] == "user"))
        return _make_tool_response(("emit_diagram", {"reason": "done"}))

    client = MagicMock()
    client.chat_tools.side_effect = fake_chat
    with patch("src.methods.driver.cluster_modules", return_value=[{"pkg.core"}]):
        _driver(client, "cluster").run(cg, target_nodes=2)

    cluster_msg, synthesis_msg = first_user_msgs[0], first_user_msgs[-1]
    # Der Teillauf eines Clusters sieht die Gesamtsicht und die Details seines Clusters.
    assert "repo_overview" in cluster_msg
    assert "cluster_modules" in cluster_msg
    # Die Synthese bekommt ebenfalls die Gesamtsicht neben dem zusammengeführten Graphen.
    assert "repo_overview" in synthesis_msg
    assert "merged_graph" in synthesis_msg


def test_synthesis_system_prompt_uses_merged_seed():
    cg = _make_code_graph()
    system_prompts: list[str] = []

    def fake_chat(msgs, tools):
        system_prompts.append(msgs[0]["content"])
        return _make_tool_response(("emit_diagram", {"reason": "done"}))

    client = MagicMock()
    client.chat_tools.side_effect = fake_chat
    with patch("src.methods.driver.cluster_modules", return_value=[{"pkg"}]):
        _driver(client, "cluster").run(cg, target_nodes=2)

    cluster_prompt, synthesis_prompt = system_prompts[0], system_prompts[-1]
    assert "starts EMPTY" in cluster_prompt
    assert "merged per-cluster" in synthesis_prompt
    assert "starts EMPTY" not in synthesis_prompt


def test_clustered_no_clusters_returns_empty():
    cg = _make_code_graph()
    client = MagicMock()
    with patch("src.methods.driver.cluster_modules", return_value=[]):
        result = _driver(client, "cluster").run(cg, target_nodes=2)
    assert result.nodes == []
    client.chat_tools.assert_not_called()


# Verlauf zusammenfassen

def test_compression_called_after_n_tool_calls():
    cg = _make_code_graph()
    client = MagicMock()
    client.chat_tools.side_effect = [
        _make_tool_response(("inspect_class", {"qualified_name": "pkg.A"})),
        _make_tool_response(("apply_edits", {"add_nodes": [{"id": "pkg.A", "name": "A", "package": "pkg"}]})),
        _make_tool_response(("emit_diagram", {"reason": "done"})),
    ]

    compress_calls: list[int] = []

    def fake_compress(client_, messages, turn_num):
        compress_calls.append(turn_num)
        return messages

    with patch("src.methods.driver.compress_history", side_effect=fake_compress):
        _driver(client, "overview-peek", compress_every_n_turns=2).run(cg, target_nodes=1)

    assert 2 in compress_calls


def test_no_compression_when_disabled():
    cg = _make_code_graph()
    client = MagicMock()
    client.chat_tools.side_effect = [
        _make_tool_response(("inspect_class", {"qualified_name": "pkg.A"})),
        _make_tool_response(("apply_edits", {"add_nodes": [{"id": "pkg.A", "name": "A", "package": "pkg"}]})),
        _make_tool_response(("emit_diagram", {"reason": "done"})),
    ]
    with patch("src.methods.driver.compress_history") as mock_compress:
        _driver(client, "overview-peek", compress_every_n_turns=0).run(cg, target_nodes=1)
    mock_compress.assert_not_called()


# inspect_class (immer verfügbar, alle Varianten)

def test_inspect_class_tool_returns_info():
    from src.parsing.python.ast_pass import ClassInfo

    cls = ClassInfo(
        name="MyClass", qualified_name="pkg.MyClass", module="pkg",
        bases=[], decorators=[], attributes=["x: int"], methods=["run()"],
        file=Path("/fake/repo/pkg.py"), line_start=1, line_end=5,
    )
    cg = _make_code_graph(classes=[cls])
    captured: list[str] = []

    def fake_chat(msgs, tools):
        for m in reversed(msgs):
            if m.get("role") == "tool":
                captured.append(m["content"])
                break
        if not captured:
            return _make_tool_response(("inspect_class", {"qualified_name": "pkg.MyClass"}))
        return _make_tool_response(("emit_diagram", {"reason": "done"}))

    client = MagicMock()
    client.chat_tools.side_effect = fake_chat
    _driver(client, "overview").run(cg, target_nodes=1)

    assert captured
    result = json.loads(captured[0])
    assert result.get("name") == "MyClass"
    assert result.get("qualified_name") == "pkg.MyClass"
