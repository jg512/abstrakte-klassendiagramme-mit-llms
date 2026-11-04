"""PlantUML-Diagramm aus einer graph.json neu erzeugen.

Aufruf:
    python -m src.tools.render_plantuml runs/<lauf-id>/graph.json

Schreibt diagram.puml in denselben Ordner wie graph.json und gibt den Pfad aus.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def render(graph_path: Path, out_path: Path | None = None) -> Path:
    from src.schema.json_io import json_to_graph as graph_from_json
    from src.schema.plantuml import to_plantuml

    data = graph_path.read_text(encoding="utf-8")
    graph = graph_from_json(data)
    puml = to_plantuml(graph)

    dest = out_path or graph_path.parent / "diagram.puml"
    dest.write_text(puml, encoding="utf-8")
    return dest


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m src.tools.render_plantuml",
        description="Re-render a PlantUML diagram from graph.json.",
    )
    parser.add_argument("graph_json", metavar="PATH", help="Path to graph.json")
    parser.add_argument("--out", metavar="PATH", help="Output .puml path (default: next to graph.json)")
    args = parser.parse_args(argv)

    path = Path(args.graph_json)
    if not path.exists():
        print(f"Error: {path} not found", file=sys.stderr)
        sys.exit(1)

    dest = render(path, Path(args.out) if args.out else None)
    print(f"Written: {dest}")


if __name__ == "__main__":
    main()
