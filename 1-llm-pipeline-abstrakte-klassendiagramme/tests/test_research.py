from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.llm.client import LLMResponse
from src.llm.tools import ToolCall
from src.runs.research import ResearchWriter, ResearchLLMClient
from src.schema.graph import AbstractGraph, Node, Edge


# Hilfsfunktionen

def _make_response(text: str = "hello", tool_calls=None) -> LLMResponse:
    return LLMResponse(
        text=text,
        tool_calls=tool_calls or [],
        tokens_in=5,
        tokens_out=10,
        elapsed_ms=42,
    )


def _stub_inner(response: LLMResponse):
    inner = MagicMock()
    inner.chat.return_value = response
    inner.chat_json.return_value = response
    inner.chat_tools.return_value = response
    inner._trace = MagicMock()
    return inner


# ResearchWriter

class TestResearchWriter:
    def test_creates_subdirs(self, tmp_path):
        rw = ResearchWriter(tmp_path / "run")
        assert (tmp_path / "run" / "prompts").is_dir()
        assert (tmp_path / "run" / "steps").is_dir()
        assert (tmp_path / "run" / "snapshots").is_dir()

    def test_save_prompt(self, tmp_path):
        rw = ResearchWriter(tmp_path)
        rw.save_prompt("system.txt", "hello world")
        assert (tmp_path / "prompts" / "system.txt").read_text() == "hello world"

    def test_record_exchange_numbering(self, tmp_path):
        rw = ResearchWriter(tmp_path)
        msgs = [{"role": "user", "content": "hi"}]
        rw.record_exchange(msgs, _make_response("first"))
        rw.record_exchange(msgs, _make_response("second"))
        assert (tmp_path / "steps" / "01_request.json").exists()
        assert (tmp_path / "steps" / "01_response.json").exists()
        assert (tmp_path / "steps" / "02_request.json").exists()
        assert (tmp_path / "steps" / "02_response.json").exists()

    def test_record_exchange_step_label(self, tmp_path):
        rw = ResearchWriter(tmp_path)
        msgs = [{"role": "user", "content": "hi"}]
        rw.record_exchange(msgs, _make_response(), step_label="pkg_core")
        data = json.loads((tmp_path / "steps" / "01_response.json").read_text())
        assert data["step_label"] == "pkg_core"

    def test_record_exchange_no_label_omitted(self, tmp_path):
        rw = ResearchWriter(tmp_path)
        msgs = [{"role": "user", "content": "hi"}]
        rw.record_exchange(msgs, _make_response())
        data = json.loads((tmp_path / "steps" / "01_response.json").read_text())
        assert "step_label" not in data

    def test_record_exchange_truncates_large_tool_result(self, tmp_path):
        rw = ResearchWriter(tmp_path)
        big_body = "x" * (9 * 1024)  # 9 KB liegt über der Schwelle von 8 KB
        msgs = [{"role": "tool", "tool_call_id": "c1", "content": big_body}]
        rw.record_exchange(msgs, _make_response())
        saved = json.loads((tmp_path / "steps" / "01_request.json").read_text())
        assert saved[0]["content"].startswith("[truncated:")

    def test_save_snapshot_dict(self, tmp_path):
        rw = ResearchWriter(tmp_path)
        rw.save_snapshot("data.json", {"key": "value", "count": 3})
        loaded = json.loads((tmp_path / "snapshots" / "data.json").read_text())
        assert loaded["key"] == "value"
        assert loaded["count"] == 3

    def test_save_snapshot_abstract_graph(self, tmp_path):
        rw = ResearchWriter(tmp_path)
        g = AbstractGraph(
            repo="testrepo",
            target_nodes=5,
            nodes=[Node(id="a.A", name="A", package="a")],
            edges=[],
        )
        rw.save_snapshot("graph.json", g)
        loaded = json.loads((tmp_path / "snapshots" / "graph.json").read_text())
        assert loaded["repo"] == "testrepo"
        assert any(n["id"] == "a.A" for n in loaded["nodes"])

    def test_save_snapshot_also_puml(self, tmp_path):
        rw = ResearchWriter(tmp_path)
        g = AbstractGraph(
            repo="testrepo",
            target_nodes=5,
            nodes=[Node(id="a.A", name="A", package="a")],
            edges=[],
        )
        rw.save_snapshot("graph.json", g, also_puml=True)
        assert (tmp_path / "snapshots" / "graph.json").exists()
        assert (tmp_path / "snapshots" / "graph.puml").exists()
        puml = (tmp_path / "snapshots" / "graph.puml").read_text()
        assert "@startuml" in puml

    def test_record_exchange_chunk_meta(self, tmp_path):
        rw = ResearchWriter(tmp_path)
        msgs = [{"role": "user", "content": "hi"}]
        meta = {"chunk_label": "pkg=alpha", "chunk_index": 1, "chunk_count": 3}
        rw.record_exchange(msgs, _make_response(), chunk_meta=meta)
        data = json.loads((tmp_path / "steps" / "01_response.json").read_text())
        assert data["chunk_label"] == "pkg=alpha"
        assert data["chunk_index"] == 1
        assert data["chunk_count"] == 3

    def test_record_exchange_no_chunk_meta_omitted(self, tmp_path):
        rw = ResearchWriter(tmp_path)
        msgs = [{"role": "user", "content": "hi"}]
        rw.record_exchange(msgs, _make_response())
        data = json.loads((tmp_path / "steps" / "01_response.json").read_text())
        assert "chunk_label" not in data
        assert "chunk_index" not in data


# ResearchLLMClient

class TestResearchLLMClient:
    def test_records_chat(self, tmp_path):
        resp = _make_response("hi")
        inner = _stub_inner(resp)
        rw = ResearchWriter(tmp_path)
        rc = ResearchLLMClient(inner, rw, phase="m1")
        msgs = [{"role": "user", "content": "go"}]
        result = rc.chat(msgs)
        assert result is resp
        assert (tmp_path / "steps" / "01_request.json").exists()
        assert (tmp_path / "steps" / "01_response.json").exists()

    def test_records_chat_json(self, tmp_path):
        resp = _make_response("{}")
        inner = _stub_inner(resp)
        rw = ResearchWriter(tmp_path)
        rc = ResearchLLMClient(inner, rw, phase="m1")
        msgs = [{"role": "user", "content": "go"}]
        result = rc.chat_json(msgs)
        assert result is resp
        assert (tmp_path / "steps" / "01_response.json").exists()

    def test_records_chat_tools(self, tmp_path):
        tc = ToolCall(id="x", name="finish", arguments={"reason": "done"})
        resp = _make_response(tool_calls=[tc])
        inner = _stub_inner(resp)
        rw = ResearchWriter(tmp_path)
        rc = ResearchLLMClient(inner, rw, phase="m2")
        msgs = [{"role": "user", "content": "go"}]
        result = rc.chat_tools(msgs, [])
        assert result is resp
        saved = json.loads((tmp_path / "steps" / "01_response.json").read_text())
        assert saved["tool_calls"][0]["name"] == "finish"

    def test_sets_and_clears_trace_context(self, tmp_path):
        resp = _make_response()
        inner = _stub_inner(resp)
        rw = ResearchWriter(tmp_path)
        rc = ResearchLLMClient(inner, rw, phase="m1")
        rc.chat([{"role": "user", "content": "hi"}])
        inner.set_trace_context.assert_called_once_with({"step": 1, "phase": "m1"})
        inner.clear_trace_context.assert_called_once()

    def test_getattr_delegates_to_inner(self, tmp_path):
        resp = _make_response()
        inner = _stub_inner(resp)
        inner.some_attr = "hello"
        rw = ResearchWriter(tmp_path)
        rc = ResearchLLMClient(inner, rw)
        assert rc.some_attr == "hello"

    def test_set_chunk_meta_propagates_to_response(self, tmp_path):
        resp = _make_response("{}")
        inner = _stub_inner(resp)
        rw = ResearchWriter(tmp_path)
        rc = ResearchLLMClient(inner, rw, phase="m4a")
        rc.set_chunk_meta({"chunk_label": "pkg=foo", "chunk_index": 2, "chunk_count": 5})
        rc.chat_json([{"role": "user", "content": "go"}])
        data = json.loads((tmp_path / "steps" / "01_response.json").read_text())
        assert data["chunk_label"] == "pkg=foo"
        assert data["chunk_count"] == 5

    def test_mark_retry_sets_is_retry(self, tmp_path):
        resp = _make_response("{}")
        inner = _stub_inner(resp)
        rw = ResearchWriter(tmp_path)
        rc = ResearchLLMClient(inner, rw, phase="m4a")
        rc.set_chunk_meta({"chunk_label": "pkg=bar"})
        rc.mark_retry()
        rc.chat_json([{"role": "user", "content": "retry"}])
        data = json.loads((tmp_path / "steps" / "01_response.json").read_text())
        assert data["is_retry"] is True
        assert data["chunk_label"] == "pkg=bar"  # vorhandene Metadaten bleiben erhalten

    def test_set_chunk_meta_none_clears(self, tmp_path):
        resp = _make_response("{}")
        inner = _stub_inner(resp)
        rw = ResearchWriter(tmp_path)
        rc = ResearchLLMClient(inner, rw)
        rc.set_chunk_meta({"chunk_label": "pkg=foo"})
        rc.set_chunk_meta(None)
        rc.chat_json([{"role": "user", "content": "clean"}])
        data = json.loads((tmp_path / "steps" / "01_response.json").read_text())
        assert "chunk_label" not in data
