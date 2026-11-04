from __future__ import annotations

import json
import logging
from typing import Any

from src.llm.client import LLMClient, LLMResponse
from src.llm.tools import Tool, ToolCall

log = logging.getLogger(__name__)

_JSON_CORRECTION = (
    "Your previous response was not valid JSON. "
    "Parser error: {error}. "
    "Please return only valid JSON with no prose and no markdown code fences."
)
_TOOL_CORRECTION = (
    "Your previous response did not contain a valid tool call. "
    "Please respond using one of the available tools with the correct argument schema."
)


def chat_json_with_retry(
    client: LLMClient,
    messages: list[dict],
) -> tuple[Any, LLMResponse]:
    """Ruft chat_json auf und wiederholt den Aufruf einmal, wenn das JSON kaputt ist.

    Gibt (geparstes Objekt, Antwort) zurück, nach zwei Fehlschlägen (None, Antwort).
    """
    resp = client.chat_json(messages)
    obj, err = _try_parse(resp.text)
    if err is None:
        return obj, resp

    log.warning("JSON parse failed on first attempt (%s) — retrying", err)
    correction = _JSON_CORRECTION.format(error=err)
    retry_messages = messages + [
        {"role": "assistant", "content": resp.text or ""},
        {"role": "user", "content": correction},
    ]
    client.mark_retry()
    resp2 = client.chat_json(retry_messages)
    obj2, err2 = _try_parse(resp2.text)
    if err2 is None:
        return obj2, resp2

    log.warning("JSON parse failed after retry (%s) — giving up", err2)
    return None, resp2


def chat_tools_with_retry(
    client: LLMClient,
    messages: list[dict],
    tools: list[Tool],
) -> LLMResponse:
    """Ruft chat_tools auf und wiederholt einmal, wenn die Antwort keine gültigen Tool-Calls enthält.

    Die zurückgegebene Antwort enthält Token und Zeit aus beiden Versuchen
    zusammen, damit die Budgetrechnung stimmt.
    """
    resp = client.chat_tools(messages, tools)
    if _has_valid_calls(resp.tool_calls, tools):
        return resp

    log.warning("No valid tool calls on first attempt — retrying")
    if resp.tool_calls:
        asst_msg: dict = {
            "role": "assistant",
            "content": None,
            "tool_calls": _serialise_calls(resp.tool_calls),
        }
    else:
        asst_msg = {"role": "assistant", "content": resp.text or ""}

    retry_messages = messages + [asst_msg, {"role": "user", "content": _TOOL_CORRECTION}]
    client.mark_retry()
    resp2 = client.chat_tools(retry_messages, tools)
    return LLMResponse(
        text=resp2.text,
        tool_calls=resp2.tool_calls,
        tokens_in=resp.tokens_in + resp2.tokens_in,
        tokens_out=resp.tokens_out + resp2.tokens_out,
        elapsed_ms=resp.elapsed_ms + resp2.elapsed_ms,
    )


def _try_parse(text: str | None) -> tuple[Any, str | None]:
    if not text:
        return None, "empty response"
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        inner = "\n".join(line for line in lines[1:] if not line.startswith("```"))
        stripped = inner.strip()
    try:
        return json.loads(stripped), None
    except json.JSONDecodeError as e:
        return None, str(e)


def _has_valid_calls(calls: list[ToolCall], tools: list[Tool]) -> bool:
    if not calls:
        return False
    known = {t.name for t in tools}
    return all(c.name in known for c in calls)


def _serialise_calls(calls: list[ToolCall]) -> list[dict]:
    return [
        {
            "id": c.id,
            "type": "function",
            "function": {"name": c.name, "arguments": json.dumps(c.arguments)},
        }
        for c in calls
    ]
