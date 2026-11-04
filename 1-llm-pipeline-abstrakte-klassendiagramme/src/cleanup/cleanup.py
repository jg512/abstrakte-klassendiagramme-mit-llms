from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from src.llm.client import LLMClient
from src.llm.retry import chat_json_with_retry
from src.llm.tokens import estimate_tokens
from src.prompts.loader import load_prompt
from src.schema.graph import AbstractGraph, Edge, Node, Package
from src.schema.json_io import graph_to_json
from src.schema.validator import validate

if TYPE_CHECKING:
    from src.runs.research import ResearchWriter

log = logging.getLogger(__name__)


class CleanupPass:
    name = "cleanup"

    def __init__(
        self,
        client: LLMClient,
        prompts_dir: Path | None = None,
        research: ResearchWriter | None = None,
        context_budget: int = 24_000,
    ) -> None:
        self._client = client
        self._research = research
        self._context_budget = context_budget
        _, self._system_prompt = load_prompt("cleanup.txt", prompts_dir)

    def run(
        self,
        graph: AbstractGraph,
        target_nodes: int | None,
        node_tolerance: float = 0.2,
        max_nodes: int | None = None,
    ) -> AbstractGraph:
        if target_nodes is not None:
            tolerance = max(1, int(target_nodes * node_tolerance))
            size_line = f"Target node count: {target_nodes} (±{tolerance})"
        else:
            size_line = (
                "Node count: open — keep the smallest graph that captures "
                "the core architecture"
            )
        if max_nodes is not None:
            size_line += f". Hard cap: {max_nodes} nodes"
        log.info("[cleanup] input: %d nodes, %d edges", len(graph.nodes), len(graph.edges))
        if self._research:
            self._research.save_prompt("system.txt", self._system_prompt)
            self._research.save_snapshot("cleanup_before.json", graph, also_puml=True)
        graph_json = graph_to_json(graph, indent=2)

        user_msg = (
            f"Graph:\n{graph_json}\n\n"
            f"{size_line}"
        )
        estimated = estimate_tokens(self._system_prompt + user_msg)
        if estimated > self._context_budget:
            log.warning(
                "[cleanup] prompt too large (~%d tokens > %d budget) — skipping",
                estimated, self._context_budget,
            )
            return graph
        messages = [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": user_msg},
        ]

        obj, _resp = chat_json_with_retry(self._client, messages)

        if obj is None or not isinstance(obj, dict):
            log.warning("[cleanup] LLM parse failed — returning original graph unchanged")
            return graph

        try:
            cleaned = _parse_graph(obj, graph.repo, target_nodes)
        except Exception as exc:
            log.warning("[cleanup] graph parse failed: %s — returning original", exc)
            return graph

        cleaned, warnings = validate(cleaned, target_nodes, node_tolerance)
        for w in warnings:
            log.debug("[cleanup] validator: %s", w)

        if self._research:
            self._research.save_snapshot("cleanup_after.json", cleaned, also_puml=True)

        log.info(
            "[cleanup] %d→%d nodes, %d→%d edges",
            len(graph.nodes), len(cleaned.nodes),
            len(graph.edges), len(cleaned.edges),
        )
        return cleaned


def _parse_graph(obj: dict, repo: str, target_nodes: int | None) -> AbstractGraph:
    packages = [
        Package(name=p["name"], parent=p.get("parent"))
        for p in obj.get("packages", [])
        if isinstance(p, dict) and p.get("name")
    ]
    nodes = [
        Node(
            id=n["id"],
            name=n.get("name") or n["id"].split(".")[-1],
            package=n.get("package") or "",
            stereotype=n.get("stereotype"),
            attributes=list(n.get("attributes") or []),
            methods=list(n.get("methods") or []),
            source_file=n.get("source_file"),
            source_line=n.get("source_line"),
        )
        for n in obj.get("nodes", [])
        if isinstance(n, dict) and n.get("id")
    ]
    edges = [
        Edge(
            source=e["source"],
            target=e["target"],
            type=e.get("type", "dependency"),
            source_card=e.get("source_card"),
            target_card=e.get("target_card"),
            label=e.get("label"),
        )
        for e in obj.get("edges", [])
        if isinstance(e, dict) and e.get("source") and e.get("target")
    ]
    return AbstractGraph(
        repo=repo,
        target_nodes=target_nodes,
        packages=packages,
        nodes=nodes,
        edges=edges,
    )
