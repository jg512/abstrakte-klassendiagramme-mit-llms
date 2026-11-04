from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from src.config import load_config
from src.llm.client import LLMClient, LLMResponse, _build_model_str
from src.llm.retry import (
    _has_valid_calls,
    _try_parse,
    chat_json_with_retry,
    chat_tools_with_retry,
)
from src.llm.tools import Tool, ToolCall, make_tool
from src.llm.trace import TraceLogger

# Die Ollama-Variante prüft die backend-spezifischen Argumente (num_ctx, api_base).
_CFG = load_config("configs/ollama.yaml")


# Hilfsfunktionen

def _fake_completion(content: str = "", tool_calls=None, tokens_in: int = 10, tokens_out: int = 20):
    """Eine minimale gefälschte ModelResponse von litellm bauen."""
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls or []

    choice = MagicMock()
    choice.message = msg

    usage = MagicMock()
    usage.prompt_tokens = tokens_in
    usage.completion_tokens = tokens_out

    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = usage
    return resp


def _fake_tool_call(name: str, arguments: dict, call_id: str = "call_1"):
    tc = MagicMock()
    tc.id = call_id
    tc.function.name = name
    tc.function.arguments = json.dumps(arguments)
    return tc


def _fake_tool_response(name: str, arguments: dict):
    return _fake_completion(tool_calls=[_fake_tool_call(name, arguments)])


# TraceLogger

class TestTraceLogger:
    def test_no_path_is_noop(self):
        logger = TraceLogger()
        logger.log({"key": "value"})  # darf nicht werfen

    def test_writes_jsonl(self, tmp_path):
        p = tmp_path / "trace.jsonl"
        logger = TraceLogger(path=p)
        logger.log({"a": 1})
        logger.log({"b": 2})
        lines = p.read_text().splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0]) == {"a": 1}
        assert json.loads(lines[1]) == {"b": 2}

    def test_appends_across_calls(self, tmp_path):
        p = tmp_path / "trace.jsonl"
        logger = TraceLogger(path=p)
        for i in range(3):
            logger.log({"i": i})
        assert len(p.read_text().splitlines()) == 3

    def test_trace_merges_context(self, tmp_path):
        p = tmp_path / "trace.jsonl"
        logger = TraceLogger(path=p)
        logger.set_context({"step": 1, "phase": "m1"})
        logger.log({"tokens_in": 10})
        line = json.loads(p.read_text().strip())
        assert line["step"] == 1
        assert line["phase"] == "m1"
        assert line["tokens_in"] == 10

    def test_trace_context_cleared(self, tmp_path):
        p = tmp_path / "trace.jsonl"
        logger = TraceLogger(path=p)
        logger.set_context({"step": 1})
        logger.clear_context()
        logger.log({"x": 2})
        line = json.loads(p.read_text().strip())
        assert "step" not in line
        assert line["x"] == 2

    def test_trace_event_overrides_context(self, tmp_path):
        p = tmp_path / "trace.jsonl"
        logger = TraceLogger(path=p)
        logger.set_context({"step": 1, "shared": "ctx"})
        logger.log({"step": 99, "extra": "val"})
        line = json.loads(p.read_text().strip())
        assert line["step"] == 99  # der Wert aus dem Ereignis gewinnt
        assert line["shared"] == "ctx"
        assert line["extra"] == "val"


# Tool / make_tool

class TestTools:
    def test_make_tool_name_and_description(self):
        def add(a: int, b: int) -> int:
            """Add two integers."""
            return a + b

        tool = make_tool(add)
        assert tool.name == "add"
        assert "Add" in tool.description

    def test_infers_int_type(self):
        def add(a: int, b: int) -> int:
            return a + b

        tool = make_tool(add)
        assert tool.parameters["properties"]["a"]["type"] == "integer"
        assert tool.parameters["properties"]["b"]["type"] == "integer"

    def test_infers_str_type(self):
        def greet(name: str) -> str:
            return f"hi {name}"

        tool = make_tool(greet)
        assert tool.parameters["properties"]["name"]["type"] == "string"

    def test_required_for_positional(self):
        def fn(x: int, y: int = 0) -> int:
            return x + y

        tool = make_tool(fn)
        assert "x" in tool.parameters["required"]
        assert "y" not in tool.parameters.get("required", [])

    def test_to_litellm_schema_shape(self):
        def noop(x: str) -> str:
            return x

        schema = make_tool(noop).to_litellm()
        assert schema["type"] == "function"
        assert "name" in schema["function"]
        assert "parameters" in schema["function"]

    def test_invoke(self):
        def multiply(x: int, y: int) -> int:
            return x * y

        tool = make_tool(multiply)
        assert tool.invoke({"x": 3, "y": 4}) == 12

    def test_explicit_parameters_override(self):
        params = {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        }

        def read_file(path):
            return ""

        tool = make_tool(read_file, description="Read a file", parameters=params)
        assert tool.parameters == params

    def test_explicit_description_override(self):
        def fn(x: int) -> int:
            """Original doc."""
            return x

        tool = make_tool(fn, description="Custom description")
        assert tool.description == "Custom description"


# LLMClient (litellm gemockt)

class TestLLMClient:
    @patch("src.llm.client.litellm.completion")
    def test_chat_returns_text_and_tokens(self, mock_comp):
        mock_comp.return_value = _fake_completion("Hello!", tokens_in=5, tokens_out=3)
        client = LLMClient(_CFG)
        resp = client.chat([{"role": "user", "content": "hi"}])
        assert isinstance(resp, LLMResponse)
        assert resp.text == "Hello!"
        assert resp.tokens_in == 5
        assert resp.tokens_out == 3
        assert resp.elapsed_ms >= 0

    @patch("src.llm.client.litellm.completion")
    def test_chat_json_passes_response_format(self, mock_comp):
        mock_comp.return_value = _fake_completion('{"k": 1}')
        client = LLMClient(_CFG)
        client.chat_json([{"role": "user", "content": "json"}])
        kwargs = mock_comp.call_args.kwargs
        assert kwargs.get("response_format") == {"type": "json_object"}

    @patch("src.llm.client.litellm.completion")
    def test_chat_tools_passes_tool_schemas(self, mock_comp):
        mock_comp.return_value = _fake_completion("ok")

        def noop(x: str) -> str:
            return x

        tool = make_tool(noop, description="noop")
        client = LLMClient(_CFG)
        client.chat_tools([{"role": "user", "content": "go"}], [tool])
        kwargs = mock_comp.call_args.kwargs
        assert "tools" in kwargs
        assert kwargs["tools"][0]["function"]["name"] == "noop"

    @patch("src.llm.client.litellm.completion")
    def test_tool_calls_parsed_correctly(self, mock_comp):
        mock_comp.return_value = _fake_tool_response("my_fn", {"arg": "val"})

        def my_fn(arg: str) -> str:
            return arg

        client = LLMClient(_CFG)
        resp = client.chat_tools([{"role": "user", "content": "call"}], [make_tool(my_fn)])
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0].name == "my_fn"
        assert resp.tool_calls[0].arguments == {"arg": "val"}
        assert resp.tool_calls[0].id == "call_1"

    @patch("src.llm.client.litellm.completion")
    def test_trace_written_on_chat(self, mock_comp, tmp_path):
        mock_comp.return_value = _fake_completion("Hi")
        trace = TraceLogger(path=tmp_path / "trace.jsonl")
        client = LLMClient(_CFG, trace=trace)
        client.chat([{"role": "user", "content": "hello"}])
        lines = (tmp_path / "trace.jsonl").read_text().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert "tokens_in" in entry
        assert "elapsed_ms" in entry
        assert "model" in entry

    def test_model_string_uses_backend_prefix(self):
        assert _build_model_str(_CFG) == "ollama/qwen2.5:14b"

    @patch("src.llm.client.litellm.completion")
    def test_ollama_passes_num_ctx_in_options(self, mock_comp):
        mock_comp.return_value = _fake_completion("ok")
        client = LLMClient(_CFG)
        client.chat([{"role": "user", "content": "hi"}])
        kwargs = mock_comp.call_args.kwargs
        assert "options" in kwargs
        assert kwargs["options"]["num_ctx"] == _CFG.num_ctx

    @patch("src.llm.client.litellm.completion")
    def test_ollama_passes_api_base(self, mock_comp):
        mock_comp.return_value = _fake_completion("ok")
        client = LLMClient(_CFG)
        client.chat([{"role": "user", "content": "hi"}])
        kwargs = mock_comp.call_args.kwargs
        assert kwargs.get("api_base") == _CFG.base_url

    @patch("src.llm.client.litellm.completion")
    def test_no_tool_calls_returns_empty_list(self, mock_comp):
        mock_comp.return_value = _fake_completion("plain text")
        client = LLMClient(_CFG)
        resp = client.chat([{"role": "user", "content": "hi"}])
        assert resp.tool_calls == []

    @patch("src.llm.client.litellm.completion")
    def test_empty_choices_returns_empty_response(self, mock_comp):
        fake = MagicMock()
        fake.choices = []
        fake.usage = None
        mock_comp.return_value = fake
        client = LLMClient(_CFG)
        resp = client.chat([{"role": "user", "content": "hi"}])
        assert resp.text is None
        assert resp.tool_calls == []
        assert resp.tokens_in == 0
        assert resp.tokens_out == 0

    @patch("src.llm.client.litellm.completion")
    def test_transient_error_retries_then_succeeds(self, mock_comp):
        import litellm as _litellm
        mock_comp.side_effect = [
            _litellm.ServiceUnavailableError(message="503", llm_provider="gemini", model="x"),
            _fake_completion("ok"),
        ]
        client = LLMClient(_CFG)
        with patch("src.llm.client.time.sleep"):
            resp = client.chat([{"role": "user", "content": "hi"}])
        assert resp.text == "ok"
        assert mock_comp.call_count == 2

    @patch("src.llm.client.litellm.completion")
    def test_transient_error_exhausted_raises(self, mock_comp):
        import litellm as _litellm
        mock_comp.side_effect = _litellm.ServiceUnavailableError(
            message="503", llm_provider="gemini", model="x"
        )
        client = LLMClient(_CFG)
        with patch("src.llm.client.time.sleep"):
            with pytest.raises(_litellm.ServiceUnavailableError):
                client.chat([{"role": "user", "content": "hi"}])
        from src.llm.client import _MAX_RETRIES
        assert mock_comp.call_count == _MAX_RETRIES


# _try_parse

class TestTryParse:
    def test_valid_json(self):
        obj, err = _try_parse('{"a": 1}')
        assert obj == {"a": 1} and err is None

    def test_invalid_json(self):
        obj, err = _try_parse("not json at all")
        assert obj is None and err is not None

    def test_empty_string(self):
        obj, err = _try_parse("")
        assert obj is None and err is not None

    def test_none_input(self):
        obj, err = _try_parse(None)
        assert obj is None and err is not None

    def test_strips_json_fence(self):
        text = "```json\n{\"x\": 42}\n```"
        obj, err = _try_parse(text)
        assert obj == {"x": 42} and err is None

    def test_strips_plain_fence(self):
        text = "```\n{\"y\": 7}\n```"
        obj, err = _try_parse(text)
        assert obj == {"y": 7} and err is None

    def test_list_json(self):
        obj, err = _try_parse("[1, 2, 3]")
        assert obj == [1, 2, 3] and err is None


# chat_json_with_retry

class TestChatJsonWithRetry:
    @patch("src.llm.client.litellm.completion")
    def test_first_attempt_succeeds_no_retry(self, mock_comp):
        mock_comp.return_value = _fake_completion('{"ok": true}')
        client = LLMClient(_CFG)
        obj, _ = chat_json_with_retry(client, [{"role": "user", "content": "json"}])
        assert obj == {"ok": True}
        assert mock_comp.call_count == 1

    @patch("src.llm.client.litellm.completion")
    def test_retries_on_bad_json_and_succeeds(self, mock_comp):
        mock_comp.side_effect = [
            _fake_completion("not json"),
            _fake_completion('{"fixed": true}'),
        ]
        client = LLMClient(_CFG)
        obj, _ = chat_json_with_retry(client, [{"role": "user", "content": "json"}])
        assert obj == {"fixed": True}
        assert mock_comp.call_count == 2

    @patch("src.llm.client.litellm.completion")
    def test_returns_none_on_double_failure(self, mock_comp):
        mock_comp.side_effect = [
            _fake_completion("bad1"),
            _fake_completion("bad2"),
        ]
        client = LLMClient(_CFG)
        obj, _ = chat_json_with_retry(client, [{"role": "user", "content": "json"}])
        assert obj is None
        assert mock_comp.call_count == 2

    @patch("src.llm.client.litellm.completion")
    def test_corrective_message_mentions_json(self, mock_comp):
        mock_comp.side_effect = [
            _fake_completion("oops"),
            _fake_completion("{}"),
        ]
        client = LLMClient(_CFG)
        chat_json_with_retry(client, [{"role": "user", "content": "x"}])
        retry_messages = mock_comp.call_args_list[1].kwargs["messages"]
        last_user = next(m for m in reversed(retry_messages) if m["role"] == "user")
        assert "not valid JSON" in last_user["content"]

    @patch("src.llm.client.litellm.completion")
    def test_accepts_markdown_fenced_json(self, mock_comp):
        mock_comp.return_value = _fake_completion("```json\n{\"a\": 1}\n```")
        client = LLMClient(_CFG)
        obj, _ = chat_json_with_retry(client, [{"role": "user", "content": "x"}])
        assert obj == {"a": 1}
        assert mock_comp.call_count == 1


# chat_tools_with_retry

class TestChatToolsWithRetry:
    def _make_fn_tool(self):
        def fn(x: str) -> str:
            return x

        return make_tool(fn)

    @patch("src.llm.client.litellm.completion")
    def test_valid_call_no_retry(self, mock_comp):
        tool = self._make_fn_tool()
        mock_comp.return_value = _fake_tool_response("fn", {"x": "hello"})
        client = LLMClient(_CFG)
        resp = chat_tools_with_retry(client, [{"role": "user", "content": "go"}], [tool])
        assert resp.tool_calls[0].name == "fn"
        assert mock_comp.call_count == 1

    @patch("src.llm.client.litellm.completion")
    def test_retries_when_no_tool_calls(self, mock_comp):
        tool = self._make_fn_tool()
        mock_comp.side_effect = [
            _fake_completion("I'll help you"),
            _fake_tool_response("fn", {"x": "fixed"}),
        ]
        client = LLMClient(_CFG)
        resp = chat_tools_with_retry(client, [{"role": "user", "content": "use tool"}], [tool])
        assert mock_comp.call_count == 2
        assert resp.tool_calls[0].name == "fn"

    @patch("src.llm.client.litellm.completion")
    def test_retries_on_unknown_tool_name(self, mock_comp):
        tool = self._make_fn_tool()
        mock_comp.side_effect = [
            _fake_tool_response("nonexistent_tool", {"x": "v"}),
            _fake_tool_response("fn", {"x": "ok"}),
        ]
        client = LLMClient(_CFG)
        resp = chat_tools_with_retry(client, [{"role": "user", "content": "use tool"}], [tool])
        assert mock_comp.call_count == 2
        assert resp.tool_calls[0].name == "fn"

    @patch("src.llm.client.litellm.completion")
    def test_corrective_message_included_in_retry(self, mock_comp):
        tool = self._make_fn_tool()
        mock_comp.side_effect = [
            _fake_completion("text, no tool call"),
            _fake_tool_response("fn", {"x": "ok"}),
        ]
        client = LLMClient(_CFG)
        chat_tools_with_retry(client, [{"role": "user", "content": "go"}], [tool])
        retry_messages = mock_comp.call_args_list[1].kwargs["messages"]
        last_user = next(m for m in reversed(retry_messages) if m["role"] == "user")
        assert "tool" in last_user["content"].lower()
