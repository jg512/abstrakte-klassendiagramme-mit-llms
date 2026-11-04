from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.llm.client import LLMResponse
from src.targeting.auto_target import (
    _DEFAULT_TARGET,
    _MAX_TARGET,
    _MIN_TARGET,
    decide_target_nodes,
)


PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _make_client(payload: dict | None) -> MagicMock:
    text = json.dumps(payload) if payload is not None else "not json"
    resp = LLMResponse(text=text, tool_calls=[], tokens_in=1, tokens_out=1, elapsed_ms=1)
    client = MagicMock()
    client.chat_json.return_value = resp
    client.mark_retry = MagicMock()
    return client


def _make_code_graph(n_classes: int = 10, n_functions: int = 5) -> MagicMock:
    cls_mock = MagicMock()
    cls_mock.module = "mypkg.core"
    classes = [cls_mock] * n_classes

    fn_mock = MagicMock()
    functions = [fn_mock] * n_functions

    cg = MagicMock()
    cg.repo = "testrepo"
    cg.language = "python"
    cg.source_files = [MagicMock()] * 8
    cg.classes = classes
    cg.functions = functions
    return cg


class TestDecideTargetNodes:
    def test_returns_llm_value(self):
        client = _make_client({"target_nodes": 15})
        result = decide_target_nodes(client, _make_code_graph(), loc=1000, prompts_dir=PROMPTS_DIR)
        assert result == 15

    def test_clamps_below_min(self):
        client = _make_client({"target_nodes": 2})
        result = decide_target_nodes(client, _make_code_graph(), loc=500, prompts_dir=PROMPTS_DIR)
        assert result == _MIN_TARGET

    def test_clamps_above_max(self):
        client = _make_client({"target_nodes": 99})
        result = decide_target_nodes(client, _make_code_graph(), loc=5000, prompts_dir=PROMPTS_DIR)
        assert result == _MAX_TARGET

    def test_fallback_on_parse_failure(self):
        resp = LLMResponse(text="not json at all", tool_calls=[], tokens_in=1, tokens_out=1, elapsed_ms=1)
        client = MagicMock()
        client.chat_json.return_value = resp
        client.mark_retry = MagicMock()
        result = decide_target_nodes(client, _make_code_graph(), loc=1000, prompts_dir=PROMPTS_DIR)
        assert result == _DEFAULT_TARGET

    def test_fallback_on_wrong_type(self):
        client = _make_client({"target_nodes": "twelve"})
        result = decide_target_nodes(client, _make_code_graph(), loc=1000, prompts_dir=PROMPTS_DIR)
        assert result == _DEFAULT_TARGET

    def test_fallback_on_missing_key(self):
        client = _make_client({"something_else": 10})
        result = decide_target_nodes(client, _make_code_graph(), loc=1000, prompts_dir=PROMPTS_DIR)
        assert result == _DEFAULT_TARGET

    def test_stats_includes_key_fields(self):
        captured = []

        def fake_chat_json(messages):
            captured.extend(messages)
            return LLMResponse(
                text=json.dumps({"target_nodes": 12}),
                tool_calls=[], tokens_in=1, tokens_out=1, elapsed_ms=1,
            )

        client = MagicMock()
        client.chat_json.side_effect = fake_chat_json
        client.mark_retry = MagicMock()

        cg = _make_code_graph(n_classes=25, n_functions=8)
        decide_target_nodes(client, cg, loc=3000, prompts_dir=PROMPTS_DIR)

        assert captured, "no messages sent to LLM"
        content = captured[0]["content"]
        assert "testrepo" in content
        assert "25" in content   # Klassenzahl
        assert "3000" in content  # LOC

    def test_exactly_at_min_boundary(self):
        client = _make_client({"target_nodes": _MIN_TARGET})
        result = decide_target_nodes(client, _make_code_graph(), loc=100, prompts_dir=PROMPTS_DIR)
        assert result == _MIN_TARGET

    def test_exactly_at_max_boundary(self):
        client = _make_client({"target_nodes": _MAX_TARGET})
        result = decide_target_nodes(client, _make_code_graph(), loc=10000, prompts_dir=PROMPTS_DIR)
        assert result == _MAX_TARGET
