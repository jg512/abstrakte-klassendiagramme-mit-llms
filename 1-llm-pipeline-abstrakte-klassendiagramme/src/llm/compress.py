from __future__ import annotations

import logging

log = logging.getLogger(__name__)

_COMPRESSION_PROMPT = (
    "You are a summarization assistant. The user will provide a conversation history "
    "from an AI agent that is building an abstract UML class diagram. "
    "Produce a concise summary (under 400 words) that preserves all information "
    "the agent needs to continue its work: which nodes and edges are currently in "
    "the diagram, which classes/files have been inspected, what decisions were made "
    "and why, and any remaining open questions or next steps."
)


def compress_history(
    client: object,
    messages: list[dict],
    turn_num: int,
) -> list[dict]:
    """Ersetzt die wachsende Nachrichtenliste durch die System-Nachricht und eine Zusammenfassung als User-Nachricht.

    Schlägt die Kompression fehl, kommen die Nachrichten unverändert zurück.
    """
    if len(messages) < 3:
        return messages

    system_msg = messages[0]

    history_text = "\n\n".join(
        f"[{m['role'].upper()}]: {_content_str(m)}"
        for m in messages[1:]
    )

    summary_request = [
        {"role": "system", "content": _COMPRESSION_PROMPT},
        {"role": "user", "content": f"Conversation history to summarize:\n\n{history_text}"},
    ]

    try:
        resp = client.chat(summary_request)  # type: ignore[attr-defined]
        summary = (resp.text or "").strip()
        if not summary:
            log.warning("[compress] empty summary at turn %d — keeping full history", turn_num)
            return messages
        log.info("[compress] history compressed at turn %d (%d→2 messages)", turn_num, len(messages))
        return [
            system_msg,
            {"role": "user", "content": f"[History summary after turn {turn_num}]\n{summary}"},
        ]
    except Exception as exc:
        log.warning("[compress] compression failed at turn %d: %s — keeping full history", turn_num, exc)
        return messages


def _content_str(msg: dict) -> str:
    content = msg.get("content") or ""
    tool_calls = msg.get("tool_calls")
    if tool_calls:
        calls = ", ".join(
            f"{tc['function']['name']}({tc['function']['arguments'][:60]})"
            for tc in tool_calls
        )
        return f"{content} [tool_calls: {calls}]" if content else f"[tool_calls: {calls}]"
    return str(content)[:500]
