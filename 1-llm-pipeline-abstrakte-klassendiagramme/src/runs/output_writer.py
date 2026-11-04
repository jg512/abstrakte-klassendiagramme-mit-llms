from __future__ import annotations

import dataclasses
import datetime
import json
import logging
from pathlib import Path

import yaml

from src.config.models import Config
from src.schema.graph import AbstractGraph
from src.schema.json_io import graph_to_json
from src.schema.plantuml import to_plantuml

log = logging.getLogger(__name__)


def create_run_dir(
    out_dir: str | Path,
    repo_name: str,
    method_name: str,
    batch_ts: str | None = None,
) -> Path:
    """Ausgabeordner für den Lauf anlegen und zurückgeben.

    Aufbau: <out_dir>/<batch_ts>/<repo>/<methode>/
    Alle Methoden eines Aufrufs teilen sich denselben batch_ts-Ordner.
    """
    ts = batch_ts or datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    run_dir = Path(out_dir) / ts / _safe_name(repo_name) / _safe_name(method_name)
    run_dir.mkdir(parents=True, exist_ok=True)
    log.debug("Created run directory %s", run_dir)
    return run_dir


def write_run_outputs(
    run_dir: Path,
    graph: AbstractGraph,
    config: Config,
    warnings: list[str],
    method_name: str,
    elapsed_s: float,
    incomplete: bool = False,
    cost: dict | None = None,
) -> None:
    """graph.json, diagram.puml, config.yaml, summary.md und errors.log schreiben.

    cost: optional {"llm_calls": int, "tokens_in": int, "tokens_out": int}.
    """
    (run_dir / "graph.json").write_text(
        graph_to_json(graph, indent=2), encoding="utf-8"
    )
    (run_dir / "diagram.puml").write_text(
        to_plantuml(graph), encoding="utf-8"
    )
    config_dict = dataclasses.asdict(config)
    (run_dir / "config.yaml").write_text(
        yaml.dump(config_dict, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    (run_dir / "summary.md").write_text(
        _build_summary(graph, config, method_name, elapsed_s, warnings, incomplete, cost),
        encoding="utf-8",
    )
    if warnings:
        (run_dir / "errors.log").write_text(
            "\n".join(warnings) + "\n", encoding="utf-8"
        )
    log.info(
        "Outputs written to %s (%d nodes, %d edges)",
        run_dir, len(graph.nodes), len(graph.edges),
    )


def _build_summary(
    graph: AbstractGraph,
    config: Config,
    method_name: str,
    elapsed_s: float,
    warnings: list[str],
    incomplete: bool,
    cost: dict | None = None,
) -> str:
    status = "INCOMPLETE" if incomplete else "complete"
    lines = [
        f"# Run Summary — {graph.repo} / {method_name}",
        "",
        f"- **Status:** {status}",
        f"- **Method:** {method_name}",
        f"- **Repo:** {graph.repo}",
        f"- **Model:** {config.backend}/{config.model}",
        f"- **Target nodes:** {config.target_nodes} (±{config.node_tolerance:.0%})",
        f"- **Nodes produced:** {len(graph.nodes)}",
        f"- **Edges produced:** {len(graph.edges)}",
        f"- **Elapsed:** {elapsed_s:.1f}s",
        f"- **Warnings:** {len(warnings)}",
    ]
    if cost:
        lines += [
            f"- **LLM calls:** {cost.get('llm_calls', 0)}",
            f"- **Tokens in/out:** {cost.get('tokens_in', 0)}/{cost.get('tokens_out', 0)}",
        ]
    return "\n".join(lines) + "\n"


def write_static_graph_outputs(
    out_dir: str | Path,
    repo_name: str,
    batch_ts: str,
    static_graph: AbstractGraph,
    basename: str = "pyreverse",
) -> None:
    """<basename>.json und <basename>.puml in den Repo-Ordner des Batches schreiben.

    Wird einmal pro Repo-Lauf gespeichert, außerhalb der Methodenordner, damit
    alle Methoden auf denselben unveränderten Quellgraphen verweisen können. Der
    Basisname nennt den Erzeuger (pyreverse für Python, javagraph für Java),
    damit man an den Dateien selbst sieht, woher sie kommen.
    """
    repo_dir = Path(out_dir) / batch_ts / _safe_name(repo_name)
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / f"{basename}.json").write_text(
        graph_to_json(static_graph, indent=2), encoding="utf-8"
    )
    (repo_dir / f"{basename}.puml").write_text(
        to_plantuml(static_graph), encoding="utf-8"
    )
    if static_graph.diagnostics:
        (repo_dir / f"{basename}.diagnostics.json").write_text(
            json.dumps([
                {
                    "code": d.code,
                    "severity": d.severity,
                    "message": d.message,
                    "source": d.source,
                    "reference": d.reference,
                    "candidates": d.candidates,
                }
                for d in static_graph.diagnostics
            ], indent=2) + "\n",
            encoding="utf-8",
        )
    log.info(
        "Static class graph written to %s/%s.* (%d nodes, %d edges)",
        repo_dir, basename, len(static_graph.nodes), len(static_graph.edges),
    )


def _safe_name(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
