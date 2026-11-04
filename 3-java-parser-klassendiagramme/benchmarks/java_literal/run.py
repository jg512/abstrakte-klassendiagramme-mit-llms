from __future__ import annotations

import argparse
import dataclasses
import json
import tempfile
from pathlib import Path

from javauml.api import Options, extract
from javauml.sources import collect_java_files

ROOT = Path(__file__).resolve().parent


def run_cases() -> dict:
    cases = json.loads((ROOT / "manifest.json").read_text())
    results = []
    for case in cases:
        with tempfile.TemporaryDirectory(prefix="abstract-uml-modern-") as td:
            root = Path(td)
            for relative, source in case["sources"].items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(source, encoding="utf-8")
            # Die Fälle nennen die Optionen so wie JavaConfig in Ordner 1.
            extra = case.get("options", {})
            options = Options(
                external_supertypes=False,
                member_profile="full",
                method_dependencies=extra.get("include_method_dependencies", False),
            )
            files = collect_java_files(root, (), ())
            graph = extract(root, options, repo=case["name"], files=files).graph
            actual = sorted(
                [edge.source, edge.target, edge.type, edge.target_card]
                for edge in graph.edges
            )
            expected = sorted(case["edges"])
            results.append({
                "name": case["name"],
                "ok": actual == expected,
                "expected": expected,
                "actual": actual,
                "diagnostics": [dataclasses.asdict(d) for d in graph.diagnostics],
            })
    return {
        "cases": len(results),
        "passed": sum(item["ok"] for item in results),
        "failed": sum(not item["ok"] for item in results),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_cases()
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
