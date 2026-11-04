"""Ergebnisse von Läufen mit einem von Hand erstellten Ground-Truth-Graphen vergleichen.

Aufruf:
    python -m src.tools.gt_compare ground_truth/schedule.json runs/<batch>/schedule

Bewertet jede <variante>/graph.json im angegebenen Repo-Ordner gegen die
Ground Truth, und wenn es ihn gibt, auch den Stand vor dem Cleanup:

  - Knoten: Precision, Recall und F1, verglichen über die Knoten-ID
  - Kanten streng: F1, wenn Quelle, Ziel und Kantenart übereinstimmen
  - Kanten locker: F1 über das Paar der Endpunkte, ohne Richtung und Kantenart

Die lockere Wertung gibt es, weil Richtung und Kantenart am unsichersten
sind, beim Modell genauso wie bei der Ground Truth. Eine Variante, die die
richtigen Klassenpaare findet, aber eine Komposition falsch herum zeichnet,
soll nicht null Punkte bekommen.

Seit das Schema erweitert wurde, gibt die Pipeline alle UML-Kantenarten aus
(inheritance, realization, composition, aggregation, association, dependency,
dazu nesting im IntelliJ-Modus für Java). Die strenge Wertung vergleicht die
Kantenart deshalb direkt. Multiplizitäten werden nicht bewertet.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _norm_type(t: str) -> str:
    return t


def _prf(predicted: set, actual: set) -> tuple[float, float, float]:
    if not predicted and not actual:
        return 1.0, 1.0, 1.0
    tp = len(predicted & actual)
    p = tp / len(predicted) if predicted else 0.0
    r = tp / len(actual) if actual else 0.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f1


def score(graph: dict, gt: dict) -> dict:
    gt_nodes = {n["id"] for n in gt["nodes"]}
    gt_strict = {(e["source"], e["target"], _norm_type(e["type"])) for e in gt["edges"]}
    gt_relaxed = {frozenset((e["source"], e["target"])) for e in gt["edges"]}

    nodes = {n["id"] for n in graph.get("nodes", [])}
    strict = {(e["source"], e["target"], _norm_type(e["type"])) for e in graph.get("edges", [])}
    relaxed = {frozenset((e["source"], e["target"])) for e in graph.get("edges", [])}

    np_, nr, nf = _prf(nodes, gt_nodes)
    sp, sr, sf = _prf(strict, gt_strict)
    rp, rr, rf = _prf(relaxed, gt_relaxed)
    return {
        "nodes": {"precision": np_, "recall": nr, "f1": nf},
        "edges_strict": {"precision": sp, "recall": sr, "f1": sf},
        "edges_relaxed": {"precision": rp, "recall": rr, "f1": rf},
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 1
    gt = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    repo_dir = Path(argv[1])

    rows = []
    for variant_dir in sorted(p for p in repo_dir.iterdir() if p.is_dir()):
        graph_file = variant_dir / "graph.json"
        if not graph_file.exists():
            continue
        final = json.loads(graph_file.read_text(encoding="utf-8"))
        rows.append((variant_dir.name, "final", score(final, gt)))
        pre = variant_dir / "snapshots" / "graph_pre_cleanup.json"
        if pre.exists():
            raw = json.loads(pre.read_text(encoding="utf-8"))
            rows.append((variant_dir.name, "pre-cleanup", score(raw, gt)))

    if not rows:
        print(f"No graph.json found under {repo_dir}")
        return 1

    print(f"Ground truth: {len(gt['nodes'])} nodes, {len(gt['edges'])} edges\n")
    header = (
        f"{'variant':<16} {'stage':<12} "
        f"{'node P/R/F1':<18} {'edge strict P/R/F1':<20} {'edge relaxed P/R/F1':<20}"
    )
    print(header)
    print("-" * len(header))
    for name, stage, s in rows:
        n, es, er = s["nodes"], s["edges_strict"], s["edges_relaxed"]
        print(
            f"{name:<16} {stage:<12} "
            f"{n['precision']:.2f}/{n['recall']:.2f}/{n['f1']:.2f}      "
            f"{es['precision']:.2f}/{es['recall']:.2f}/{es['f1']:.2f}        "
            f"{er['precision']:.2f}/{er['recall']:.2f}/{er['f1']:.2f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
