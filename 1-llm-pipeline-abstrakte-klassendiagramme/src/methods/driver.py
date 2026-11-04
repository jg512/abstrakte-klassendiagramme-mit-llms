"""Der Driver, über den alle Varianten laufen.

Alle acht Varianten (siehe variants.py) benutzen dieselbe Tool-Schleife, mit
denselben Prompts, Budgets, Abbruchbedingungen und derselben Prüfung der
Ausgabe. Was eine Variante ausmacht, steht allein in ihrer Einstellung: womit
der Graph startet, welcher Kontext in der ersten Nachricht steht, ob das
Modell den Quelltext lesen darf und ob der Lauf nach Clustern des
Importgraphen aufgeteilt wird.
"""
from __future__ import annotations

import copy
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.llm.client import LLMClient
from src.llm.compress import compress_history
from src.llm.retry import chat_tools_with_retry
from src.llm.tokens import estimate_tokens
from src.methods.clustering import cluster_modules, inter_cluster_edges, naive_merge
from src.methods.toolbox import build_tools
from src.methods.variants import Variant
from src.parsing.code_graph import CodeGraph
from src.prompts.loader import load_prompt
from src.schema.graph import AbstractGraph
from src.schema.json_io import graph_to_dict
from src.schema.validator import validate

if TYPE_CHECKING:
    from src.runs.research import ResearchWriter

log = logging.getLogger(__name__)

# Die Schleife fügt einmal eine Nachricht "jetzt abschließen" ein, sobald das
# restliche Budget nur noch für etwa zwei normale Züge reicht. Sonst sehen die
# Modelle nicht, wie viel noch übrig ist, und der Lauf endet oft mitten im
# Erkunden, bevor der Graph ausgegeben ist. Ein Auslöser nach verbrauchtem
# Anteil kam zu spät. Weil der Verlauf jedes Mal mitgeschickt wird, kosten späte
# Züge viele Token, und gebündelte Tool-Calls können eine kleine Aufrufgrenze in
# einem einzigen Zug überschreiten.
LOW_BUDGET_TURNS = 2.0          # auslösen, wenn die restlichen Token < dieser Faktor mal Kosten des letzten Zugs
LOW_BUDGET_REMAINING = 0.25     # ... oder wenn von einem der beiden Budgets nur noch dieser Anteil übrig ist

# Hat eine Phase höchstens so viele Tool-Calls im Budget, steht schon in der
# ersten User-Nachricht, dass das Modell gleich im ersten Zug den Graphen
# bearbeiten soll. Eine Warnung mitten im Lauf käme zu spät, wenn ein einziger
# gebündelter Zug das ganze Budget verbrauchen kann.
SMALL_BUDGET_CALLS = 10

# Jeder Teillauf eines Clusters bekommt mindestens so viele Tool-Calls und
# Token, auch wenn sein Anteil nach Größe kleiner wäre. Mit 2 Aufrufen und 4k
# Token reicht es nicht, erst nachzusehen und dann zu ändern. Kleine Cluster
# kämen dann immer leer zurück. Die Summe über den Batch kann dadurch etwas über
# dem eingestellten Budget liegen.
MIN_CLUSTER_CALLS = 6
MIN_CLUSTER_TOKENS = 8_000


@dataclass
class RunStats:
    """Kostensummen über alle Schleifenphasen eines Laufs (ohne Cleanup)."""
    tool_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0


class Driver:
    def __init__(
        self,
        client: LLMClient,
        variant: Variant,
        *,
        max_tool_calls: int = 40,
        max_tokens: int = 30_000,
        read_file_max_lines: int = 200,
        compress_every_n_turns: int = 0,
        max_cluster_size: int = 40,
        min_cluster_size: int = 3,
        synthesis_share: float = 0.25,
        node_tolerance: float = 0.2,
        context_budget: int = 24_000,
        seed: int = 42,
        prompts_dir: Path | None = None,
        research: ResearchWriter | None = None,
    ) -> None:
        self._client = client
        self._variant = variant
        self._max_tool_calls = max_tool_calls
        self._max_tokens = max_tokens
        self._read_file_max_lines = read_file_max_lines
        self._compress_every_n = compress_every_n_turns
        self._max_cluster_size = max_cluster_size
        self._min_cluster_size = min_cluster_size
        self._synthesis_share = synthesis_share
        self._node_tolerance = node_tolerance
        self._context_budget = context_budget
        self._seed = seed
        self._research = research

        _, self._system_tpl = load_prompt("driver_system.txt", prompts_dir)
        seed_frag = "driver_seed_full.txt" if variant.seed == "pyreverse" else "driver_seed_empty.txt"
        _, self._seed_instructions = load_prompt(seed_frag, prompts_dir)
        peek_frag = "driver_peek_on.txt" if variant.peek else "driver_peek_off.txt"
        _, self._peek_instructions = load_prompt(peek_frag, prompts_dir)
        _, self._phase_cluster = load_prompt("driver_phase_cluster.txt", prompts_dir)
        _, self._phase_synthesis = load_prompt("driver_phase_synthesis.txt", prompts_dir)
        _, self._seed_merged = load_prompt("driver_seed_merged.txt", prompts_dir)

        self.stats = RunStats()

    @property
    def name(self) -> str:
        return self._variant.name

    def run(
        self,
        code_graph: CodeGraph,
        target_nodes: int | None,
        max_nodes: int | None = None,
    ) -> AbstractGraph:
        self.stats = RunStats()
        if self._variant.needs_pyreverse and code_graph.pyreverse_graph is None:
            log.warning("[%s] pyreverse graph unavailable for %s", self.name, code_graph.repo)
            return AbstractGraph(repo=code_graph.repo, target_nodes=target_nodes)

        if self._variant.decomposition == "per_cluster":
            graph = self._run_clustered(code_graph, target_nodes, max_nodes)
        else:
            graph = self._seed_graph(code_graph, target_nodes)
            context = self._static_context(code_graph)
            self._run_loop(
                code_graph, graph, context, target_nodes,
                max_nodes=max_nodes,
                max_tool_calls=self._max_tool_calls,
                max_tokens=self._max_tokens,
                phase="main",
            )

        graph, val_warnings = validate(
            graph, target_nodes, self._node_tolerance, max_nodes=max_nodes
        )
        for w in val_warnings:
            log.debug("[%s] validator: %s", self.name, w)

        log.info("[%s] done: %d nodes, %d edges", self.name, len(graph.nodes), len(graph.edges))
        return graph

    # Startgraph und statischer Kontext (die beiden Informationsachsen)

    def _seed_graph(self, code_graph: CodeGraph, target_nodes: int | None) -> AbstractGraph:
        if self._variant.seed == "pyreverse":
            graph = copy.deepcopy(code_graph.pyreverse_graph)
            graph.target_nodes = target_nodes
            log.info(
                "[%s] seeded with pyreverse graph: %d nodes, %d edges",
                self.name, len(graph.nodes), len(graph.edges),
            )
            return graph
        return AbstractGraph(repo=code_graph.repo, target_nodes=target_nodes)

    def _static_context(self, code_graph: CodeGraph) -> dict:
        if self._variant.context == "graph":
            return {
                "representation": "full pyreverse class graph",
                "graph": graph_to_dict(code_graph.pyreverse_graph),
            }
        return {
            "representation": "package overview",
            "overview": _overview(code_graph),
        }

    # Die Tool-Schleife

    def _run_loop(
        self,
        code_graph: CodeGraph,
        graph: AbstractGraph,
        context: dict,
        target_nodes: int | None,
        *,
        max_tool_calls: int,
        max_tokens: int,
        phase: str,
        max_nodes: int | None = None,
        module_scope: set[str] | None = None,
        phase_instructions: str = "",
        seed_instructions: str | None = None,
    ) -> None:
        if target_nodes is not None:
            tolerance = max(1, int(target_nodes * self._node_tolerance))
            size_instructions = f"Target node count: {target_nodes} (±{tolerance})."
        else:
            tolerance = None
            size_instructions = (
                "Node count: open — choose the smallest graph that captures "
                "the core architecture; do not pad it out."
            )
        if max_nodes is not None:
            size_instructions += f" Hard cap: {max_nodes} nodes."

        system_prompt = _fill(
            self._system_tpl,
            seed_instructions=(seed_instructions or self._seed_instructions).strip(),
            peek_instructions=self._peek_instructions.strip(),
            phase_instructions=phase_instructions.strip(),
            size_instructions=size_instructions,
            max_tool_calls=str(max_tool_calls),
            max_tokens=str(max_tokens),
            language=_language_label(code_graph.language),
        )
        if self._research:
            self._research.save_prompt(f"{phase}_system.txt", system_prompt)

        context_json = json.dumps(context, indent=2)
        user_msg = f"Static context:\n\n{context_json}\n\nBegin."
        if max_tool_calls <= SMALL_BUDGET_CALLS:
            user_msg = (
                f"NOTE: this phase's budget is only {max_tool_calls} tool calls — "
                "edit the graph starting with your very first turn.\n\n"
            ) + user_msg
        estimated = estimate_tokens(system_prompt + user_msg)
        if estimated > self._context_budget:
            log.warning(
                "[%s/%s] initial context ~%d tokens exceeds budget %d",
                self.name, phase, estimated, self._context_budget,
            )

        finished = [False]
        tools = build_tools(
            code_graph, graph, finished,
            peek=self._variant.peek,
            read_file_max_lines=self._read_file_max_lines,
            module_scope=module_scope,
            phase=phase,
            research=self._research,
            target_nodes=target_nodes,
            node_tolerance=tolerance,
            max_nodes=max_nodes,
        )
        tool_lookup = {t.name: t for t in tools}

        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ]

        self._client.set_chunk_meta({"phase": phase})
        tool_calls_used = 0
        tokens_in = 0
        tokens_out = 0
        warned_low_budget = False

        while not finished[0]:
            if tool_calls_used >= max_tool_calls:
                log.warning("[%s/%s] tool call budget exhausted (%d) — returning partial graph",
                            self.name, phase, max_tool_calls)
                break
            if tokens_in + tokens_out >= max_tokens:
                log.warning("[%s/%s] token budget exhausted (%d) — returning partial graph",
                            self.name, phase, max_tokens)
                break

            resp = chat_tools_with_retry(self._client, messages, tools)
            tokens_in += resp.tokens_in
            tokens_out += resp.tokens_out

            if not resp.tool_calls:
                log.warning("[%s/%s] no tool calls returned after retry — stopping", self.name, phase)
                break

            asst_msg: dict[str, Any] = {
                "role": "assistant",
                "content": resp.text,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in resp.tool_calls
                ],
            }
            messages.append(asst_msg)

            for tc in resp.tool_calls:
                tool_calls_used += 1
                tool = tool_lookup.get(tc.name)
                if tool is None:
                    result_text = f"Unknown tool: {tc.name}"
                    log.warning("[%s/%s] unknown tool %r", self.name, phase, tc.name)
                else:
                    try:
                        result = tool.invoke(tc.arguments)
                        result_text = json.dumps(result) if not isinstance(result, str) else result
                    except Exception as exc:
                        result_text = f"Tool error: {exc}"
                        log.warning("[%s/%s] tool %r raised: %s", self.name, phase, tc.name, exc)

                log.info("[%s/%s] tool=%s args=%s → %s",
                         self.name, phase, tc.name, _brief(tc.arguments), result_text[:80])
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_text,
                })

                if finished[0]:
                    break

            spent_tokens = tokens_in + tokens_out
            last_turn_cost = resp.tokens_in + resp.tokens_out
            remaining_tokens = max_tokens - spent_tokens
            remaining_calls = max_tool_calls - tool_calls_used
            if (
                not warned_low_budget
                and not finished[0]
                and (
                    remaining_tokens < max(
                        LOW_BUDGET_TURNS * last_turn_cost,
                        LOW_BUDGET_REMAINING * max_tokens,
                    )
                    or remaining_calls <= max(2, round(LOW_BUDGET_REMAINING * max_tool_calls))
                )
            ):
                warned_low_budget = True
                messages.append({
                    "role": "user",
                    "content": (
                        f"[budget] Only ~{max(0, remaining_tokens)} tokens and "
                        f"{max(0, remaining_calls)} tool calls remain — about one "
                        "or two turns. Stop exploring. Finalize the graph now: make "
                        "any remaining edits in one batched turn, then call "
                        "emit_diagram."
                    ),
                })
                log.info("[%s/%s] low-budget warning injected (%d tokens, %d calls spent)",
                         self.name, phase, spent_tokens, tool_calls_used)

            if (
                self._compress_every_n > 0
                and tool_calls_used > 0
                and tool_calls_used % self._compress_every_n == 0
                and not finished[0]
            ):
                messages = compress_history(self._client, messages, tool_calls_used)

        self._client.set_chunk_meta(None)
        self.stats.tool_calls += tool_calls_used
        self.stats.tokens_in += tokens_in
        self.stats.tokens_out += tokens_out
        log.info(
            "[%s/%s] loop done: %d nodes, %d edges, %d tool calls, %d tokens",
            self.name, phase, len(graph.nodes), len(graph.edges),
            tool_calls_used, tokens_in + tokens_out,
        )

    # Zerlegung pro Cluster: Teilläufe und Synthese in derselben Schleife

    def _run_clustered(
        self,
        code_graph: CodeGraph,
        target_nodes: int | None,
        max_nodes: int | None = None,
    ) -> AbstractGraph:
        clusters = cluster_modules(
            code_graph,
            max_cluster_size=self._max_cluster_size,
            min_cluster_size=self._min_cluster_size,
            seed=self._seed,
        )
        if not clusters:
            log.warning("[%s] no clusters produced — returning empty graph", self.name)
            return AbstractGraph(repo=code_graph.repo, target_nodes=target_nodes)

        inter_edges = inter_cluster_edges(code_graph, clusters)
        if self._research:
            self._research.save_snapshot("inter_cluster_edges.json", {"edges": inter_edges})

        # Das Gesamtbudget entspricht dem der unzerlegten Varianten: Ein Anteil für
        # die Synthese wird zurückgehalten, der Rest nach Größe auf die Cluster verteilt.
        synth_calls = max(1, int(self._max_tool_calls * self._synthesis_share))
        synth_tokens = max(1, int(self._max_tokens * self._synthesis_share))
        cluster_calls = self._max_tool_calls - synth_calls
        cluster_tokens = self._max_tokens - synth_tokens
        total_modules = sum(len(c) for c in clusters)

        log.info("[%s] %d clusters, target_nodes=%s", self.name, len(clusters), target_nodes)

        sub_graphs: list[AbstractGraph] = []
        for idx, cluster in enumerate(clusters):
            share = len(cluster) / total_modules
            # Bei offenem Ziel ist auch das Ziel jedes Clusters offen. Die Obergrenze wird
            # anteilig aufgeteilt, damit der zusammengeführte Graph die Grenze des Laufs
            # nicht überschreitet.
            c_target = None if target_nodes is None else max(1, round(target_nodes * share))
            c_max = None if max_nodes is None else max(2, round(max_nodes * share))
            sub = AbstractGraph(repo=code_graph.repo, target_nodes=c_target)
            context = {
                "representation": "cluster overview with repo-wide context",
                "repo_overview": _overview(code_graph),
                "cluster": _cluster_overview(code_graph, cluster),
            }
            log.info("[%s] cluster %d/%d: %d modules, target=%s",
                     self.name, idx + 1, len(clusters), len(cluster), c_target)
            self._run_loop(
                code_graph, sub, context, c_target,
                max_nodes=c_max,
                max_tool_calls=max(MIN_CLUSTER_CALLS, int(cluster_calls * share)),
                max_tokens=max(MIN_CLUSTER_TOKENS, int(cluster_tokens * share)),
                phase=f"cluster_{idx:02d}",
                module_scope=cluster,
                phase_instructions=self._phase_cluster,
            )
            sub_graphs.append(sub)
            if self._research:
                self._research.save_snapshot(f"cluster_{idx:02d}.json", sub, also_puml=True)

        merged = naive_merge(sub_graphs, code_graph.repo, target_nodes)
        if self._research:
            self._research.save_snapshot("merged_before_synthesis.json", merged, also_puml=True)

        context = {
            "representation": "merged cluster sub-graphs with repo-wide context",
            "repo_overview": _overview(code_graph),
            "merged_graph": graph_to_dict(merged),
            "inter_cluster_import_edges": inter_edges,
        }
        self._run_loop(
            code_graph, merged, context, target_nodes,
            max_nodes=max_nodes,
            max_tool_calls=synth_calls,
            max_tokens=synth_tokens,
            phase="synthesis",
            phase_instructions=self._phase_synthesis,
            # Der Arbeitsgraph enthält hier schon den zusammengeführten Graphen. Der
            # Seed-Text der Variante ("startet leer") würde dem widersprechen.
            seed_instructions=self._seed_merged,
        )
        return merged


# Aufbau des statischen Kontexts

def _overview(code_graph: CodeGraph) -> dict:
    """Paketbaum, qualifizierte Klassennamen pro Paket und Importkanten auf oberster Ebene.

    Die Klassennamen (nur die Namen, ohne Member und Beziehungen) sind dabei,
    damit auch Varianten ohne Peek mit echten IDs arbeiten können. Member und
    Beziehungen bleiben den reicheren Kontextstufen vorbehalten.
    """
    classes_by_pkg: dict[str, list[str]] = {}
    for cls in code_graph.classes:
        pkg = cls.module.split(".")[0]
        classes_by_pkg.setdefault(pkg, []).append(cls.qualified_name)

    edges = []
    seen: set[tuple[str, str]] = set()
    for src_pkg, targets in code_graph.package_imports.items():
        for tgt in targets:
            pair = (src_pkg, tgt)
            if pair not in seen:
                seen.add(pair)
                edges.append({"from": src_pkg, "to": tgt})

    return {
        "repo": code_graph.repo,
        "packages": sorted(classes_by_pkg.keys()),
        "classes_by_package": {k: sorted(v) for k, v in sorted(classes_by_pkg.items())},
        "import_edges": edges[:60],
        "total_classes": len(code_graph.classes),
        "total_files": len(code_graph.source_files),
    }


def _cluster_overview(code_graph: CodeGraph, cluster: set[str]) -> dict:
    """Klassen eines Clusters und seine Importkanten."""
    cls_list = [
        {
            "qualified_name": c.qualified_name,
            "module": c.module,
            "bases": c.bases,
            "method_count": len(c.methods),
        }
        for c in code_graph.classes
        if c.module in cluster
    ]
    edges = []
    seen: set[tuple[str, str]] = set()
    for src, targets in code_graph.module_imports.items():
        if src not in cluster:
            continue
        for tgt in targets:
            pair = (src, tgt)
            if pair not in seen:
                seen.add(pair)
                edges.append({"from": src, "to": tgt, "external": tgt not in cluster})
    return {
        "cluster_modules": sorted(cluster),
        "classes": cls_list,
        "import_edges": edges,
    }


def _language_label(language: str) -> str:
    """Anzeigename der Sprache für die Prompts.

    Das Modell soll wissen, um welche Sprache es geht, denn Java hat Interfaces
    und Realisierungen, Python nicht.
    """
    return {"python": "Python", "java": "Java"}.get(language, str(language).capitalize())


def _fill(template: str, **kwargs: str) -> str:
    """Füllt die Vorlage per str.replace. Geschweifte Klammern in den Werten stören dabei nicht."""
    for key, value in kwargs.items():
        template = template.replace(f"{{{key}}}", value)
    return template


def _brief(args: dict) -> str:
    s = json.dumps(args, separators=(",", ":"))
    return s[:60] + "..." if len(s) > 60 else s
