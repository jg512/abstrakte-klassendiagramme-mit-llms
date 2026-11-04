from __future__ import annotations

import json
import textwrap

import pytest

from src.schema import (
    AbstractGraph,
    Edge,
    EdgeEvidence,
    Diagnostic,
    Node,
    Package,
    check_plantuml,
    dict_to_graph,
    graph_to_dict,
    graph_to_json,
    json_to_graph,
    to_plantuml,
    validate,
)


# Testdaten


def _canonical_graph() -> AbstractGraph:
    """Der Beispielgraph aus dem ursprünglichen Entwurf der Datenformate."""
    return AbstractGraph(
        repo="test-repo",
        target_nodes=20,
        packages=[
            Package(name="app", parent=None),
            Package(name="app.domain", parent="app"),
        ],
        nodes=[
            Node(
                id="app.domain.Order",
                name="Order",
                package="app.domain",
                stereotype="dataclass",
                attributes=["id: int", "status: OrderStatus"],
                methods=["submit()", "cancel()"],
            ),
            Node(
                id="app.domain.Entity",
                name="Entity",
                package="app.domain",
                stereotype="abstract",
                attributes=["id: int"],
                methods=["validate()"],
            ),
        ],
        edges=[
            Edge(source="app.domain.Order", target="app.domain.Entity", type="inheritance"),
        ],
    )


# graph.py


def test_graph_defaults():
    g = AbstractGraph(repo="r", target_nodes=10)
    assert g.packages == []
    assert g.nodes == []
    assert g.edges == []


def test_node_defaults():
    n = Node(id="pkg.A", name="A", package="pkg")
    assert n.stereotype is None
    assert n.attributes == []
    assert n.methods == []


def test_package_defaults():
    p = Package(name="pkg")
    assert p.parent is None


# json_io.py


def test_round_trip_json():
    g = _canonical_graph()
    recovered = json_to_graph(graph_to_json(g))

    assert recovered.repo == g.repo
    assert recovered.target_nodes == g.target_nodes
    assert len(recovered.packages) == len(g.packages)
    assert len(recovered.nodes) == len(g.nodes)
    assert len(recovered.edges) == len(g.edges)

    assert recovered.packages[0].name == "app"
    assert recovered.packages[1].parent == "app"

    n = recovered.nodes[0]
    assert n.id == "app.domain.Order"
    assert n.stereotype == "dataclass"
    assert n.attributes == ["id: int", "status: OrderStatus"]

    e = recovered.edges[0]
    assert e.source == "app.domain.Order"
    assert e.type == "inheritance"


def test_round_trip_preserves_source_evidence_and_diagnostics():
    g = _canonical_graph()
    g.nodes[0].source_file = "src/Order.java"
    g.nodes[0].source_line = 12
    g.edges[0].label = "entity"
    g.edges[0].evidence.append(EdgeEvidence(
        kind="field", member="entity", declared_type="Entity",
        file="src/Order.java", line=14,
    ))
    g.diagnostics.append(Diagnostic(
        code="ambiguous-type", message="ambiguous", source="Order", candidates=["a.X", "b.X"]
    ))
    recovered = json_to_graph(graph_to_json(g))
    assert recovered.nodes[0].source_file == "src/Order.java"
    assert recovered.edges[0].label == "entity"
    assert recovered.edges[0].evidence[0].line == 14
    assert recovered.diagnostics[0].candidates == ["a.X", "b.X"]


def test_round_trip_dict():
    g = _canonical_graph()
    assert dict_to_graph(graph_to_dict(g)).repo == g.repo


def test_json_null_stereotype_preserved():
    g = AbstractGraph(
        repo="r",
        target_nodes=5,
        packages=[Package(name="p")],
        nodes=[Node(id="p.A", name="A", package="p", stereotype=None)],
        edges=[],
    )
    recovered = json_to_graph(graph_to_json(g))
    assert recovered.nodes[0].stereotype is None


def test_json_pretty_print():
    g = _canonical_graph()
    pretty = graph_to_json(g, indent=2)
    parsed = json.loads(pretty)
    assert parsed["repo"] == "test-repo"


def test_dict_to_graph_missing_optional_fields():
    d = {"repo": "r", "target_nodes": 10}
    g = dict_to_graph(d)
    assert g.packages == []
    assert g.nodes == []
    assert g.edges == []


# validator.py


def test_validator_clean_graph_no_warnings():
    g = _canonical_graph()
    # Prüfung der Knotenzahl überspringen (der Graph hat 2 Knoten, bei target_nodes=20 käme eine Warnung)
    repaired, warnings = validate(g)
    assert warnings == []
    assert len(repaired.nodes) == 2
    assert len(repaired.edges) == 1


def test_validator_dedup_nodes_keeps_first():
    g = AbstractGraph(
        repo="r",
        target_nodes=5,
        packages=[Package(name="p")],
        nodes=[
            Node(id="p.A", name="A", package="p", attributes=["x: int"]),
            Node(id="p.A", name="A", package="p", attributes=["y: str"]),  # doppelt
        ],
        edges=[],
    )
    repaired, warnings = validate(g)
    assert len(repaired.nodes) == 1
    assert repaired.nodes[0].attributes == ["x: int"]
    assert any("Duplicate" in w for w in warnings)


def test_validator_preserves_all_attributes():
    node = Node(id="p.A", name="A", package="p", attributes=["a1", "a2", "a3", "a4", "a5", "a6"])
    g = AbstractGraph(repo="r", target_nodes=5, packages=[Package(name="p")], nodes=[node], edges=[])
    repaired, _ = validate(g)
    assert len(repaired.nodes[0].attributes) == 6


def test_validator_preserves_all_methods():
    node = Node(id="p.A", name="A", package="p", methods=["m1()", "m2()", "m3()", "m4()"])
    g = AbstractGraph(repo="r", target_nodes=5, packages=[Package(name="p")], nodes=[node], edges=[])
    repaired, _ = validate(g)
    assert len(repaired.nodes[0].methods) == 4


def test_validator_invalid_stereotype_set_to_none():
    node = Node(id="p.A", name="A", package="p", stereotype="singleton")
    g = AbstractGraph(repo="r", target_nodes=5, packages=[Package(name="p")], nodes=[node], edges=[])
    repaired, warnings = validate(g)
    assert repaired.nodes[0].stereotype is None
    assert any("stereotype" in w for w in warnings)


def test_validator_valid_stereotypes_preserved():
    for stereo in ("abstract", "interface", "dataclass", "enum"):
        node = Node(id="p.A", name="A", package="p", stereotype=stereo)
        g = AbstractGraph(repo="r", target_nodes=5, packages=[Package(name="p")], nodes=[node], edges=[])
        repaired, warnings = validate(g)
        assert repaired.nodes[0].stereotype == stereo
        assert not any("stereotype" in w for w in warnings)


def test_validator_auto_creates_missing_package():
    node = Node(id="myapp.core.Foo", name="Foo", package="myapp.core")
    g = AbstractGraph(repo="r", target_nodes=5, packages=[], nodes=[node], edges=[])
    repaired, _ = validate(g)
    pkg_names = {p.name for p in repaired.packages}
    assert "myapp.core" in pkg_names
    assert "myapp" in pkg_names


def test_validator_auto_created_package_parent_chain():
    node = Node(id="a.b.c.D", name="D", package="a.b.c")
    g = AbstractGraph(repo="r", target_nodes=5, packages=[], nodes=[node], edges=[])
    repaired, _ = validate(g)
    pkg_map = {p.name: p.parent for p in repaired.packages}
    assert pkg_map["a"] is None
    assert pkg_map["a.b"] == "a"
    assert pkg_map["a.b.c"] == "a.b"


def test_validator_drop_edge_invalid_type():
    g = AbstractGraph(
        repo="r",
        target_nodes=5,
        packages=[Package(name="p")],
        nodes=[Node(id="p.A", name="A", package="p"), Node(id="p.B", name="B", package="p")],
        edges=[Edge(source="p.A", target="p.B", type="uses")],
    )
    repaired, warnings = validate(g)
    assert len(repaired.edges) == 0
    assert any("edge type" in w.lower() for w in warnings)


def test_validator_drop_edge_missing_source():
    g = AbstractGraph(
        repo="r",
        target_nodes=5,
        packages=[Package(name="p")],
        nodes=[Node(id="p.B", name="B", package="p")],
        edges=[Edge(source="p.Missing", target="p.B", type="inheritance")],
    )
    repaired, warnings = validate(g)
    assert len(repaired.edges) == 0
    assert any("source" in w for w in warnings)


def test_validator_drop_edge_missing_target():
    g = AbstractGraph(
        repo="r",
        target_nodes=5,
        packages=[Package(name="p")],
        nodes=[Node(id="p.A", name="A", package="p")],
        edges=[Edge(source="p.A", target="p.Missing", type="dependency")],
    )
    repaired, warnings = validate(g)
    assert len(repaired.edges) == 0
    assert any("target" in w for w in warnings)


def test_validator_node_count_warning_below():
    g = AbstractGraph(
        repo="r",
        target_nodes=20,
        packages=[Package(name="p")],
        nodes=[Node(id="p.A", name="A", package="p")],
        edges=[],
    )
    _, warnings = validate(g, target_nodes=20, node_tolerance=0.2)
    assert any("count" in w.lower() for w in warnings)


def test_validator_node_count_no_warning_in_range():
    nodes = [Node(id=f"p.N{i}", name=f"N{i}", package="p") for i in range(20)]
    g = AbstractGraph(repo="r", target_nodes=20, packages=[Package(name="p")], nodes=nodes, edges=[])
    _, warnings = validate(g, target_nodes=20, node_tolerance=0.2)
    assert not any("count" in w.lower() for w in warnings)


def test_validator_does_not_mutate_original():
    original_node = Node(id="p.A", name="A", package="p", attributes=["a"] * 6)
    g = AbstractGraph(repo="r", target_nodes=5, packages=[Package(name="p")], nodes=[original_node], edges=[])
    validate(g)
    assert len(original_node.attributes) == 6  # unverändert


def test_validator_multiple_repairs_in_one_pass():
    g = AbstractGraph(
        repo="r",
        target_nodes=5,
        packages=[],
        nodes=[
            Node(id="x.A", name="A", package="x", stereotype="bad", attributes=["a"] * 6),
            Node(id="x.A", name="A", package="x"),  # doppelt
        ],
        edges=[Edge(source="x.A", target="x.Z", type="inheritance")],  # target fehlt
    )
    repaired, warnings = validate(g)
    assert len(repaired.nodes) == 1
    assert repaired.nodes[0].stereotype is None
    assert len(repaired.nodes[0].attributes) == 6  # Member werden nicht gekürzt
    assert len(repaired.edges) == 0
    assert len(warnings) >= 3


# plantuml.py


_EXPECTED_CANONICAL = """\
@startuml

package "app" {
  package "domain" {
    class Order <<dataclass>> {
      id: int
      status: OrderStatus
      --
      submit()
      cancel()
    }

    abstract class Entity {
      id: int
      --
      validate()
    }
  }
}

Order --|> Entity

@enduml
"""


def test_plantuml_canonical_output():
    assert to_plantuml(_canonical_graph()) == _EXPECTED_CANONICAL


def test_plantuml_node_no_body():
    g = AbstractGraph(
        repo="r",
        target_nodes=5,
        packages=[Package(name="p")],
        nodes=[Node(id="p.A", name="A", package="p")],
        edges=[],
    )
    puml = to_plantuml(g)
    # Auf die class-Zeile darf kein Rumpf-Block folgen
    assert "  class A\n" in puml
    assert "class A {" not in puml


def test_plantuml_only_attributes_no_separator():
    g = AbstractGraph(
        repo="r",
        target_nodes=5,
        packages=[Package(name="p")],
        nodes=[Node(id="p.A", name="A", package="p", attributes=["x: int"])],
        edges=[],
    )
    puml = to_plantuml(g)
    assert "x: int" in puml
    assert "--" not in puml


def test_plantuml_only_methods_no_separator():
    g = AbstractGraph(
        repo="r",
        target_nodes=5,
        packages=[Package(name="p")],
        nodes=[Node(id="p.A", name="A", package="p", methods=["run()"])],
        edges=[],
    )
    puml = to_plantuml(g)
    assert "run()" in puml
    assert "--" not in puml


def test_plantuml_interface_stereotype():
    g = AbstractGraph(
        repo="r",
        target_nodes=5,
        packages=[Package(name="p")],
        nodes=[Node(id="p.I", name="I", package="p", stereotype="interface")],
        edges=[],
    )
    assert "interface I" in to_plantuml(g)


def test_plantuml_enum_stereotype():
    g = AbstractGraph(
        repo="r",
        target_nodes=5,
        packages=[Package(name="p")],
        nodes=[Node(id="p.E", name="E", package="p", stereotype="enum")],
        edges=[],
    )
    assert "enum E" in to_plantuml(g)


def test_plantuml_composition_edge():
    g = AbstractGraph(
        repo="r",
        target_nodes=5,
        packages=[Package(name="p")],
        nodes=[Node(id="p.A", name="A", package="p"), Node(id="p.B", name="B", package="p")],
        edges=[Edge(source="p.A", target="p.B", type="composition")],
    )
    assert "A *-- B" in to_plantuml(g)


def test_plantuml_dependency_edge():
    g = AbstractGraph(
        repo="r",
        target_nodes=5,
        packages=[Package(name="p")],
        nodes=[Node(id="p.A", name="A", package="p"), Node(id="p.B", name="B", package="p")],
        edges=[Edge(source="p.A", target="p.B", type="dependency")],
    )
    assert "A ..> B" in to_plantuml(g)


def test_plantuml_ambiguous_names_use_full_id():
    g = AbstractGraph(
        repo="r",
        target_nodes=5,
        packages=[Package(name="a"), Package(name="b")],
        nodes=[
            Node(id="a.Foo", name="Foo", package="a"),
            Node(id="b.Foo", name="Foo", package="b"),
        ],
        edges=[Edge(source="a.Foo", target="b.Foo", type="dependency")],
    )
    puml = to_plantuml(g)
    assert 'class "Foo" as type_' in puml
    relation = next(line for line in puml.splitlines() if " ..> " in line)
    assert relation.startswith("type_") and " ..> type_" in relation
    assert check_plantuml(puml) == []


def test_plantuml_nested_name_collisions_get_distinct_aliases():
    g = AbstractGraph(
        repo="r", target_nodes=None, packages=[Package(name="p")],
        nodes=[
            Node(id="p.OuterA.Listener", name="Listener", package="p"),
            Node(id="p.OuterB.Listener", name="Listener", package="p"),
        ],
        edges=[Edge(source="p.OuterA.Listener", target="p.OuterB.Listener", type="association")],
    )
    puml = to_plantuml(g)
    assert 'class "OuterA.Listener" as type_' in puml
    assert 'class "OuterB.Listener" as type_' in puml
    aliases = [line.rsplit(" as ", 1)[-1] for line in puml.splitlines() if 'class "Outer' in line]
    assert len(set(aliases)) == 2
    assert check_plantuml(puml) == []


def test_plantuml_trailing_newline():
    assert to_plantuml(_canonical_graph()).endswith("\n")


def test_plantuml_starts_with_startuml():
    assert to_plantuml(_canonical_graph()).startswith("@startuml\n")


def test_check_plantuml_valid_output():
    puml = to_plantuml(_canonical_graph())
    assert check_plantuml(puml) == []


def test_check_plantuml_unbalanced_braces():
    puml = "@startuml\npackage \"p\" {\nclass A {\n@enduml\n"
    warnings = check_plantuml(puml)
    assert any("brace" in w.lower() for w in warnings)


def test_check_plantuml_undeclared_class_in_relation():
    puml = "@startuml\nclass A {}\nA --|> Missing\n@enduml\n"
    warnings = check_plantuml(puml)
    assert any("Missing" in w for w in warnings)
