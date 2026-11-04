import json
from pathlib import Path

from benchmark import edge


ROOT = Path(__file__).resolve().parent.parent


def records():
    return json.loads((ROOT / "daten" / "zhang-hebig" / "reference.json").read_text())


def test_curated_reference_totals_match_paper_package():
    data = records()
    assert len(data) == 9
    assert sum(len(row["nodes"]) for row in data) == 79
    assert sum(row["reported_model_relations"] for row in data) == 82
    assert sum(len({edge(*item) for item in row["edges"]}) for row in data) == 79


def test_all_reference_edges_use_declared_nodes_and_supported_kinds():
    for row in records():
        nodes = set(row["nodes"])
        assert len(nodes) == len(row["nodes"])
        for source, target, kind in row["edges"]:
            assert source in nodes
            assert target in nodes
            assert kind in {"association", "inheritance", "realization"}


def test_aliases_target_unique_source_names():
    for row in records():
        source_names = [row.get("aliases", {}).get(node, node) for node in row["nodes"]]
        assert len(source_names) == len(set(source_names))
