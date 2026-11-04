from __future__ import annotations

import json

from src.llm.stub import StubLLMClient, _STUB_GRAPH_JSON
from src.llm.tools import Tool, make_tool


# Hilfsfunktionen

def _no_trace_stub() -> StubLLMClient:
    return StubLLMClient()


def _finish_tool() -> Tool:
    def finish(reason: str) -> dict:
        return {"ok": True}
    return make_tool(finish)


def _apply_edits_tool() -> Tool:
    def apply_edits(remove_node_ids: list = None, add_nodes: list = None,
                    add_edges: list = None) -> dict:
        return {"ok": True}
    return make_tool(apply_edits)


def _inspect_tool() -> Tool:
    def inspect_class(qualified_name: str) -> dict:
        return {"name": qualified_name}
    return make_tool(inspect_class)


# chat / chat_json

def test_chat_returns_stub_graph():
    stub = _no_trace_stub()
    resp = stub.chat([{"role": "user", "content": "hi"}])
    assert resp.text == _STUB_GRAPH_JSON
    assert resp.tool_calls == []
    assert resp.tokens_in == 0
    assert resp.tokens_out == 0
    assert resp.elapsed_ms == 1


def test_chat_json_returns_stub_graph():
    stub = _no_trace_stub()
    resp = stub.chat_json([{"role": "user", "content": "hi"}])
    data = json.loads(resp.text)
    assert len(data["nodes"]) == 3
    assert len(data["edges"]) == 2


# chat_tools: vorgegebene Abfolge

def test_chat_tools_first_call_apply_edits():
    stub = _no_trace_stub()
    tools = [_inspect_tool(), _apply_edits_tool(), _finish_tool()]
    resp = stub.chat_tools([], tools)
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "apply_edits"
    assert len(resp.tool_calls[0].arguments["add_nodes"]) == 2
    assert len(resp.tool_calls[0].arguments["add_edges"]) == 1


def test_chat_tools_second_call_finish():
    stub = _no_trace_stub()
    tools = [_inspect_tool(), _apply_edits_tool(), _finish_tool()]
    stub.chat_tools([], tools)  # Aufruf 0
    resp = stub.chat_tools([], tools)  # Aufruf 1
    assert resp.tool_calls[0].name == "finish"


def test_chat_tools_no_add_tool_falls_through_to_finish():
    stub = _no_trace_stub()
    tools = [_finish_tool()]
    resp = stub.chat_tools([], tools)
    assert resp.tool_calls[0].name == "finish"


def test_chat_tools_finish_args_contain_reason():
    stub = _no_trace_stub()
    tools = [_finish_tool()]
    # Weiter bis Aufruf 3
    for _ in range(3):
        stub.chat_tools([], tools)
    resp = stub.chat_tools([], tools)
    assert resp.tool_calls[0].arguments.get("reason")


def test_stub_independent_sequence_per_tools_list():
    stub = _no_trace_stub()
    tools_a = [_apply_edits_tool(), _finish_tool()]
    tools_b = [_finish_tool()]

    resp_a = stub.chat_tools([], tools_a)
    resp_b = stub.chat_tools([], tools_b)

    assert resp_a.tool_calls[0].name == "apply_edits"
    assert resp_b.tool_calls[0].name == "finish"


def test_stub_token_counts_are_zero():
    stub = _no_trace_stub()
    tools = [_finish_tool()]
    resp = stub.chat_tools([], tools)
    assert resp.tokens_in == 0
    assert resp.tokens_out == 0
