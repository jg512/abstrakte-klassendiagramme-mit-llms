from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass

import litellm

from src.config.models import Config
from src.llm.tools import Tool, ToolCall
from src.llm.trace import TraceLogger

log = logging.getLogger(__name__)

# Erfolgs- und Debug-Ausgaben von litellm unterdrücken, Warnungen und Fehler behalten.
litellm.success_callback = []
litellm.failure_callback = []

_TRANSIENT_ERRORS = (
    litellm.ServiceUnavailableError,
    litellm.RateLimitError,
    litellm.Timeout,
    litellm.APIConnectionError,
)
_MAX_RETRIES = 10
_RETRY_BASE_DELAY = 5.0  # Sekunden; verdoppelt sich mit jedem Wiederholversuch


@dataclass
class LLMResponse:
    text: str | None
    tool_calls: list[ToolCall]
    tokens_in: int
    tokens_out: int
    elapsed_ms: int


class LLMClient:
    def __init__(self, config: Config, trace: TraceLogger | None = None) -> None:
        self._config = config
        self._trace = trace or TraceLogger()
        self._model_str = _build_model_str(config)
        self._base_kwargs = _build_base_kwargs(config)

    def chat(self, messages: list[dict]) -> LLMResponse:
        return self._call(messages)

    def chat_json(self, messages: list[dict]) -> LLMResponse:
        return self._call(messages, response_format={"type": "json_object"})

    def chat_tools(self, messages: list[dict], tools: list[Tool]) -> LLMResponse:
        return self._call(messages, tools=[t.to_litellm() for t in tools])

    # Leere Methoden, die ResearchLLMClient für die Protokollierung überschreibt.
    def set_chunk_meta(self, meta: dict | None) -> None:  # noqa: ARG002
        pass

    def mark_retry(self) -> None:
        pass

    def set_trace_context(self, ctx: dict) -> None:
        self._trace.set_context(ctx)

    def clear_trace_context(self) -> None:
        self._trace.clear_context()

    def _call(self, messages: list[dict], **extra) -> LLMResponse:
        kwargs = {**self._base_kwargs, **extra}
        t0 = time.monotonic()
        delay = _RETRY_BASE_DELAY
        for attempt in range(_MAX_RETRIES):
            try:
                response = litellm.completion(
                    model=self._model_str,
                    messages=messages,
                    **kwargs,
                )
                break
            except _TRANSIENT_ERRORS as exc:
                if attempt == _MAX_RETRIES - 1:
                    raise
                log.warning("Transient error (attempt %d/%d): %s — retrying in %.0fs",
                            attempt + 1, _MAX_RETRIES, exc, delay)
                time.sleep(delay)
                delay *= 2
        elapsed_ms = int((time.monotonic() - t0) * 1000)

        if not response.choices:
            # Gemini liefert manchmal eine leere choices-Liste als Endsignal. Das wird wie
            # eine Antwort ohne Text und ohne Tool-Calls behandelt, damit der Aufrufer
            # sauber aussteigen kann.
            log.warning("LLM returned empty choices list (model=%s) — treating as empty response", self._model_str)
            empty = LLMResponse(text=None, tool_calls=[], tokens_in=0, tokens_out=0, elapsed_ms=elapsed_ms)
            self._trace.log({
                "model": self._model_str,
                "tokens_in": 0,
                "tokens_out": 0,
                "elapsed_ms": elapsed_ms,
                "has_tool_calls": False,
            })
            return empty
        choice = response.choices[0]
        msg = choice.message
        text = msg.content
        raw_calls = msg.tool_calls if msg.tool_calls else []
        tool_calls = _parse_tool_calls(raw_calls)

        usage = response.usage
        tokens_in = (getattr(usage, "prompt_tokens", 0) or 0) if usage else 0
        tokens_out = (getattr(usage, "completion_tokens", 0) or 0) if usage else 0

        result = LLMResponse(
            text=text,
            tool_calls=tool_calls,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            elapsed_ms=elapsed_ms,
        )
        log.debug(
            "llm call done tokens_in=%d tokens_out=%d elapsed_ms=%d model=%s",
            tokens_in, tokens_out, elapsed_ms, self._model_str,
        )
        entry: dict = {
            "model": self._model_str,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "elapsed_ms": elapsed_ms,
            "has_tool_calls": bool(tool_calls),
        }
        if self._config.output.trace_messages:
            entry["messages"] = messages
            entry["tools"] = extra.get("tools")
            entry["json_mode"] = extra.get("response_format", {}).get("type") == "json_object"
        self._trace.log(entry)
        return result


def _build_model_str(config: Config) -> str:
    return f"{config.backend}/{config.model}"


def _build_base_kwargs(config: Config) -> dict:
    kwargs: dict = {
        "temperature": config.temperature,
        "seed": config.seed,
        "drop_params": True,   # Parameter, die das aktive Backend nicht kennt, stillschweigend weglassen
    }
    if config.base_url:
        kwargs["api_base"] = config.base_url
    if config.api_key_env:
        key = os.environ.get(config.api_key_env, "")
        if key:
            kwargs["api_key"] = key
    if config.backend == "ollama":
        kwargs["options"] = {"num_ctx": config.num_ctx}
    if config.request_timeout > 0:
        kwargs["timeout"] = config.request_timeout
    return kwargs


def _parse_tool_calls(raw: list) -> list[ToolCall]:
    calls = []
    for tc in raw:
        fn = tc.function
        try:
            args = (
                json.loads(fn.arguments)
                if isinstance(fn.arguments, str)
                else (fn.arguments or {})
            )
        except (json.JSONDecodeError, AttributeError):
            log.warning("Failed to parse tool call arguments: %s", getattr(fn, "arguments", None))
            args = {}
        calls.append(ToolCall(id=tc.id or "", name=fn.name or "", arguments=args))
    return calls
