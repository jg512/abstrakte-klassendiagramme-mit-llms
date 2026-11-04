from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from src.llm.client import LLMResponse
from src.schema.json_io import graph_to_dict

log = logging.getLogger(__name__)

_TRUNCATE_BYTES = 8 * 1024  # 8 KB


class ResearchWriter:
    def __init__(self, run_dir: Path) -> None:
        self._run_dir = run_dir
        self._step_counter = 0
        (run_dir / "prompts").mkdir(parents=True, exist_ok=True)
        (run_dir / "steps").mkdir(parents=True, exist_ok=True)
        (run_dir / "snapshots").mkdir(parents=True, exist_ok=True)

    def save_prompt(self, name: str, content: str) -> None:
        (self._run_dir / "prompts" / name).write_text(content, encoding="utf-8")

    def record_exchange(
        self,
        messages: list[dict],
        response: LLMResponse,
        step_label: str | None = None,
        chunk_meta: dict | None = None,
    ) -> None:
        self._step_counter += 1
        n = self._step_counter
        label = f"{n:02d}"

        safe_messages = []
        for msg in messages:
            if msg.get("role") == "tool":
                body = msg.get("content", "")
                if isinstance(body, str) and len(body.encode()) > _TRUNCATE_BYTES:
                    msg = {**msg, "content": f"[truncated: {len(body.encode())} bytes]"}
            safe_messages.append(msg)

        req_path = self._run_dir / "steps" / f"{label}_request.json"
        req_path.write_text(json.dumps(safe_messages, indent=2), encoding="utf-8")

        resp_data: dict[str, Any] = {
            "text": response.text,
            "tool_calls": [
                {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                for tc in response.tool_calls
            ],
            "tokens_in": response.tokens_in,
            "tokens_out": response.tokens_out,
            "elapsed_ms": response.elapsed_ms,
        }
        if step_label is not None:
            resp_data["step_label"] = step_label
        if chunk_meta is not None:
            resp_data.update(chunk_meta)

        resp_path = self._run_dir / "steps" / f"{label}_response.json"
        resp_path.write_text(json.dumps(resp_data, indent=2), encoding="utf-8")

    def save_snapshot(self, name: str, data: Any, also_puml: bool = False) -> None:
        from src.schema.graph import AbstractGraph
        if isinstance(data, AbstractGraph):
            graph = data
            data = graph_to_dict(graph)
        else:
            graph = None
        (self._run_dir / "snapshots" / name).write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )
        if also_puml and graph is not None:
            from src.schema.plantuml import to_plantuml
            puml = to_plantuml(graph)
            puml_name = name.replace(".json", ".puml")
            (self._run_dir / "snapshots" / puml_name).write_text(puml, encoding="utf-8")


class ResearchLLMClient:
    def __init__(self, inner: Any, research: ResearchWriter, phase: str = "") -> None:
        self._inner = inner
        self._research = research
        self._phase = phase
        self._chunk_meta: dict | None = None
        self._is_retry: bool = False

    def set_chunk_meta(self, meta: dict | None) -> None:
        self._chunk_meta = meta
        self._is_retry = False

    def mark_retry(self) -> None:
        # Markiert nur den nächsten aufgezeichneten Austausch als Wiederholung, danach wird das Flag zurückgesetzt.
        self._is_retry = True

    def _consume_meta(self) -> dict | None:
        meta = self._chunk_meta
        if self._is_retry:
            meta = {**(meta or {}), "is_retry": True}
            self._is_retry = False
        return meta

    def chat(self, messages: list[dict]) -> LLMResponse:
        self._inner.set_trace_context({"step": self._research._step_counter + 1, "phase": self._phase})
        try:
            resp = self._inner.chat(messages)
        finally:
            self._inner.clear_trace_context()
        self._research.record_exchange(messages, resp, chunk_meta=self._consume_meta())
        return resp

    def chat_json(self, messages: list[dict]) -> LLMResponse:
        self._inner.set_trace_context({"step": self._research._step_counter + 1, "phase": self._phase})
        try:
            resp = self._inner.chat_json(messages)
        finally:
            self._inner.clear_trace_context()
        self._research.record_exchange(messages, resp, chunk_meta=self._consume_meta())
        return resp

    def chat_tools(self, messages: list[dict], tools: list) -> LLMResponse:
        self._inner.set_trace_context({"step": self._research._step_counter + 1, "phase": self._phase})
        try:
            resp = self._inner.chat_tools(messages, tools)
        finally:
            self._inner.clear_trace_context()
        self._research.record_exchange(messages, resp, chunk_meta=self._consume_meta())
        return resp

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)
