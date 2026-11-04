from __future__ import annotations

import argparse
import dataclasses
import datetime
import json
import logging
import time
from pathlib import Path

from src.cleanup.cleanup import CleanupPass
from src.config.loader import ConfigError, load_config
from src.io.filters import collect_source_files
from src.io.preflight import PreflightError, run_preflight
from src.io.repo_loader import RepoLoadError, load_repo
from src.llm.client import LLMClient
from src.llm.trace import TraceLogger
from src.methods.driver import Driver
from src.methods.variants import ALIASES, VARIANTS, resolve
from src.parsing.code_graph import CodeGraph, build_code_graph
from src.parsing.languages import LANGUAGES, resolve_language
from src.runs.batch_summary import RunRecord, write_batch_summary, write_experiment_summary
from src.runs.output_writer import create_run_dir, write_run_outputs, write_static_graph_outputs
from src.runs.research import ResearchLLMClient, ResearchWriter
from src.schema.graph import AbstractGraph
from src.schema.validator import validate
from src.targeting.auto_target import decide_target_nodes


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m src",
        description="Produce an abstract PlantUML class diagram from a source repo.",
    )
    p.add_argument("input", nargs="?", help="GitHub URL, local path, or .txt batch file")
    p.add_argument(
        "--method",
        choices=[*VARIANTS, *ALIASES, "all"],
        default="catalog",
        help="Which variant(s) to run; legacy names (m1a..m4b) map onto the "
             "variant grid (default: catalog)",
    )
    p.add_argument(
        "--language",
        choices=sorted(LANGUAGES),
        help="Source language of the input repo (default: from config, python)",
    )
    p.add_argument("--java-source-sets", choices=["auto", "all"], help="Java source-root discovery mode")
    p.add_argument(
        "--java-member-profile",
        choices=["structure", "summary", "public-api", "full"],
        help="Java member detail written into the class graph",
    )
    p.add_argument("--java-symbol-solver", choices=["source", "javac"], help="Optional JDK-backed symbol enrichment")
    p.add_argument("--java-classpath", action="append", metavar="PATH", help="Classpath entry for --java-symbol-solver javac; repeatable")
    p.add_argument("--java-method-dependencies", action="store_true", help="Include parameter/return types as dependency edges")
    p.add_argument("--java-include-generated", action="store_true", help="Include generated Java source roots in auto mode")
    p.add_argument("--no-java-external-supertypes", action="store_true", help="Omit JDK/library supertypes from the Java graph")
    p.add_argument("--java-relations", choices=["literal", "intellij"], help="Java class graph rules: literal (default) or like IntelliJ IDEA")
    p.add_argument("--java-diagram-classes", metavar="FILE", help="intellij: file with one fully qualified class name per line")
    p.add_argument("--java-ide-no-jdk", action="store_true", help="intellij: behave as if no JDK was configured")
    p.add_argument("--java-ide-no-same-package", action="store_true", help="intellij: behave as if same-package lookup failed (wrong source root)")
    p.add_argument("--config", metavar="PATH", help="Custom YAML config file")
    p.add_argument(
        "--target-nodes", metavar="N|open",
        help="Override target node count; 'open' lets the model choose the size",
    )
    p.add_argument("--no-cleanup", action="store_true", help="Skip the cleanup pass")
    p.add_argument("--out", default="runs", metavar="DIR", help="Output directory (default: runs/)")
    p.add_argument("--backend", metavar="NAME", help="LLM backend override")
    p.add_argument("--model", metavar="NAME", help="LLM model override")
    p.add_argument(
        "--verbose", action="store_true",
        help="Print one terse line per LLM call to console",
    )
    p.add_argument(
        "--cache", action="store_true",
        help="Enable parser cache (stored in dev.cache_dir, off by default)",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Stub LLM calls — tests pipeline plumbing without burning tokens",
    )
    p.add_argument(
        "--replay", metavar="TRACE",
        help="Replay a single LLM call from a trace.jsonl file",
    )
    p.add_argument(
        "--step", type=int, default=0, metavar="N",
        help="Which entry to replay from --replay trace (0-based, default: 0)",
    )
    p.add_argument(
        "--seeds", nargs="+", type=int, metavar="SEED",
        help="Run multiple times with different seeds (e.g. --seeds 42 7 123); "
             "outputs go under runs/experiment_<ts>/seed_<N>/",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # --replay ist ein eigener Modus, also direkt weiterreichen
    if args.replay:
        from src.tools.replay import run_replay
        run_replay(Path(args.replay), args.step, args.config)
        return 0

    if not args.input:
        parser.error("input is required")

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    log = logging.getLogger("cli")

    overrides: dict = {}
    if args.target_nodes is not None:
        if args.target_nodes.strip().lower() == "open":
            overrides["target_nodes"] = "open"
        else:
            try:
                overrides["target_nodes"] = int(args.target_nodes)
            except ValueError:
                parser.error(f"--target-nodes must be an integer or 'open', got {args.target_nodes!r}")
    if args.language:
        overrides["language"] = args.language
    java_overrides = {}
    if args.java_source_sets:
        java_overrides["source_sets"] = args.java_source_sets
    if args.java_member_profile:
        java_overrides["member_profile"] = args.java_member_profile
    if args.java_symbol_solver:
        java_overrides["symbol_solver"] = args.java_symbol_solver
    if args.java_classpath:
        java_overrides["classpath"] = args.java_classpath
    if args.java_method_dependencies:
        java_overrides["include_method_dependencies"] = True
    if args.java_include_generated:
        java_overrides["include_generated"] = True
    if args.no_java_external_supertypes:
        java_overrides["include_external_supertypes"] = False
    if args.java_relations:
        java_overrides["relation_style"] = args.java_relations
    if args.java_diagram_classes:
        lines = Path(args.java_diagram_classes).read_text(encoding="utf-8").splitlines()
        java_overrides["diagram_classes"] = [
            line.strip() for line in lines if line.strip() and not line.strip().startswith("#")
        ]
    if args.java_ide_no_jdk:
        java_overrides["ide_jdk"] = False
    if args.java_ide_no_same_package:
        java_overrides["ide_same_package"] = False
    if java_overrides:
        overrides["java"] = java_overrides
    if args.no_cleanup:
        overrides["cleanup"] = False
    if args.backend:
        overrides["backend"] = args.backend
    if args.model:
        overrides["model"] = args.model
    if args.verbose:
        overrides.setdefault("dev", {})["verbose"] = True

    try:
        config = load_config(args.config, overrides or None)
    except ConfigError as exc:
        logging.getLogger("cli").error("Config error: %s", exc)
        return 1

    method_names = list(VARIANTS) if args.method == "all" else [resolve(args.method).name]
    run_ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")

    try:
        roots = list(load_repo(args.input))
    except RepoLoadError as exc:
        log.error("Repo load error: %s", exc)
        return 1

    cache_dir = Path(config.dev.cache_dir) if args.cache else None

    seeds = args.seeds if args.seeds else None
    if seeds:
        experiment_dir = Path(args.out) / f"experiment_{run_ts}"
        seed_records: dict[int, list[RunRecord]] = {}
        exit_code = 0
        for seed in seeds:
            log.info("=== Seed %d ===", seed)
            seed_config = load_config(args.config, {**(overrides or {}), "seed": seed})
            seed_batch_ts = f"seed_{seed}"
            records, ec = _run_batch(
                args, log, seed_config, roots, method_names, cache_dir,
                out_dir=str(experiment_dir), batch_ts=seed_batch_ts,
            )
            seed_records[seed] = records
            if records:
                write_batch_summary(experiment_dir / seed_batch_ts, records)
            if ec:
                exit_code = ec
            # Abbrechen, wenn dieser Seed nichts Brauchbares geliefert hat (kein Graph mit Inhalt).
            produced = any(r.node_count > 0 and not r.incomplete for r in records)
            if not produced:
                log.warning(
                    "Seed %d produced no usable diagrams — stopping early "
                    "(remaining seeds skipped).", seed,
                )
                break
        if seed_records:
            exp_path = write_experiment_summary(experiment_dir, seed_records)
            log.info("Experiment summary: %s", exp_path)
        return exit_code
    else:
        records, exit_code = _run_batch(
            args, log, config, roots, method_names, cache_dir,
            out_dir=args.out, batch_ts=run_ts,
        )
        if records:
            summary_path = write_batch_summary(Path(args.out) / run_ts, records)
            log.info("Batch summary: %s", summary_path)
        return exit_code


def _run_batch(
    args: object,
    log: logging.Logger,
    config,
    roots: list,
    method_names: list[str],
    cache_dir,
    out_dir: str,
    batch_ts: str,
) -> tuple[list[RunRecord], int]:
    """Führt für einen Batch jede Methode auf jedem Repo aus. Gibt (records, exit_code) zurück."""
    exit_code = 0
    records: list[RunRecord] = []

    language = resolve_language(config.language)

    for root in roots:
        source_files = collect_source_files(root, config.filters, language, java=config.java)
        try:
            preflight = run_preflight(root, source_files, config.size_caps, language)
        except PreflightError as exc:
            log.error("Preflight failed for %s: %s", root, exc)
            exit_code = 1
            continue

        log.info(
            "Repo: %s — %s, %d files, %d LOC, %d classes",
            root.name, language.name, len(source_files), preflight.loc, preflight.class_count,
        )

        need_static = any(resolve(m).needs_pyreverse for m in method_names)
        code_graph = _load_code_graph(
            root, source_files, need_static, cache_dir, log, language, config.java
        )

        if config.output.write_pyreverse and code_graph.static_graph is not None:
            write_static_graph_outputs(
                out_dir, code_graph.repo, batch_ts, code_graph.static_graph,
                basename=language.static_graph_basename,
            )

        if config.auto_target_nodes and config.target_nodes is not None:
            _auto_client = LLMClient(config, TraceLogger()) if not args.dry_run else None
            if _auto_client is not None:
                log.info("[auto-target] deciding target_nodes for %s ...", code_graph.repo)
                target_nodes = decide_target_nodes(_auto_client, code_graph, preflight.loc)
                log.info("[auto-target] target_nodes=%d for %s", target_nodes, code_graph.repo)
            else:
                target_nodes = config.target_nodes
        else:
            target_nodes = config.target_nodes

        # Harte Obergrenze: max_nodes aus der Config, zusätzlich auf die Klassenzahl
        # des Repos gekappt (ein Repo kann nicht auf mehr Knoten abstrahiert werden,
        # als es Klassen hat). Deterministisch und für jede Variante gleich, damit
        # Vergleiche pro Repo gültig bleiben. Eine feste Zielzahl wird auf die
        # Grenze gekappt, ein offenes Ziel ("open") bekommt nur die Grenze.
        max_nodes = config.max_nodes
        if preflight.class_count and max_nodes > preflight.class_count:
            max_nodes = preflight.class_count
        if target_nodes is not None and target_nodes > max_nodes:
            log.info(
                "target_nodes %d exceeds cap — clipped to %d for %s",
                target_nodes, max_nodes, code_graph.repo,
            )
            target_nodes = max_nodes
        log.info(
            "Size: target=%s, max_nodes=%d for %s",
            "open" if target_nodes is None else target_nodes, max_nodes, code_graph.repo,
        )

        for method_name in method_names:
            variant = resolve(method_name)
            if variant.needs_pyreverse and code_graph.static_graph is None:
                log.warning("[%s] static class graph unavailable — skipping %s",
                            variant.name, root.name)
                continue

            run_dir = create_run_dir(out_dir, code_graph.repo, method_name, batch_ts=batch_ts)
            trace_path = run_dir / "trace.jsonl" if config.output.trace_jsonl else None
            trace = TraceLogger(trace_path)

            if args.dry_run:
                from src.llm.stub import StubLLMClient
                inner_client: LLMClient | StubLLMClient = StubLLMClient(trace)
                log.info("[%s] dry-run mode: using stub LLM", method_name)
            else:
                inner_client = LLMClient(config, trace)

            research = ResearchWriter(run_dir)
            research.save_snapshot("code_graph.json", _code_graph_summary(code_graph))
            client = ResearchLLMClient(inner_client, research, phase=method_name)

            method = Driver(
                client,
                variant,
                max_tool_calls=config.driver.max_tool_calls,
                max_tokens=config.driver.max_tokens,
                read_file_max_lines=config.driver.read_file_max_lines,
                compress_every_n_turns=config.driver.compress_every_n_turns,
                max_cluster_size=config.clustering.max_cluster_size,
                min_cluster_size=config.clustering.min_cluster_size,
                synthesis_share=config.clustering.synthesis_share,
                node_tolerance=config.node_tolerance,
                context_budget=config.context_budget,
                seed=config.seed,
                research=research,
            )

            log.info(
                "[%s] starting on %s (target=%s, cap=%d nodes)",
                method_name, code_graph.repo,
                "open" if target_nodes is None else target_nodes, max_nodes,
            )
            t0 = time.monotonic()

            try:
                graph = method.run(code_graph, target_nodes, max_nodes=max_nodes)
            except Exception as exc:
                log.exception("[%s] run failed: %s", method_name, exc)
                elapsed = time.monotonic() - t0
                empty = AbstractGraph(repo=code_graph.repo, target_nodes=target_nodes)
                cost = {
                    "llm_calls": trace.calls,
                    "tokens_in": trace.tokens_in,
                    "tokens_out": trace.tokens_out,
                }
                write_run_outputs(
                    run_dir, empty, config, [str(exc)], method_name, elapsed,
                    incomplete=True, cost=cost,
                )
                records.append(RunRecord(
                    repo=code_graph.repo, method=method_name, run_dir=run_dir,
                    node_count=0, edge_count=0, elapsed_s=elapsed,
                    warnings=1, incomplete=True,
                    llm_calls=trace.calls, tokens_in=trace.tokens_in, tokens_out=trace.tokens_out,
                ))
                exit_code = 1
                continue

            elapsed = time.monotonic() - t0
            graph, warnings = validate(graph, target_nodes, config.node_tolerance, max_nodes=max_nodes)
            raw_node_count, raw_edge_count = len(graph.nodes), len(graph.edges)

            if config.cleanup and not args.dry_run:
                # Der Cleanup kann den Graphen stark umbauen. Deshalb wird die Ausgabe des
                # Drivers vorher gesichert, damit man die Varianten auch ohne Cleanup bewerten kann.
                research.save_snapshot("graph_pre_cleanup.json", graph, also_puml=True)
                log.info("[%s] running cleanup pass", method_name)
                cleaner = CleanupPass(
                    client, research=research, context_budget=config.context_budget
                )
                graph = cleaner.run(graph, target_nodes, config.node_tolerance, max_nodes=max_nodes)
                graph, cleanup_warnings = validate(
                    graph, target_nodes, config.node_tolerance, max_nodes=max_nodes
                )
                warnings.extend(cleanup_warnings)

            # Kosten des ganzen Laufs aus dem Trace (Driver und Cleanup).
            cost = {
                "llm_calls": trace.calls,
                "tokens_in": trace.tokens_in,
                "tokens_out": trace.tokens_out,
            }
            write_run_outputs(run_dir, graph, config, warnings, method_name, elapsed, cost=cost)
            records.append(RunRecord(
                repo=code_graph.repo, method=method_name, run_dir=run_dir,
                node_count=len(graph.nodes), edge_count=len(graph.edges),
                elapsed_s=elapsed, warnings=len(warnings), incomplete=False,
                llm_calls=trace.calls, tokens_in=trace.tokens_in, tokens_out=trace.tokens_out,
                raw_node_count=raw_node_count, raw_edge_count=raw_edge_count,
            ))
            log.info(
                "[%s] done: %d nodes, %d edges — %s",
                method_name, len(graph.nodes), len(graph.edges), run_dir,
            )

    return records, exit_code


def _code_graph_summary(cg: CodeGraph) -> dict:
    pkg_class_counts: dict[str, int] = {}
    for cls in cg.classes:
        pkg = cls.module.split(".")[0]
        pkg_class_counts[pkg] = pkg_class_counts.get(pkg, 0) + 1
    return {
        "repo": cg.repo,
        "language": cg.language,
        "total_files": len(cg.source_files),
        "total_classes": len(cg.classes),
        "modules": sorted({cls.module for cls in cg.classes}),
        "class_counts_by_package": pkg_class_counts,
        "has_static_graph": cg.static_graph is not None,
        "diagnostics": len(cg.diagnostics),
    }


def _load_code_graph(root, source_files, need_static, cache_dir, log, language, java_options):
    """Baut den CodeGraph oder lädt ihn aus dem Cache, wenn der Cache an ist."""
    if cache_dir is not None:
        from src.parsing.cache import load_cached
        cache_variant = json.dumps(dataclasses.asdict(java_options), sort_keys=True) if language.name == "java" else ""
        cached = load_cached(source_files, cache_dir, language.name, cache_variant)
        # Ein Graph, der ohne statischen Klassengraphen gecacht wurde, taugt nicht
        # für catalog/prune, weil diese Varianten ihn als Kontext oder Startgraph lesen.
        if cached is not None and (not need_static or cached.static_graph is not None):
            log.info("Parser cache hit for %s", root.name)
            return cached

    code_graph = build_code_graph(
        root, source_files, repo=root.name,
        use_static_graph=need_static, language=language.name,
        java_options=java_options,
    )

    if cache_dir is not None:
        from src.parsing.cache import save_cached
        cache_variant = json.dumps(dataclasses.asdict(java_options), sort_keys=True) if language.name == "java" else ""
        save_cached(source_files, code_graph, cache_dir, language.name, cache_variant)
        log.debug("Parser cache saved for %s", root.name)

    return code_graph
