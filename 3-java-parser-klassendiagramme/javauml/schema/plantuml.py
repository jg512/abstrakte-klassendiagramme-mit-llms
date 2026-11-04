from __future__ import annotations

import re
import hashlib
from collections import defaultdict

from .graph import AbstractGraph, Node, Package

_EDGE_ARROWS: dict[str, str] = {
    "inheritance": "--|>",
    "realization": "..|>",
    "composition": "*--",
    "aggregation": "o--",
    "association": "-->",
    "dependency": "..>",
    "nesting": "+--",     # äußere Klasse +-- innere Klasse
}

_DECL_RE = re.compile(
    r'^\s*(?:abstract\s+)?(?:class|interface|enum)\s+(?:"[^"]+"\s+as\s+)?(\S+)'
)
_REL_RE = re.compile(
    r'^\s*(\S+)\s+(?:"[^"]*"\s+)?(?:--\|>|\.\.\|>|\*--|o--|-->|\.\.>|\+--)\s+(?:"[^"]*"\s+)?(\S+)'
)


def _leaf_name(package_name: str) -> str:
    return package_name.rsplit(".", 1)[-1]


def _puml_escape(s: str) -> str:
    return s.replace('"', '\\"').replace("{", "").replace("}", "")


def _class_header(node: Node, alias: str | None = None) -> str:
    display = node.name
    if alias is not None and node.package and node.id.startswith(node.package + "."):
        display = node.id[len(node.package) + 1:]
    name = f'"{_puml_escape(display)}" as {alias}' if alias else _puml_escape(display)
    if node.stereotype == "abstract":
        return f"abstract class {name}"
    if node.stereotype == "interface":
        return f"interface {name}"
    if node.stereotype == "enum":
        return f"enum {name}"
    if node.stereotype in ("dataclass", "exception"):
        return f"class {name} <<{node.stereotype}>>"
    return f"class {name}"


def _render_node(node: Node, indent: int, alias: str | None = None) -> list[str]:
    pad = "  " * indent
    header = _class_header(node, alias)

    has_attrs = bool(node.attributes)
    has_methods = bool(node.methods)

    if not has_attrs and not has_methods:
        return [f"{pad}{header}"]

    inner = "  "
    lines = [f"{pad}{header} {{"]
    if has_attrs:
        for attr in node.attributes:
            lines.append(f"{pad}{inner}{_puml_escape(attr)}")
    if has_attrs and has_methods:
        lines.append(f"{pad}{inner}--")
    if has_methods:
        for method in node.methods:
            lines.append(f"{pad}{inner}{_puml_escape(method)}")
    lines.append(f"{pad}}}")
    return lines


def _render_package(
    pkg: Package,
    children_map: dict[str, list[Package]],
    nodes_by_pkg: dict[str, list[Node]],
    name_count: dict[str, int],
    aliases: dict[str, str],
    indent: int,
) -> list[str]:
    pad = "  " * indent
    leaf = _leaf_name(pkg.name)

    items: list[list[str]] = []
    for child in children_map.get(pkg.name, []):
        items.append(_render_package(child, children_map, nodes_by_pkg, name_count, aliases, indent + 1))
    for node in nodes_by_pkg.get(pkg.name, []):
        items.append(_render_node(node, indent + 1, aliases.get(node.id)))

    lines = [f'{pad}package "{leaf}" {{']
    for i, item in enumerate(items):
        lines.extend(item)
        if i < len(items) - 1:
            lines.append("")
    lines.append(f"{pad}}}")
    return lines


def _relation_ref(
    node_id: str, node: Node | None, name_count: dict[str, int], aliases: dict[str, str]
) -> str:
    if node_id in aliases:
        return aliases[node_id]
    if node is None:
        return node_id
    if name_count.get(node.name, 0) > 1:
        return node.id
    return node.name


def to_plantuml(graph: AbstractGraph) -> str:
    children_map: dict[str, list[Package]] = defaultdict(list)
    for pkg in graph.packages:
        if pkg.parent is not None:
            children_map[pkg.parent].append(pkg)

    nodes_by_pkg: dict[str, list[Node]] = defaultdict(list)
    node_by_id: dict[str, Node] = {}
    name_count: dict[str, int] = defaultdict(int)
    for node in graph.nodes:
        nodes_by_pkg[node.package].append(node)
        node_by_id[node.id] = node
        name_count[node.name] += 1
    aliases = {
        node.id: "type_" + hashlib.sha1(node.id.encode("utf-8")).hexdigest()[:10]
        for node in graph.nodes if name_count[node.name] > 1
    }

    roots = [pkg for pkg in graph.packages if pkg.parent is None]
    known_pkgs = {pkg.name for pkg in graph.packages}

    lines: list[str] = ["@startuml", ""]

    for root in roots:
        lines.extend(_render_package(root, children_map, nodes_by_pkg, name_count, aliases, indent=0))
        lines.append("")

    # Knoten, deren Paket nicht in graph.packages steht, landen auf oberster Ebene
    for node in graph.nodes:
        if node.package not in known_pkgs:
            lines.extend(_render_node(node, indent=0, alias=aliases.get(node.id)))
            lines.append("")

    if graph.edges:
        for edge in graph.edges:
            src_ref = _relation_ref(edge.source, node_by_id.get(edge.source), name_count, aliases)
            tgt_ref = _relation_ref(edge.target, node_by_id.get(edge.target), name_count, aliases)
            arrow = _EDGE_ARROWS[edge.type]
            src_card = f' "{_puml_escape(edge.source_card)}"' if edge.source_card else ""
            tgt_card = f'"{_puml_escape(edge.target_card)}" ' if edge.target_card else ""
            text = edge.label
            # PlantUML zeigt Stereotypen nur mit doppelten spitzen Klammern als «...» an.
            if text and text.startswith("«") and text.endswith("»"):
                text = f"<<{text[1:-1]}>>"
            label = f" : {_puml_escape(text)}" if text else ""
            lines.append(f"{src_ref}{src_card} {arrow} {tgt_card}{tgt_ref}{label}")
        lines.append("")

    lines.append("@enduml")
    lines.append("")

    return "\n".join(lines)


def check_plantuml(puml: str) -> list[str]:
    """Einfache Syntaxprüfung: Klammern paarig, alle referenzierten Klassen deklariert."""
    warnings: list[str] = []

    depth = 0
    for ch in puml:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
    if depth != 0:
        warnings.append(f"Unbalanced braces: net depth {depth}")

    declared: set[str] = set()
    for line in puml.splitlines():
        m = _DECL_RE.match(line)
        if m:
            declared.add(m.group(1))

    for line in puml.splitlines():
        m = _REL_RE.match(line)
        if m:
            for ref in (m.group(1), m.group(2)):
                if ref not in declared:
                    warnings.append(f"Undeclared class in relation: {ref!r}")

    return warnings
