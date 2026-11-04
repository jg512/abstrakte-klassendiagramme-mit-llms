"""Einen einzelnen LLM-Aufruf aus einer trace.jsonl noch einmal abschicken.

Aufruf:
    python -m src.tools.replay --trace runs/<lauf>/trace.jsonl --step 4

Lädt Eintrag Nummer <step> (ab 0 gezählt) aus dem Trace und schickt die dort
aufgezeichneten Nachrichten und Tools noch einmal ab. Modell und Backend kommen
aus der aktuellen Konfiguration (oder der mit --config angegebenen). Die
Prompt-Dateien werden dabei nicht neu gelesen, geänderte Prompts wirken sich
also nicht aus. Danach wird die Antwort ausgegeben. Das geht nur, wenn der Lauf
mit trace_messages: true aufgezeichnet wurde.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path


def load_trace(trace_path: Path) -> list[dict]:
    entries = []
    for line in trace_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return entries


def run_replay(trace_path: Path, step: int, config_path: str | None = None) -> None:
    from src.config.loader import load_config
    from src.llm.client import LLMClient
    from src.llm.trace import TraceLogger

    entries = load_trace(trace_path)
    if not entries:
        print(f"No entries found in {trace_path}", file=sys.stderr)
        sys.exit(1)

    if step < 0 or step >= len(entries):
        print(
            f"Step {step} out of range (trace has {len(entries)} entries, indices 0–{len(entries)-1})",
            file=sys.stderr,
        )
        sys.exit(1)

    entry = entries[step]
    messages = entry.get("messages")
    if messages is None:
        print(
            f"Trace entry {step} has no 'messages' field.\n"
            "Note: the current trace format logs metadata only — full message replay\n"
            "requires the trace to include the 'messages' key.\n"
            f"Entry keys: {sorted(entry.keys())}",
            file=sys.stderr,
        )
        sys.exit(1)

    config = load_config(config_path)
    client = LLMClient(config, TraceLogger())

    tools_schema = entry.get("tools")
    if tools_schema:
        from src.llm.tools import Tool

        tools = [
            Tool(
                name=t["function"]["name"],
                description=t["function"].get("description", ""),
                parameters=t["function"].get("parameters", {}),
                fn=lambda **_: {},
            )
            for t in tools_schema
            if t.get("type") == "function"
        ]
        resp = client.chat_tools(messages, tools)
    elif entry.get("json_mode"):
        resp = client.chat_json(messages)
    else:
        resp = client.chat(messages)

    print(f"\n=== Replay: trace {trace_path.name}, step {step} ===")
    print(f"Model: {config.backend}/{config.model}")
    print(f"Tokens in/out: {resp.tokens_in}/{resp.tokens_out}  elapsed: {resp.elapsed_ms}ms\n")

    if resp.tool_calls:
        for tc in resp.tool_calls:
            print(f"[tool_call] {tc.name}({json.dumps(tc.arguments, indent=2)})")
    else:
        print(resp.text or "(empty response)")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m src.tools.replay",
        description="Replay a single LLM call from a trace.jsonl file.",
    )
    parser.add_argument("--trace", required=True, metavar="PATH", help="trace.jsonl file")
    parser.add_argument("--step", type=int, default=0, metavar="N", help="Entry index (0-based)")
    parser.add_argument("--config", metavar="PATH", help="Custom YAML config")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING)
    run_replay(Path(args.trace), args.step, args.config)


if __name__ == "__main__":
    main()
