from __future__ import annotations

import logging
from pathlib import Path

from src.llm.client import LLMClient
from src.llm.retry import chat_json_with_retry
from src.parsing.code_graph import CodeGraph
from src.prompts.loader import load_prompt

log = logging.getLogger(__name__)

_DEFAULT_TARGET = 20
_MIN_TARGET = 5
_MAX_TARGET = 50


def decide_target_nodes(
    client: LLMClient,
    code_graph: CodeGraph,
    loc: int,
    prompts_dir: Path | None = None,
) -> int:
    """Das LLM anhand von Kennzahlen des Codes entscheiden lassen, wie viele Knoten das Diagramm haben soll.

    Gibt eine Ganzzahl zwischen _MIN_TARGET und _MAX_TARGET zurück. Bei jedem Fehler wird _DEFAULT_TARGET genommen.
    """
    _, template = load_prompt("auto_target.txt", prompts_dir)

    packages = sorted({cls.module.split(".")[0] for cls in code_graph.classes})
    stats = (
        f"repo: {code_graph.repo}\n"
        f"files: {len(code_graph.source_files)}\n"
        f"classes: {len(code_graph.classes)}\n"
        f"functions: {len(code_graph.functions)}\n"
        f"loc: {loc}\n"
        f"top-level packages: {len(packages)} ({', '.join(packages[:10])})"
    )

    prompt = _fill(template, stats=stats,
                   language=_language_label(code_graph.language))
    messages = [{"role": "user", "content": prompt}]

    obj, _ = chat_json_with_retry(client, messages)

    if obj is None or not isinstance(obj, dict):
        log.warning("[auto-target] LLM parse failed — using default %d", _DEFAULT_TARGET)
        return _DEFAULT_TARGET

    raw = obj.get("target_nodes")
    if not isinstance(raw, int):
        log.warning("[auto-target] unexpected value %r — using default %d", raw, _DEFAULT_TARGET)
        return _DEFAULT_TARGET

    clamped = max(_MIN_TARGET, min(_MAX_TARGET, raw))
    if clamped != raw:
        log.info("[auto-target] clamped %d → %d", raw, clamped)
    log.info("[auto-target] decided target_nodes=%d for %s", clamped, code_graph.repo)
    return clamped


def _language_label(language: str) -> str:
    return {"python": "Python", "java": "Java"}.get(language, str(language).capitalize())


def _fill(template: str, **kwargs: str) -> str:
    """Vorlage per str.replace füllen, damit geschweifte Klammern in den Werten nicht stören."""
    for key, value in kwargs.items():
        template = template.replace(f"{{{key}}}", value)
    return template
