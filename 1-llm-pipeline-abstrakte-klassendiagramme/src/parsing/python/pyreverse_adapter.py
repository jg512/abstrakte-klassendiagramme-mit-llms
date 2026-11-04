from __future__ import annotations

import logging
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from src.schema.graph import AbstractGraph, Edge, Node, Package

logger = logging.getLogger(__name__)

# Aufruf als Unterprozess

_VENV_PYREVERSE = str(Path(sys.executable).parent / "pyreverse")

_CMDS = [
    [_VENV_PYREVERSE, "-o", "plantuml", "-p", "output"],
    ["pyreverse", "-o", "plantuml", "-p", "output"],
]


def run_pyreverse(root: Path) -> AbstractGraph | None:
    """pyreverse auf *root* ausführen und einen normalisierten AbstractGraph zurückgeben.

    Gibt None zurück, wenn pyreverse nicht installiert ist oder aus irgendeinem
    Grund scheitert. Der Aufrufer behandelt None als weichen Fehler und lässt die
    prune-Varianten (früher M4a/M4b) aus.
    """
    packages = _find_top_level_packages(root)
    targets = packages if packages else [root]

    with tempfile.TemporaryDirectory(prefix="abstract_uml_pyrev_") as tmp:
        tmp_path = Path(tmp)
        # Aus der Repo-Wurzel starten, damit relative Paketnamen richtig aufgelöst werden.
        succeeded = _invoke(targets, out_dir=tmp_path, cwd=root)
        if not succeeded:
            return None

        puml_files = sorted(tmp_path.glob("classes_*.plantuml"))
        if not puml_files:
            logger.warning("pyreverse ran but produced no classes_*.plantuml in %s", tmp)
            return None

        puml_parts = []
        for pf in puml_files:
            text = pf.read_text(encoding="utf-8", errors="replace")
            text = re.sub(r"@start\w+[^\n]*\n?", "", text)
            text = re.sub(r"@end\w+[^\n]*\n?", "", text)
            puml_parts.append(text)
        puml = "@startuml\n" + "\n".join(puml_parts) + "\n@enduml\n"
        graph = parse_pyreverse_output(puml, repo=root.name)
        if not graph.nodes:
            logger.warning("pyreverse produced output but parsed 0 nodes for %s", root.name)
            return None
        return graph


def _find_top_level_packages(root: Path) -> list[str]:
    """Namen der Python-Pakete oberster Ebene (Verzeichnisse mit __init__.py) unter root liefern."""
    skip = {"test", "tests", "docs", "doc", "examples", "example", "build", "dist"}
    packages = []
    for child in sorted(root.iterdir()):
        if (
            child.is_dir()
            and (child / "__init__.py").exists()
            and child.name not in skip
            and not child.name.startswith(".")
        ):
            packages.append(child.name)
    return packages


def _invoke(targets: list[str | Path], out_dir: Path, cwd: Path) -> bool:
    str_targets = [str(t) for t in targets]
    for base_cmd in _CMDS:
        cmd = [*base_cmd, "-d", str(out_dir), *str_targets]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(cwd),
                timeout=60,
            )
            if result.returncode == 0:
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    logger.warning("pyreverse not available or failed for %s", cwd.name)
    return False


# PlantUML-Parser

# class "Anzeigename" as voll.qualifizierter.Alias  oder  ... <<stereo>>
# Gruppe 1 = Anzeigename, Gruppe 2 = Alias (wird in Beziehungen benutzt), Gruppe 3 = Stereotyp
_CLASS_ALIASED = re.compile(
    r'^(?:abstract\s+)?class\s+"([^"]+)"\s+as\s+(\S+?)(?:\s+<<([^>]+)>>)?\s*\{?\s*$'
)
# class Kurzname  oder  abstract class Kurzname  oder  class Name <<stereo>>
_CLASS_SIMPLE = re.compile(
    r'^(?:abstract\s+)?class\s+(\S+?)(?:\s+<<([^>]+)>>)?\s*\{?\s*$'
)
# interface Name
_IFACE = re.compile(r'^interface\s+(\S+?)\s*\{?\s*$')
# namespace-/package-Block: `namespace foo.bar {` oder `package "a.b" as P {`
_NS_OPEN = re.compile(r'^(?:namespace|package)\s+"?([^"{\s]+)"?\s*(?:as\s+\S+)?\s*\{?\s*$')

# Attributzeile in einer Klasse: optional {field} vorn, dann "name : typ"
_ATTR = re.compile(r'^(?:\{field\}\s*)?(\S+)\s*:\s*(.+)$')
# Methodenzeile: alles, was auf ")" endet (darf Argumente enthalten)
_METHOD = re.compile(r'^(?:\{method\}\s*)?(\S.*\))$')

# Muster für Beziehungen. Ein optionales Label am Ende wird vor dem Vergleich entfernt
_RELS = [
    (re.compile(r'^(\S+)\s+--\|>\s+(\S+)'), "inheritance", False),   # A --|> B  (A erbt von B)
    (re.compile(r'^(\S+)\s+<\|--\s+(\S+)'), "inheritance", True),    # A <|-- B  (B erbt von A, also vertauschen)
    (re.compile(r'^(\S+)\s+\*--\s+(\S+)'), "composition", False),
    (re.compile(r'^(\S+)\s+--\*\s+(\S+)'), "composition", True),
    (re.compile(r'^(\S+)\s+[o#]\s*--\s+(\S+)'), "composition", False),
    (re.compile(r'^(\S+)\s+--\s*[o#]\s+(\S+)'), "composition", True),
    (re.compile(r'^(\S+)\s+-->\s+(\S+)'), "dependency", False),
    (re.compile(r'^(\S+)\s+<--\s+(\S+)'), "dependency", True),
    (re.compile(r'^(\S+)\s+\.\.\>\s+(\S+)'), "dependency", False),
    (re.compile(r'^(\S+)\s+<\.\.\s+(\S+)'), "dependency", True),
]


def parse_pyreverse_output(puml: str, repo: str = "") -> AbstractGraph:
    """Eine PlantUML-Ausgabe von pyreverse in einen AbstractGraph umwandeln."""
    _classes: list[dict] = []   # {qualified_name, alias, name, stereotype, attrs, methods}
    _edges: list[tuple[str, str, str]] = []   # (source, type, target)

    ns_stack: list[str] = []    # Stapel der aktuellen namespace-Präfixe
    current: dict | None = None  # Klasse, die gerade gelesen wird

    for raw_line in puml.splitlines():
        line = raw_line.strip()

        # Direktiven und Leerzeilen überspringen
        if not line or line.startswith("@") or line.startswith("set ") or line == "--":
            continue

        # Schließende Klammer
        if line == "}":
            if current is not None:
                _classes.append(current)
                current = None
            elif ns_stack:
                ns_stack.pop()
            continue

        # Innerhalb eines Klassenrumpfs
        if current is not None:
            _parse_body_line(line, current)
            continue

        # namespace-/package-Block geht auf
        m = _NS_OPEN.match(line)
        if m and "{" in line:
            ns_stack.append(m.group(1))
            continue

        # Deklaration von Klasse oder Interface
        cinfo = _parse_class_header(line, ns_stack)
        if cinfo is not None:
            current = cinfo
            if "{" not in line:
                # Kein Rumpf, also sofort abschließen
                _classes.append(current)
                current = None
            continue

        # Beziehungszeile
        rel = _parse_relation(line)
        if rel:
            _edges.append(rel)

    if current is not None:
        _classes.append(current)

    return _build_graph(_classes, _edges, repo)


def _parse_class_header(line: str, ns_stack: list[str]) -> dict | None:
    """Ein frisches dict mit Klasseninfos zurückgeben, wenn *line* eine Klassen- oder Interface-Deklaration ist."""
    prefix = ".".join(ns_stack) + "." if ns_stack else ""

    m = _CLASS_ALIASED.match(line)
    if m:
        display_name = m.group(1)
        alias = m.group(2)          # z. B. loguru._colorizer.AnsiParser, wird in Beziehungen benutzt
        stereo = _map_stereotype(m.group(3))
        if stereo is None and line.lstrip().startswith("abstract "):
            stereo = "abstract"
        short = display_name.split(".")[-1]
        # Den Alias als qualified_name nehmen, weil die Beziehungen auf ihn verweisen
        return {"qualified_name": alias, "alias": alias, "name": short,
                "stereotype": stereo, "attrs": [], "methods": []}

    m = _CLASS_SIMPLE.match(line)
    if m:
        short = m.group(1)
        # Ein durchgerutschtes `{` am Ende entfernen
        short = short.rstrip("{").strip()
        stereo = _map_stereotype(m.group(2))
        if line.lstrip().startswith("abstract "):
            stereo = "abstract"
        qualified = prefix + short
        return {"qualified_name": qualified, "name": short,
                "stereotype": stereo, "attrs": [], "methods": []}

    m = _IFACE.match(line)
    if m:
        short = m.group(1).rstrip("{").strip()
        qualified = prefix + short
        return {"qualified_name": qualified, "name": short,
                "stereotype": "interface", "attrs": [], "methods": []}

    return None


def _parse_body_line(line: str, cinfo: dict) -> None:
    if line == "--":
        return

    m = _ATTR.match(line)
    if m:
        cinfo["attrs"].append(f"{m.group(1)}: {m.group(2).strip()}")
        return

    m = _METHOD.match(line)
    if m:
        cinfo["methods"].append(m.group(1))
        return


def _parse_relation(line: str) -> tuple[str, str, str] | None:
    # Optionales Label entfernen (z. B. "A o-- B : jobs" wird zu "A o-- B")
    no_label = re.sub(r'\s*:.*$', '', line).strip()

    for pattern, rel_type, swap in _RELS:
        m = pattern.match(no_label)
        if m:
            src, dst = (m.group(2), m.group(1)) if swap else (m.group(1), m.group(2))
            return src, rel_type, dst

    return None


def _map_stereotype(raw: str | None) -> str | None:
    if not raw:
        return None
    lower = raw.lower().strip()
    mapping = {
        "abstract": "abstract",
        "interface": "interface",
        "dataclass": "dataclass",
        "enum": "enum",
    }
    return mapping.get(lower)


# Aufbau des Graphen

def _build_graph(
    classes: list[dict],
    edges: list[tuple[str, str, str]],
    repo: str,
) -> AbstractGraph:
    # Qualifizierte Namen für die Prüfung der Beziehungen indizieren
    known: set[str] = {c["qualified_name"] for c in classes}

    # Pakethierarchie aufbauen
    packages = _infer_packages(known)

    nodes = []
    for c in classes:
        qname = c["qualified_name"]
        pkg = ".".join(qname.split(".")[:-1]) if "." in qname else ""
        nodes.append(Node(
            id=qname,
            name=c["name"],
            package=pkg,
            stereotype=c["stereotype"],
            attributes=c["attrs"][:15],
            methods=c["methods"][:15],
        ))

    graph_edges = []
    for src, rel_type, dst in edges:
        if src in known and dst in known and src != dst:
            graph_edges.append(Edge(source=src, target=dst, type=rel_type))

    return AbstractGraph(
        repo=repo,
        target_nodes=0,  # Platzhalter: pyreverse liefert den vollen Graphen, das Ziel wird zur Laufzeit gesetzt
        packages=packages,
        nodes=nodes,
        edges=graph_edges,
    )


def _infer_packages(qualified_names: set[str]) -> list[Package]:
    """Die vollständige Menge der Pakete aus allen qualifizierten Klassennamen ableiten."""
    pkg_names: set[str] = set()
    for qname in qualified_names:
        parts = qname.split(".")
        for i in range(1, len(parts)):
            pkg_names.add(".".join(parts[:i]))

    packages: list[Package] = []
    for name in sorted(pkg_names):
        parent_parts = name.rsplit(".", 1)
        parent = parent_parts[0] if len(parent_parts) > 1 else None
        if parent and parent not in pkg_names:
            parent = None
        packages.append(Package(name=name, parent=parent))

    return packages
