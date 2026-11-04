"""Den IntelliJ-Modus des eigenen Extraktors mit den Diagrammen von IntelliJ vergleichen.

Für jedes Projekt in ``daten/intellij/projekte.json`` wird der Klassengraph nach den
Regeln von IntelliJ gebaut, mit derselben Klassenauswahl und derselben Umgebung
(JDK ja oder nein, Paketauflösung ja oder nein), die sich aus dem jeweiligen
IntelliJ-Bild ergibt. Das Ergebnis wird mit den Kanten verglichen, die aus dem
Bild abgelesen wurden (``daten/intellij/referenz/<Projekt>.json``).

Aufruf aus Ordner 2:

    PYTHONPATH=../1-llm-pipeline-abstrakte-klassendiagramme \\
        .venv/bin/python skripte/intellij_abgleich.py [--render]

``--render`` erzeugt zusätzlich PNG-Dateien mit PlantUML (braucht Java).
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Die Pfade in projekte.json (Quelle, Bild) sind relativ zu daten/.
DATA = ROOT / "daten"
CONFIG = DATA / "intellij" / "projekte.json"
REFERENCE_DIR = DATA / "intellij" / "referenz"
RESULTS = ROOT / "ergebnisse" / "messungen" / "intellij"
DIAGRAMS = ROOT / "ergebnisse" / "diagramme-intellij"
PLANTUML = ROOT / "werkzeuge" / "plantuml-1.2025.4.jar"


def edge_key(edge: dict) -> tuple:
    return (edge["art"], edge["von"], edge["nach"], edge.get("bezeichnung"), edge.get("ziel_kardinalitaet"))


def run_project(project: dict, render: bool) -> dict:
    from src.parsing.java.intellij import IdeEnvironment, build_intellij_graph
    from src.schema.plantuml import to_plantuml

    source = DATA / project["quelle"]
    files = sorted(source.rglob("*.java"))
    env = IdeEnvironment(jdk=project["umgebung"]["jdk"],
                         same_package=project["umgebung"]["same_package"])
    graph = build_intellij_graph(files, source, project["name"], env, project["klassen"])

    # Die Knoten-IDs sind um das gemeinsame Paketpräfix gekürzt. Verglichen wird
    # mit den voll qualifizierten Namen aus der Konfiguration.
    def full_name(node_id: str) -> str:
        short = node_id.removeprefix("external.")
        matches = [c for c in project["klassen"] if c == short or c.endswith("." + short)]
        return matches[0] if len(matches) == 1 else node_id

    edges = []
    for e in graph.edges:
        label = e.label if e.type in {"composition", "dependency"} else None
        card = e.target_card if e.type == "composition" else None
        edges.append({
            "art": e.type, "von": full_name(e.source), "nach": full_name(e.target),
            "bezeichnung": label, "ziel_kardinalitaet": card,
        })
    edges.sort(key=lambda x: (x["art"], x["von"], x["nach"], x["bezeichnung"] or ""))

    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"{project['name']}.json").write_text(
        json.dumps({"projekt": project["name"], "kanten": edges}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    out_dir = DIAGRAMS / project["name"]
    out_dir.mkdir(parents=True, exist_ok=True)
    puml = out_dir / "eigener-extraktor.puml"
    puml.write_text(to_plantuml(graph), encoding="utf-8")
    image = DATA / project["bild"]
    if image.exists():
        shutil.copyfile(image, out_dir / "00-intellij.png")
    if render and PLANTUML.exists():
        # Ohne PLANTUML_LIMIT_SIZE schneidet PlantUML Bilder bei 4096 Pixeln ab
        # (betraf Orekit, Artemis, NeurophChanges und RaiseMeUp).
        subprocess.run(["java", "-Djava.awt.headless=true", "-DPLANTUML_LIMIT_SIZE=16384",
                        "-jar", str(PLANTUML), "-Playout=smetana", "-tpng", str(puml)],
                       check=False, capture_output=True, timeout=600)

    reference_file = REFERENCE_DIR / f"{project['name']}.json"
    reference = json.loads(reference_file.read_text(encoding="utf-8")) if reference_file.exists() else None
    result = {"projekt": project["name"], "kanten": len(edges)}
    if reference is not None:
        ours = {edge_key(e) for e in edges}
        expected = {edge_key(e) for e in reference["kanten"]}
        result["referenz"] = reference["umfang"]
        result["referenzkanten"] = len(expected)
        result["gefunden"] = len(expected & ours)
        result["fehlend"] = sorted(map(list, expected - ours))
        # Zusätzliche Kanten lassen sich nur gegen eine vollständige Abschrift werten.
        result["zusaetzlich"] = sorted(map(list, ours - expected)) if reference["umfang"] == "vollständig" else None
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--render", action="store_true", help="PNG mit PlantUML erzeugen")
    parser.add_argument("--projekt", action="append", help="nur dieses Projekt (mehrfach möglich)")
    args = parser.parse_args()

    projects = json.loads(CONFIG.read_text(encoding="utf-8"))["projekte"]
    if args.projekt:
        projects = [p for p in projects if p["name"] in args.projekt]
    results = [run_project(p, args.render) for p in projects]
    (RESULTS / "abgleich.json").write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n",
                                           encoding="utf-8")

    print(f"{'Projekt':20} {'Kanten':>6} {'Referenz':>12} {'gefunden':>9} {'fehlend':>8} {'zusätzlich':>10}")
    for r in results:
        if "referenz" not in r:
            print(f"{r['projekt']:20} {r['kanten']:>6} {'-':>12}")
            continue
        extra = "-" if r["zusaetzlich"] is None else str(len(r["zusaetzlich"]))
        print(f"{r['projekt']:20} {r['kanten']:>6} {r['referenz']:>12} "
              f"{r['gefunden']:>4}/{r['referenzkanten']:<4} {len(r['fehlend']):>8} {extra:>10}")
    if any(r.get("fehlend") or r.get("zusaetzlich") for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
