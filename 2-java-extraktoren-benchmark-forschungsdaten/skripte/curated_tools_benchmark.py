"""Alle sieben Extraktoren von Java nach UML auf den kuratierten Projekten von Zhang et al. messen.

Als Referenz dienen die von Hand gezeichneten Diagramme, abgeschrieben in
``daten/zhang-hebig/reference.json``. Maßstab ist also die Abstraktion durch
Menschen und nicht das, was der Compiler über den Code weiß.

Vier der sieben Werkzeuge lesen Bytecode, und der fehlt im Replikationspaket.
``compile_project`` versucht deshalb pro Projekt einen dokumentierten
``javac``-Lauf mit den JARs aus dem Projekt und aus ``werkzeuge/extra/jars``.
Projekte, die sich nicht kompilieren lassen, werden als solche vermerkt. Die
Bytecode-Werkzeuge melden dann ``no bytecode`` und bekommen nicht stillschweigend
eine Null.

Jeder bewertete Graph wird außerdem als PlantUML geschrieben und unter
``ergebnisse/diagramme/`` neben dem Referenzdiagramm als PNG gerendert. So lassen
sich die Ausgaben auch im Bild vergleichen und nicht nur über die Zahlen.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

from benchmark import edge, jl_graph, j2p, metrics, ours
from curated_hebig_benchmark import (
    DATA,
    SOURCE_BASE,
    canonical_map,
    normalized_reference,
    selected_files,
)

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "werkzeuge"
EXTRA_JARS = sorted(str(p) for p in (TOOLS / "extra/jars").glob("*.jar"))
PLANTUML = TOOLS / "plantuml-1.2025.4.jar"
GENUML_BIN = str(Path.home() / ".local/bin/genuml")

SOURCE_TOOLS = ("ours", "javalang", "java2plantuml")
BYTECODE_TOOLS = ("jdeps", "plantuml-generator", "java2plantuml-juanmf", "genuml")
ALL_TOOLS = SOURCE_TOOLS + BYTECODE_TOOLS

# Weitere Module, die ein Projekt zum Kompilieren braucht, in denen aber keine
# Klasse aus dem Modell liegt. Sie gehen nur in den Compiler und nie in den
# bewerteten Umfang.
COMPILE_ONLY_ROOTS = {
    "EAPLI_PL_2NB": ["eapli.util/src"],
    "PatrickFromTheMOOC": ["exception", "ihm"],
}


def simple(name: str) -> str:
    return name.replace("$", ".").split(".")[-1]


def project_jars(project_root: Path) -> list[str]:
    return sorted({str(j) for j in project_root.rglob("*.jar") if "-sources" not in j.name})


# Kompilieren


def compile_project(record: dict, project_root: Path, workdir: Path) -> dict:
    """Versucht einmal, das Projekt mit javac zu kompilieren.

    Returns:
        Einen Bericht über den Versuch. Die Funktion wirft keine Ausnahme,
        auch wenn das Kompilieren scheitert.
    """
    roots = [project_root / r for r in record["source_roots"]]
    roots += [project_root / r for r in COMPILE_ONLY_ROOTS.get(record["project"], [])]
    sources = sorted({f for root in roots if root.is_dir() for f in root.rglob("*.java")})
    classes = workdir / "classes" / record["project"]
    if classes.exists():
        shutil.rmtree(classes)
    classes.mkdir(parents=True, exist_ok=True)
    if not sources:
        return {"compiled": False, "reason": "no sources", "class_files": 0}
    classpath = ":".join(project_jars(project_root) + EXTRA_JARS) or "."
    command = [
        "javac", "-nowarn", "-proc:none", "-encoding", "UTF-8",
        "-cp", classpath, "-d", str(classes),
    ] + [str(f) for f in sources]
    started = time.perf_counter()
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=600)
        returncode, stderr = completed.returncode, completed.stderr
    except subprocess.TimeoutExpired:
        returncode, stderr = -1, "javac exceeded 600 second timeout"
    produced = len(list(classes.rglob("*.class")))
    errors = [line for line in stderr.splitlines() if ": error:" in line]
    missing = Counter(re.findall(r"package ([\w.]+) does not exist", stderr))
    report = {
        "compiled": returncode == 0 and produced > 0,
        "returncode": returncode,
        "source_files": len(sources),
        "class_files": produced,
        "errors": len(errors),
        "missing_packages": dict(missing.most_common(5)),
        "first_errors": [e.split("java:")[-1][:160] for e in errors[:3]],
        "seconds": time.perf_counter() - started,
        "classpath_jars": len(project_jars(project_root)) + len(EXTRA_JARS),
    }
    if not report["compiled"]:
        shutil.rmtree(classes, ignore_errors=True)
    return report


def bytecode_root(record: dict, workdir: Path) -> Path | None:
    path = workdir / "classes" / record["project"]
    return path if path.is_dir() and any(path.rglob("*.class")) else None


def root_packages(classes: Path) -> list[str]:
    packages = set()
    for c in classes.rglob("*.class"):
        parts = c.relative_to(classes).parts[:-1]
        if parts:
            packages.add(parts[0])
    return sorted(packages)


# PlantUML-Text lesen

_RELATION = re.compile(
    r'^\s*"?([\w.$<>\[\] ]+?)"?\s*(?:"[^"]*")?\s*'
    r'(<\|-+|-+\|>|<\|\.+|\.+\|>|\*-+|-+\*|o-+|-+o|-+>|<-+|-+|\.+>|<\.+)'
    r'\s*(?:"[^"]*")?\s*"?([\w.$<>\[\] ]+?)"?\s*(?::.*)?$')
_DECLARATION = re.compile(r"^\s*(?:abstract\s+)?(?:class|interface|enum|annotation)\s+([\w.$]+)")
_DIRECTION_HINT = re.compile(r"(?<=[-.<|*o])(up|down|left|right)(?=[-.|>*o])")


def _canonical_arrow(arrow: str) -> str:
    return re.sub(r"\.+", "..", re.sub(r"-+", "--", arrow))


def parse_puml(text: str) -> dict:
    """Ein PlantUML-Klassendiagramm in die gemeinsame Form aus Knoten und Kanten bringen."""
    nodes: dict[str, dict] = {}
    edges: list[tuple[str, str, str]] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith(("@", "skinparam", "hide", "note", "'",
                                                "left to right", "top to bottom", "!")):
            continue
        declared = _DECLARATION.match(raw_line)
        if declared:
            nodes[simple(declared.group(1))] = {"name": simple(declared.group(1))}
            continue
        if "{" in raw_line or "}" in raw_line:
            continue
        if re.match(r"^\s*[-+#~]", raw_line):
            continue
        match = _RELATION.match(_DIRECTION_HINT.sub("", raw_line))
        if not match:
            continue
        arrow = _canonical_arrow(match.group(2))
        a, b = simple(match.group(1).strip()), simple(match.group(3).strip())
        if not a or not b:
            continue
        for name in (a, b):
            nodes.setdefault(name, {"name": name})
        if arrow == "<|--":
            edges.append(edge(b, a, "inheritance"))
        elif arrow == "--|>":
            edges.append(edge(a, b, "inheritance"))
        elif arrow == "<|..":
            edges.append(edge(b, a, "realization"))
        elif arrow == "..|>":
            edges.append(edge(a, b, "realization"))
        elif arrow in ("*--", "o--", "-->", "--", "..>"):
            edges.append(edge(a, b, "association"))
        elif arrow in ("--*", "--o", "<--", "<.."):
            edges.append(edge(b, a, "association"))
    return {"nodes": nodes, "edges": sorted(set(edges))}


# Aufruf der Werkzeuge


def run_jdeps(classes: Path, project_root: Path) -> dict:
    completed = subprocess.run(
        ["jdeps", "-v", "-cp", str(classes), str(classes)],
        capture_output=True, text=True, timeout=600)
    nodes: dict[str, dict] = {}
    edges = []
    for line in completed.stdout.splitlines():
        match = re.match(r"\s+(\S+)\s+->\s+(\S+)\s+(\S+)\s*$", line)
        if not match:
            continue
        source, target = simple(match.group(1)), simple(match.group(2))
        if source == target:
            continue
        nodes.setdefault(source, {"name": source})
        nodes.setdefault(target, {"name": target})
        edges.append(edge(source, target, "association"))
    return {
        "nodes": nodes, "edges": sorted(set(edges)), "returncode": completed.returncode,
        "note": "untyped dependency edges from the constant pool; no inheritance relation",
    }


def run_plantuml_generator(classes: Path, project_root: Path) -> dict:
    classpath = ":".join(
        [str(p) for p in (TOOLS / "pug/lib").glob("*.jar")] + [str(TOOLS / "pug/driver")])
    jars = ":".join(project_jars(project_root) + EXTRA_JARS) or "-"
    packages = root_packages(classes)
    if not packages:
        return {"nodes": {}, "edges": [], "error": "no root packages in bytecode"}
    completed = subprocess.run(
        ["java", "-cp", classpath, "Run", str(classes), jars, *packages],
        capture_output=True, text=True, timeout=900)
    if completed.returncode != 0 or "@startuml" not in completed.stdout:
        return {"nodes": {}, "edges": [], "error": _java_error(completed.stderr),
                "returncode": completed.returncode}
    return {**parse_puml(completed.stdout), "native_puml": completed.stdout}


def run_juanmf(classes: Path, project_root: Path) -> dict:
    jar = TOOLS / "juanmf/target/java2PlantUML-maven-plugin-1.0.1.jar"
    if not jar.exists():
        return {"nodes": {}, "edges": [], "error": "tool not built"}
    classpath = ":".join([
        str(jar), (TOOLS / "juanmf/cp.txt").read_text().strip(), str(TOOLS / "juanmf/driver")])
    jars = ":".join(project_jars(project_root) + EXTRA_JARS) or "-"
    packages = ", ".join(root_packages(classes))
    completed = subprocess.run(
        ["java", "-cp", classpath, "JuanmfRun", str(classes), jars, packages],
        capture_output=True, text=True, timeout=900)
    if "@startuml" not in completed.stdout:
        return {"nodes": {}, "edges": [], "error": _java_error(completed.stderr),
                "returncode": completed.returncode}
    return {**parse_puml(completed.stdout), "native_puml": completed.stdout}


def run_genuml(classes: Path, project_root: Path) -> dict:
    executable = Path(GENUML_BIN)
    if not executable.exists():
        return {"nodes": {}, "edges": [], "error": "genuml not installed"}
    chunks, ok, failed = [], 0, 0
    errors: Counter = Counter()
    for class_file in sorted(classes.rglob("*.class")):
        completed = subprocess.run(
            [str(executable), "generate", str(class_file)],
            capture_output=True, text=True, timeout=120)
        if completed.returncode == 0 and completed.stdout.strip():
            ok += 1
            chunks.append(completed.stdout)
        else:
            failed += 1
            message = ((completed.stderr.strip() or completed.stdout.strip()).splitlines() or ["?"])[-1]
            errors[message[:90]] += 1
    body = "\n".join(chunks)
    relation_lines = sum(
        1 for line in body.splitlines()
        if re.search(r"(<\|--|--\|>|\.\.\|>|-->|o--|\*--)", line))
    return {
        **parse_puml(body), "native_puml": body,
        "classes_ok": ok, "classes_failed": failed,
        "relation_lines_emitted": relation_lines,
        "errors": dict(errors.most_common(3)),
    }


def _java_error(stderr: str) -> str:
    for line in (stderr or "").splitlines():
        text = line.strip()
        if text and not text.startswith(("at ", "... ", "WARNING", "Caused by:")) and "Exception" in text:
            return text[:220]
    lines = [l for l in (stderr or "").splitlines() if l.strip()]
    return lines[0][:220] if lines else "no stderr"


BYTECODE_RUNNERS = {
    "jdeps": run_jdeps,
    "plantuml-generator": run_plantuml_generator,
    "java2plantuml-juanmf": run_juanmf,
    "genuml": run_genuml,
}


# Diagramme schreiben und rendern


def write_diagram(path: Path, title: str, nodes: set[str], edges: set[tuple[str, str, str]]) -> None:
    arrow = {"inheritance": "--|>", "realization": "..|>", "association": "--"}
    lines = ["@startuml", "hide empty members", f"title {title}", ""]
    for name in sorted(nodes):
        lines.append(f"class {name}")
    lines.append("")
    for source, target, kind in sorted(edges):
        lines.append(f"{source} {arrow[kind]} {target}")
    lines += ["", "@enduml"]
    path.write_text("\n".join(lines))


def render(puml_files: list[Path]) -> tuple[int, str]:
    """PlantUML als PNG rendern. Mit dem Layout Smetana wird Graphviz nicht gebraucht."""
    if not puml_files:
        return 0, "nothing to render"
    completed = subprocess.run(
        ["java", "-jar", str(PLANTUML), "-tpng", "-Playout=smetana", "-nbthread", "4",
         *[str(p) for p in puml_files]],
        capture_output=True, text=True, timeout=1800)
    rendered = sum(1 for p in puml_files if p.with_suffix(".png").exists())
    return rendered, (completed.stderr or "").strip()[:300]


# Hauptprogramm


def run(label: str, workdir: Path, tools: list[str]) -> None:
    records = json.loads((DATA / "reference.json").read_text())
    output = ROOT / "ergebnisse" / "messungen" / label
    output.mkdir(parents=True, exist_ok=True)
    diagrams = ROOT / "ergebnisse" / "diagramme"
    diagrams.mkdir(exist_ok=True)

    results, compilation, to_render = [], {}, []

    for record in records:
        project = record["project"]
        project_root = SOURCE_BASE / record["source_dir"]
        files, _ = selected_files(record, project_root)
        reference_nodes = set(record["nodes"])
        reference_edges = normalized_reference(record)

        folder = diagrams / project
        folder.mkdir(parents=True, exist_ok=True)
        reference_puml = folder / "00-reference.puml"
        write_diagram(reference_puml, f"{project} — Referenz (Zhang et al.)",
                      reference_nodes, reference_edges)
        to_render.append(reference_puml)

        report = compile_project(record, project_root, workdir)
        compilation[project] = report
        classes = bytecode_root(record, workdir)
        print(f"[compile] {project:<20} {'OK' if report['compiled'] else 'FEHLER':<7} "
              f"{report['class_files']} class-Dateien", flush=True)

        for tool in tools:
            destination = output / f"{project}__{tool}.json"
            started = time.perf_counter()

            def timed_out(signum, frame):
                raise TimeoutError("extractor exceeded 900 second timeout")

            previous = signal.signal(signal.SIGALRM, timed_out)
            signal.alarm(900)
            try:
                if tool == "ours":
                    raw = ours(files, project_root)
                elif tool == "javalang":
                    raw = jl_graph(files, project_root)
                elif tool == "java2plantuml":
                    raw = j2p(files, project_root, destination)
                elif tool in BYTECODE_RUNNERS:
                    if classes is None:
                        raw = {"nodes": {}, "edges": [],
                               "error": "no bytecode: project does not compile"}
                    else:
                        raw = BYTECODE_RUNNERS[tool](classes, project_root)
                else:
                    raise ValueError(f"unknown tool: {tool}")
            except Exception as exc:
                raw = {"nodes": {}, "edges": [], "error": f"{type(exc).__name__}: {exc}"}
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, previous)
            seconds = time.perf_counter() - started

            native = raw.pop("native_puml", None)
            if native:
                (folder / f"{tool}-native.puml").write_text(native)

            mapping, candidates = canonical_map(raw["nodes"], record)
            predicted_nodes = set(mapping.values())
            predicted_edges = {
                edge(mapping[s], mapping[t], k)
                for s, t, k in raw["edges"] if s in mapping and t in mapping
            }

            scoped = folder / f"{tool}.puml"
            write_diagram(scoped, f"{project} — {tool}", predicted_nodes, predicted_edges)
            to_render.append(scoped)

            result = {
                "project": project,
                "tool": tool,
                "family": "Quelltext" if tool in SOURCE_TOOLS else "Bytecode",
                "status": "failed" if raw.get("error") else "ok",
                "error": raw.get("error"),
                "seconds": seconds,
                "selected_source_files": len(files),
                "compiled": report["compiled"],
                "model_nodes": len(reference_nodes),
                "normalized_model_relations": len(reference_edges),
                "raw_nodes": len(raw["nodes"]),
                "raw_edges": len(raw["edges"]),
                "nodes": metrics(predicted_nodes, reference_nodes),
                "edges": metrics(predicted_edges, reference_edges),
                "missing_nodes": sorted(reference_nodes - predicted_nodes),
                "missing_edges": sorted(reference_edges - predicted_edges),
                "extra_edges": sorted(predicted_edges - reference_edges),
                "mapping_candidates": candidates,
                "meta": {k: v for k, v in raw.items() if k not in ("nodes", "edges")},
            }
            destination.write_text(json.dumps(result, indent=2))
            results.append(result)
            print(f"  {project:<20} {tool:<22} {result['status']:<7} "
                  f"N {result['nodes']['tp']}/{len(reference_nodes)} "
                  f"E {result['edges']['tp']}/{len(reference_edges)} "
                  f"{result.get('error') or ''}", flush=True)

    (output / "results.json").write_text(json.dumps(results, indent=2))
    (output / "compilation.json").write_text(json.dumps(compilation, indent=2))

    aggregate = {}
    for tool in tools:
        rows = [r for r in results if r["tool"] == tool]
        node_counts, edge_counts = Counter(), Counter()
        for row in rows:
            node_counts.update({k: row["nodes"][k] for k in ("tp", "fp", "fn")})
            edge_counts.update({k: row["edges"][k] for k in ("tp", "fp", "fn")})
        entry = {
            "family": "Quelltext" if tool in SOURCE_TOOLS else "Bytecode",
            "completed": sum(r["status"] == "ok" for r in rows),
            "projects": len(rows),
            "seconds": sum(r["seconds"] for r in rows),
        }
        for key, counts in (("nodes", node_counts), ("edges", edge_counts)):
            tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
            entry[key] = {
                "tp": tp, "fp": fp, "fn": fn,
                "precision": tp / (tp + fp) if tp + fp else None,
                "recall": tp / (tp + fn) if tp + fn else None,
                "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
            }
        aggregate[tool] = entry
    (output / "aggregate.json").write_text(json.dumps(aggregate, indent=2))

    fields = ["project", "tool", "family", "status", "seconds", "compiled",
              "model_nodes", "normalized_model_relations", "raw_nodes", "raw_edges",
              "node_tp", "node_f1", "edge_tp", "edge_precision", "edge_recall", "edge_f1"]
    with (output / "results.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in results:
            writer.writerow({
                **{k: row[k] for k in fields[:10]},
                "node_tp": row["nodes"]["tp"], "node_f1": row["nodes"]["f1"],
                "edge_tp": row["edges"]["tp"],
                **{f"edge_{k}": row["edges"][k] for k in ("precision", "recall", "f1")},
            })

    rendered, message = render(to_render)
    print(f"\n{rendered}/{len(to_render)} PNG gerendert nach {diagrams}/  {message}")

    print("\nGesamt:")
    for tool, entry in aggregate.items():
        e = entry["edges"]
        print(f"  {tool:<22} {entry['family']:<10} gelaufen {entry['completed']}/{entry['projects']}  "
              f"Knoten {entry['nodes']['tp']}/79  Kanten {e['tp']}/79  "
              f"P {e['precision'] or 0:.3f}  R {e['recall'] or 0:.3f}  F1 {e['f1'] or 0:.3f}  "
              f"{entry['seconds']:.1f}s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="curated-alltools")
    parser.add_argument("--workdir", default="/tmp/java-uml-bytecode")
    parser.add_argument("--genuml", default=str(Path.home() / ".local/bin/genuml"))
    parser.add_argument("--tools", nargs="+", default=list(ALL_TOOLS))
    args = parser.parse_args()
    GENUML_BIN = args.genuml
    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    run(args.label, workdir, args.tools)
