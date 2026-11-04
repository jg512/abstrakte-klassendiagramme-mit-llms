"""Platzhalter für den LLMClient bei Trockenläufen.

Liefert feste Antworten, ohne ein echtes Modell aufzurufen. In der
Driver-Schleife ruft er die Tools in dieser Reihenfolge auf:

  Aufruf 0:      apply_edits mit den Platzhalter-Knoten und, falls vorhanden,
                 der Kante. Gibt es apply_edits nicht, das erste Tool, das den
                 Lauf nicht beendet.
  ab Aufruf 1:   emit_diagram (bzw. finish), was den Lauf beendet

Bei Aufrufen ohne Tools (chat_json, chat) gibt er einen sehr kleinen,
gültigen Graphen zurück.
"""
from __future__ import annotations

import json
import logging

from src.llm.client import LLMResponse
from src.llm.tools import Tool, ToolCall
from src.llm.trace import TraceLogger

log = logging.getLogger(__name__)

_STUB_GRAPH_JSON = json.dumps({
    "repo": "stub",
    "target_nodes": 3,
    "packages": [{"name": "stub"}],
    "nodes": [
        {"id": "stub.Alpha", "name": "Alpha", "package": "stub",
         "stereotype": None, "attributes": [], "methods": []},
        {"id": "stub.Beta", "name": "Beta", "package": "stub",
         "stereotype": None, "attributes": [], "methods": []},
        {"id": "stub.Gamma", "name": "Gamma", "package": "stub",
         "stereotype": None, "attributes": [], "methods": []},
    ],
    "edges": [
        {"source": "stub.Alpha", "target": "stub.Beta", "type": "dependency"},
        {"source": "stub.Beta", "target": "stub.Gamma", "type": "dependency"},
    ],
})

_STUB_NODES = [
    {"id": "stub.Alpha", "name": "Alpha", "package": "stub"},
    {"id": "stub.Beta", "name": "Beta", "package": "stub"},
]

_STUB_EDGES = [
    {"source": "stub.Alpha", "target": "stub.Beta", "type": "dependency"},
]

_TOOL_CALL_ID = "stub-call-{n}"


class StubLLMClient:
    """Ersatz für LLMClient, der nie ein echtes LLM aufruft."""

    def __init__(self, trace: TraceLogger | None = None) -> None:
        self._trace = trace or TraceLogger()
        self._tool_seq: dict[int, int] = {}  # Objekt-ID -> Aufrufindex
        # Referenzen auf die Tool-Listen behalten, damit der GC ihre id() nicht für neue Objekte freigibt.
        self._tool_refs: list[list[Tool]] = []

    def _response(self, text: str | None, tool_calls: list[ToolCall]) -> LLMResponse:
        resp = LLMResponse(
            text=text,
            tool_calls=tool_calls,
            tokens_in=0,
            tokens_out=0,
            elapsed_ms=1,
        )
        self._trace.log({
            "model": "stub",
            "tokens_in": 0,
            "tokens_out": 0,
            "elapsed_ms": 1,
            "has_tool_calls": bool(tool_calls),
            "stub": True,
        })
        return resp

    def chat(self, messages: list[dict]) -> LLMResponse:
        return self._response(_STUB_GRAPH_JSON, [])

    def chat_json(self, messages: list[dict]) -> LLMResponse:
        return self._response(_STUB_GRAPH_JSON, [])

    def set_trace_context(self, ctx: dict) -> None:
        self._trace.set_context(ctx)

    def clear_trace_context(self) -> None:
        self._trace.clear_context()

    # Leere Methoden, damit die Schnittstelle zu LLMClient passt.
    def set_chunk_meta(self, meta: dict | None) -> None:  # noqa: ARG002
        pass

    def mark_retry(self) -> None:
        pass

    def chat_tools(self, messages: list[dict], tools: list[Tool]) -> LLMResponse:
        seq_key = id(tools)
        if seq_key not in self._tool_seq:
            self._tool_refs.append(tools)
        call_idx = self._tool_seq.get(seq_key, 0)
        self._tool_seq[seq_key] = call_idx + 1

        tc = _pick_tool_call(call_idx, tools)
        return self._response(None, [tc])


_FINISH_NAMES: frozenset[str] = frozenset({"finish", "emit_diagram"})


def _pick_tool_call(call_idx: int, tools: list[Tool]) -> ToolCall:
    tc_id = _TOOL_CALL_ID.format(n=call_idx)
    tool_names = {t.name for t in tools}

    if call_idx == 0:
        if "apply_edits" in tool_names:
            return ToolCall(
                id=tc_id,
                name="apply_edits",
                arguments={"add_nodes": _STUB_NODES, "add_edges": _STUB_EDGES},
            )
        for tool in tools:
            if tool.name not in _FINISH_NAMES:
                return ToolCall(id=tc_id, name=tool.name, arguments={})

    # Sonst emit_diagram bzw. finish
    for name in _FINISH_NAMES:
        if name in tool_names:
            return ToolCall(id=tc_id, name=name, arguments={"reason": "stub dry-run complete"})

    return ToolCall(id=tc_id, name=tools[-1].name, arguments={})
