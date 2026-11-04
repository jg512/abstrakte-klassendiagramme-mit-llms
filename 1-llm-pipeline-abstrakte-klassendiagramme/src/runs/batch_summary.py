from __future__ import annotations

import datetime
import math
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RunRecord:
    repo: str
    method: str
    run_dir: Path
    node_count: int
    edge_count: int
    elapsed_s: float
    warnings: int
    incomplete: bool
    # Kosten des ganzen Laufs inklusive Cleanup, für den Kostenvergleich.
    llm_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    # Ausgabe des Drivers vor dem Cleanup. Der Cleanup kann Inhalt hinzufügen oder
    # entfernen. Deshalb müssen sich die Varianten auch danach bewerten lassen, was
    # die Strategie selbst erzeugt hat.
    raw_node_count: int = 0
    raw_edge_count: int = 0


def write_batch_summary(out_dir: Path, records: list[RunRecord]) -> Path:
    """batch_summary.md nach out_dir schreiben und den Pfad zurückgeben."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "batch_summary.md"
    path.write_text(_build(records), encoding="utf-8")
    return path


def write_experiment_summary(
    experiment_dir: Path,
    seed_records: dict[int, list[RunRecord]],
) -> Path:
    """experiment_summary.md schreiben, das die Läufe über die Seeds hinweg vergleicht."""
    experiment_dir.mkdir(parents=True, exist_ok=True)
    path = experiment_dir / "experiment_summary.md"
    path.write_text(_build_experiment(seed_records), encoding="utf-8")
    return path


def _build_experiment(seed_records: dict[int, list[RunRecord]]) -> str:
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    seeds = sorted(seed_records.keys())

    lines = [
        "# Experiment Summary",
        "",
        f"Generated: {ts}",
        f"Seeds tested: {', '.join(str(s) for s in seeds)}",
        "",
    ]

    # Alle Paare (repo, methode) einsammeln
    combos: dict[tuple[str, str], dict[int, RunRecord]] = {}
    for seed, records in seed_records.items():
        for r in records:
            key = (r.repo, r.method)
            combos.setdefault(key, {})[seed] = r

    lines += [
        "## Per-run Results",
        "",
        "| Repo | Method | Seed | Nodes | Edges | Pre-cleanup n/e | Elapsed (s) | Tokens in/out | Status |",
        "|------|--------|------|-------|-------|-----------------|-------------|---------------|--------|",
    ]
    for (repo, method), by_seed in sorted(combos.items()):
        for seed in seeds:
            r = by_seed.get(seed)
            if r is None:
                lines.append(f"| {repo} | {method} | {seed} | — | — | — | — | — | MISSING |")
            else:
                status = "INCOMPLETE" if r.incomplete else "ok"
                lines.append(
                    f"| {repo} | {method} | {seed} | {r.node_count} | {r.edge_count}"
                    f" | {r.raw_node_count}/{r.raw_edge_count}"
                    f" | {r.elapsed_s:.1f} | {r.tokens_in}/{r.tokens_out} | {status} |"
                )
    lines.append("")

    lines += [
        "## Aggregate Statistics",
        "",
        "| Repo | Method | Nodes mean | Nodes std | Edges mean | Raw nodes mean | Raw edges mean | Elapsed mean (s) | Tokens mean | Stable? |",
        "|------|--------|-----------|-----------|-----------|----------------|----------------|-----------------|-------------|---------|",
    ]
    for (repo, method), by_seed in sorted(combos.items()):
        complete = [r for r in by_seed.values() if not r.incomplete]
        if not complete:
            lines.append(f"| {repo} | {method} | — | — | — | — | — | — | — | — |")
            continue
        node_counts = [r.node_count for r in complete]
        edge_counts = [r.edge_count for r in complete]
        raw_nodes = [r.raw_node_count for r in complete]
        raw_edges = [r.raw_edge_count for r in complete]
        elapsed = [r.elapsed_s for r in complete]
        tokens = [r.tokens_in + r.tokens_out for r in complete]
        node_mean = sum(node_counts) / len(node_counts)
        node_std = math.sqrt(sum((x - node_mean) ** 2 for x in node_counts) / len(node_counts))
        edge_mean = sum(edge_counts) / len(edge_counts)
        raw_node_mean = sum(raw_nodes) / len(raw_nodes)
        raw_edge_mean = sum(raw_edges) / len(raw_edges)
        elapsed_mean = sum(elapsed) / len(elapsed)
        tokens_mean = sum(tokens) / len(tokens)
        stable = "yes" if node_mean == 0 or node_std / node_mean <= 0.2 else "NO"
        lines.append(
            f"| {repo} | {method} | {node_mean:.1f} | {node_std:.1f}"
            f" | {edge_mean:.1f} | {raw_node_mean:.1f} | {raw_edge_mean:.1f}"
            f" | {elapsed_mean:.1f} | {tokens_mean:.0f} | {stable} |"
        )
    lines.append("")

    return "\n".join(lines)


def _build(records: list[RunRecord]) -> str:
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# Batch Summary",
        "",
        f"Generated: {ts}",
        f"Total runs: {len(records)}",
        "",
    ]

    complete = [r for r in records if not r.incomplete]
    failed = [r for r in records if r.incomplete]

    lines += [f"- Complete: {len(complete)}", f"- Failed/incomplete: {len(failed)}", ""]

    if records:
        lines += [
            "## Results",
            "",
            "| Repo | Method | Nodes | Edges | Pre-cleanup n/e | Elapsed (s) | LLM calls | Tokens in/out | Warnings | Status |",
            "|------|--------|-------|-------|-----------------|-------------|-----------|---------------|----------|--------|",
        ]
        for r in records:
            status = "INCOMPLETE" if r.incomplete else "ok"
            lines.append(
                f"| {r.repo} | {r.method} | {r.node_count} | {r.edge_count} "
                f"| {r.raw_node_count}/{r.raw_edge_count} "
                f"| {r.elapsed_s:.1f} | {r.llm_calls} | {r.tokens_in}/{r.tokens_out} "
                f"| {r.warnings} | {status} |"
            )
        lines.append("")

    if failed:
        lines += ["## Failed runs", ""]
        for r in failed:
            lines.append(f"- `{r.run_dir.name}` — {r.repo}/{r.method}")
        lines.append("")

    return "\n".join(lines)
