"""Die statischen Extraktoren auf den Projekten von Zhang et al. mit von Hand abstrahierten Diagrammen messen.

Die Diagramme im Paket sind Bilder. ``daten/zhang-hebig/reference.json`` ist
deshalb eine von Hand erstellte Abschrift ihrer Klassen und Beziehungen. Das
Paper zählt die Beziehungen im Diagramm gerichtet. Damit das Ergebnis mit der
Suite aus 30 Projekten vergleichbar bleibt, werden Assoziationen hier ohne
Richtung und Besitz verglichen. Bei Vererbung und Realisierung bleibt die
Richtung erhalten.
"""
from __future__ import annotations

from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import re
import signal
import time

from benchmark import edge, jl_graph, j2p, metrics, ours


ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "daten" / "zhang-hebig"
SOURCE_BASE = DATA / "Version(s) of Source Code Used"
DECLARATION = re.compile(r"\b(?:class|interface|enum|record)\s+([A-Za-z_$][\w$]*)\b")


def text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass
    raise UnicodeDecodeError("utf-8", raw, 0, 1, "unsupported source encoding")


def selected_files(record: dict, project_root: Path) -> tuple[list[Path], dict[str, list[str]]]:
    """Die Dateien auswählen, in denen eine Klasse aus dem Modell oder ihr dokumentierter Alias deklariert ist."""
    source_to_model = {record.get("aliases", {}).get(node, node): node for node in record["nodes"]}
    hits = {node: [] for node in record["nodes"]}
    selected: set[Path] = set()
    for relative_root in record["source_roots"]:
        root = project_root / relative_root
        for path in root.rglob("*.java"):
            declared = set(DECLARATION.findall(text(path)))
            for source_name, model_name in source_to_model.items():
                if source_name in declared:
                    selected.add(path)
                    hits[model_name].append(str(path.relative_to(project_root)))
    return sorted(selected), hits


def canonical_map(raw_nodes: dict, record: dict) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Knoten-IDs eines Werkzeugs nur dann Modellnamen zuordnen, wenn der Name im Quelltext eindeutig ist."""
    source_to_model = {record.get("aliases", {}).get(node, node): node for node in record["nodes"]}
    candidates: dict[str, list[str]] = {name: [] for name in source_to_model}
    for raw_id in raw_nodes:
        simple = raw_id.rsplit(".", 1)[-1]
        if simple in candidates:
            candidates[simple].append(raw_id)
    mapping: dict[str, str] = {}
    for source_name, ids in candidates.items():
        if len(ids) == 1:
            mapping[ids[0]] = source_to_model[source_name]
    return mapping, candidates


def normalized_reference(record: dict) -> set[tuple[str, str, str]]:
    return {edge(source, target, kind) for source, target, kind in record["edges"]}


def run(label: str, tools: list[str]) -> None:
    records = json.loads((DATA / "reference.json").read_text())
    output = ROOT / "ergebnisse" / "messungen" / label
    output.mkdir(parents=True, exist_ok=True)
    results = []
    manifest = []

    for record in records:
        project_root = SOURCE_BASE / record["source_dir"]
        files, source_hits = selected_files(record, project_root)
        file_hashes = {
            str(path.relative_to(project_root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in files
        }
        manifest.append(
            {
                **record,
                "selected_files": sorted(file_hashes),
                "selected_file_sha256": file_hashes,
                "source_hits": source_hits,
                "normalized_model_relations": len(normalized_reference(record)),
            }
        )
        reference_nodes = set(record["nodes"])
        reference_edges = normalized_reference(record)

        for tool in tools:
            destination = output / f"{record['project']}__{tool}.json"
            started = time.perf_counter()

            def timed_out(signum, frame):
                raise TimeoutError("extractor exceeded 180 second timeout")

            previous_handler = signal.signal(signal.SIGALRM, timed_out)
            signal.alarm(180)
            try:
                if tool == "ours":
                    raw = ours(files, project_root)
                elif tool == "javalang":
                    raw = jl_graph(files, project_root)
                elif tool == "java2plantuml":
                    raw = j2p(files, project_root, destination)
                else:
                    raise ValueError(f"unknown tool: {tool}")
            except Exception as exc:
                raw = {"nodes": {}, "edges": [], "error": f"{type(exc).__name__}: {exc}"}
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, previous_handler)

            mapping, candidates = canonical_map(raw["nodes"], record)
            predicted_nodes = set(mapping.values())
            predicted_edges = {
                edge(mapping[source], mapping[target], kind)
                for source, target, kind in raw["edges"]
                if source in mapping and target in mapping
            }
            result = {
                "project": record["project"],
                "tool": tool,
                "status": "failed" if raw.get("error") else "partial" if raw.get("failures") else "ok",
                "seconds": time.perf_counter() - started,
                "selected_source_files": len(files),
                "model_nodes": len(reference_nodes),
                "reported_model_relations": record["reported_model_relations"],
                "normalized_model_relations": len(reference_edges),
                "raw_nodes": len(raw["nodes"]),
                "raw_edges": len(raw["edges"]),
                "nodes": metrics(predicted_nodes, reference_nodes),
                "edges": metrics(predicted_edges, reference_edges),
                "missing_nodes": sorted(reference_nodes - predicted_nodes),
                "missing_edges": sorted(reference_edges - predicted_edges),
                "extra_edges": sorted(predicted_edges - reference_edges),
                "mapping_candidates": candidates,
                "raw": raw,
            }
            destination.write_text(json.dumps(result, indent=2))
            results.append(result)
            print(label, record["project"], tool, result["status"], result["nodes"], result["edges"], flush=True)

    (DATA / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (output / "results.json").write_text(json.dumps(results, indent=2))
    fields = [
        "project", "tool", "status", "seconds", "selected_source_files",
        "model_nodes", "reported_model_relations", "normalized_model_relations",
        "raw_nodes", "raw_edges", "node_precision", "node_recall", "node_f1",
        "edge_precision", "edge_recall", "edge_f1", "edge_tp", "edge_fp", "edge_fn",
    ]
    with (output / "results.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    **{name: result[name] for name in fields[:10]},
                    **{f"node_{name}": result["nodes"][name] for name in ("precision", "recall", "f1")},
                    **{f"edge_{name}": result["edges"][name] for name in ("precision", "recall", "f1", "tp", "fp", "fn")},
                }
            )

    aggregate = {}
    for tool in tools:
        rows = [row for row in results if row["tool"] == tool]
        node_counts = Counter()
        edge_counts = Counter()
        for row in rows:
            node_counts.update({key: row["nodes"][key] for key in ("tp", "fp", "fn")})
            edge_counts.update({key: row["edges"][key] for key in ("tp", "fp", "fn")})
        aggregate[tool] = {
            "completed": sum(row["status"] != "failed" for row in rows),
            "projects": len(rows),
            "seconds": sum(row["seconds"] for row in rows),
            "nodes": metrics(set(range(node_counts["tp"])), set(range(node_counts["tp"] + node_counts["fn"]))),
            "edges": metrics(set(range(edge_counts["tp"])), set(range(edge_counts["tp"] + edge_counts["fn"]))),
        }
        # Die Mengen oben enthalten nur TP und FN, keine FP. Deshalb werden die Werte
        # hier direkt aus den Zählern berechnet. Das gemeinsame Schema bleibt gleich.
        for key, counts in (("nodes", node_counts), ("edges", edge_counts)):
            tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
            aggregate[tool][key] = {
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "precision": tp / (tp + fp) if tp + fp else None,
                "recall": tp / (tp + fn) if tp + fn else None,
                "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
            }
    (output / "aggregate.json").write_text(json.dumps(aggregate, indent=2))
    print(json.dumps(aggregate, indent=2))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="curated-final")
    parser.add_argument("--tools", nargs="+", default=["ours", "javalang", "java2plantuml"])
    args = parser.parse_args()
    run(args.label, args.tools)
