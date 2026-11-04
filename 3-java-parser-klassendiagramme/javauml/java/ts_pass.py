from __future__ import annotations

import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from javauml.model import ClassInfo, FieldRef, FunctionInfo, MethodRef
from javauml.schema.graph import Diagnostic

logger = logging.getLogger(__name__)

# Typen, bei denen das *Element* das interessante Ende der Beziehung ist. Ein
# Feld `List<Client> clients` ist eine Aggregation von Client, keine Assoziation
# mit java.util.List. Arrays werden unten über `array_type` genauso behandelt.
_CONTAINER_TYPES = frozenset({
    "List", "ArrayList", "LinkedList", "Set", "HashSet", "TreeSet", "LinkedHashSet",
    "Collection", "Queue", "Deque", "ArrayDeque", "Iterable", "Stream",
    "Map", "HashMap", "TreeMap", "LinkedHashMap", "Optional",
})
_MANY_CONTAINER_TYPES = _CONTAINER_TYPES - {"Optional"}

# Felder, die für die Architektur nie interessant sind.
_FIELD_BLACKLIST = frozenset({"serialVersionUID"})

_TYPE_NODES = ("type_identifier", "generic_type", "array_type", "scoped_type_identifier")

# int, long, double, boolean und void bleiben drin: `count: int` und
# `getValueAt(int, int)` sagen im Klassendiagramm etwas aus. Sie können nie auf
# eine deklarierte Klasse zeigen und werden deshalb nie zu Kanten.
_PRIMITIVE_NODES = ("integral_type", "floating_point_type", "boolean_type", "void_type")

_DECL_NODES = {
    "class_declaration": None,
    "interface_declaration": "interface",
    "enum_declaration": "enum",
    "record_declaration": "record",
    "annotation_type_declaration": "annotation",
}

_ENCODINGS = ("utf-8", "cp1252", "latin-1")


class JavaParserUnavailable(RuntimeError):
    """tree-sitter bzw. tree-sitter-java ist nicht installiert."""


@dataclass
class JavaParseResult:
    classes: list[ClassInfo]
    functions: list[FunctionInfo] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)


def _get_parser():
    """Einen tree-sitter-Parser für Java bauen oder erklären, was fehlt."""
    try:
        import tree_sitter_java as tsj
        from tree_sitter import Language, Parser
    except ImportError as exc:  # pragma: no cover - exercised via error path
        raise JavaParserUnavailable(
            "Java support needs the tree-sitter parser. Install it with:\n"
            "    pip install 'abstract-uml[java]'\n"
            "  or: pip install tree-sitter tree-sitter-java"
        ) from exc
    return Parser(Language(tsj.language()))


def read_source(path: Path) -> tuple[bytes, str]:
    """Quelldatei als UTF-8-Bytes lesen und dabei das Encoding auf der Platte erraten.

    Alter Java-Code ist oft in ISO-8859-1 oder CP1252 statt UTF-8 gespeichert.
    Wer UTF-8 annimmt, verliert ganze Dateien, und Werkzeuge, die das tun,
    scheitern meist ohne Meldung. Der Parser erwartet UTF-8-Bytes. Deshalb wird
    der Text erst dekodiert und neu kodiert, statt die Rohbytes weiterzugeben.
    """
    raw = path.read_bytes()
    for enc in _ENCODINGS:
        try:
            return raw.decode(enc).encode("utf-8"), enc
        except UnicodeDecodeError:
            continue
    logger.warning("Undecodable source %s — falling back to replacement chars", path)
    return raw.decode("utf-8", "replace").encode("utf-8"), "replace"


def _text(node) -> str:
    return node.text.decode("utf-8", "replace")


def _last(name: str | None) -> str | None:
    """Letzter Teil eines eventuell qualifizierten Typnamens.

    Typnamen behalten die Qualifizierung, die im Quelltext steht. Ohne sie wäre
    `java.util.Comparator` nicht mehr von einer gleichnamigen Projektklasse zu
    unterscheiden. Wo nur die *Art* des Typs zählt (Erkennung von Containern,
    Darstellung von Attributen), wird stattdessen der letzte Teil genommen.
    """
    return name.rsplit(".", 1)[-1] if name else name


def _split_type(node) -> tuple[str | None, list[str], bool]:
    """(roher_typ, typargumente, is_many) für einen Typknoten zurückgeben.

    `is_many` ist bei Arrays und bei den Containertypen oben gesetzt. In beiden
    Fällen gilt "0..*" für den Elementtyp, und zum Container gibt es keine Kante.
    """
    if node is None:
        return None, [], False
    if node.type == "array_type":
        raw, args, _ = _split_type(node.child_by_field_name("element"))
        return raw, args, True
    if node.type == "generic_type":
        raw: str | None = None
        args: list[str] = []
        for child in node.children:
            if child.type in ("type_identifier", "scoped_type_identifier") and raw is None:
                raw, _, _ = _split_type(child)
            elif child.type == "type_arguments":
                for arg in child.children:
                    if arg.type in _TYPE_NODES:
                        sub_raw, sub_args, _ = _split_type(arg)
                        if sub_raw:
                            args.append(sub_raw)
                        args.extend(sub_args)
                    elif arg.type == "wildcard":
                        for wc in arg.children:
                            if wc.type in _TYPE_NODES:
                                sub_raw, _, _ = _split_type(wc)
                                if sub_raw:
                                    args.append(sub_raw)
        return raw, args, _last(raw) in _MANY_CONTAINER_TYPES
    if node.type == "scoped_type_identifier":
        # Die Qualifizierung bleibt. Wird `java.util.Comparator` zu `Comparator`
        # gekürzt, löst es sich auf eine gleichnamige Projektklasse auf, und die
        # echte Beziehung geht ohne Meldung verloren. Wird `Bestellung.Position` zu
        # `Position` gekürzt, weiß niemand mehr, welcher verschachtelte Typ gemeint
        # war. _resolve liest beides richtig. Der Knoten verschachtelt sich nach
        # links: `java.util.Comparator` ist scoped(scoped(java, util), Comparator).
        # Die Teile müssen also rekursiv eingesammelt werden, die direkten Kinder
        # enthalten nur den letzten.
        ids: list[str] = []

        def collect(n) -> None:
            for child in n.children:
                if child.type == "type_identifier":
                    ids.append(_text(child))
                elif child.type == "scoped_type_identifier":
                    collect(child)

        collect(node)
        return (".".join(ids) if ids else None), [], False
    if node.type == "type_identifier" or node.type in _PRIMITIVE_NODES:
        return _text(node), [], False
    return None, [], False


def _render_type(raw: str, args: list[str], many: bool) -> str:
    """Lesbarer Typ für ein Attribut oder eine Parameterliste.

    Arrays und generische Container setzen beide `many`, sehen aber verschieden
    aus: `User[]` gegenüber `List<Session>`. Bei `List[]` ginge der Elementtyp
    verloren, und nur der ist interessant.
    """
    short = _last(raw)
    if args:
        return f"{short}<{', '.join(_last(a) for a in args)}>"
    return f"{short}[]" if many else short


def _field_targets(raw: str, args: list[str]) -> list[str]:
    """Typen, auf die ein Feld verweist, einschließlich seiner generischen Argumente.

    Bei einem bekannten Container wie ``List<Client>`` zählt nur ``Client``. Bei
    einer eigenen oder fremden Hülle wie ``Page<Client>`` oder
    ``NeurophArrayList<Neuron>`` kommen die Hülle und ihre Typargumente beide in
    Frage. Beim Bau des Graphen fallen Hüllen später weg, wenn sie außerhalb der
    analysierten Quellen liegen. Deklarierte Argumente bleiben.
    """
    targets = args if (args and _last(raw) in _CONTAINER_TYPES) else [raw, *args]
    return list(dict.fromkeys(targets))


def _supertype_names(node) -> list[str]:
    """Namen aus einer `superclass`- bzw. `super_interfaces`-Klausel, so wie sie im Quelltext stehen (auch qualifiziert)."""
    names: list[str] = []
    for child in node.children:
        if child.type in _TYPE_NODES:
            raw, _, _ = _split_type(child)
            if raw:
                names.append(raw)
        elif child.type == "type_list":
            for item in child.children:
                if item.type in _TYPE_NODES:
                    raw, _, _ = _split_type(item)
                    if raw:
                        names.append(raw)
    return names


def _modifiers(node) -> tuple[set[str], list[str]]:
    """(Schlüsselwort-Modifizierer, Annotationsnamen) aus einer Deklaration zurückgeben."""
    keywords: set[str] = set()
    annotations: list[str] = []
    for child in node.children:
        if child.type != "modifiers":
            continue
        for m in child.children:
            if m.type in ("marker_annotation", "annotation"):
                name = m.child_by_field_name("name")
                annotations.append("@" + (_text(name) if name else _text(m).lstrip("@")))
            else:
                keywords.add(_text(m))
    return keywords, annotations


def _is_accessor(name: str) -> bool:
    return name.startswith(("get", "set", "is", "has")) and len(name) > 3


def _visibility(modifiers: set[str]) -> str:
    if "public" in modifiers:
        return "+"
    if "protected" in modifiers:
        return "#"
    if "private" in modifiers:
        return "-"
    return "~"


def _method_signature(
    node, profile: str = "summary", implicit_public: bool = False
) -> str | None:
    """Entweder eine kurze Zusammenfassung oder eine vollständige Signatur im UML-Stil erzeugen."""
    name_node = node.child_by_field_name("name")
    if name_node is None:
        return None
    mods, _ = _modifiers(node)
    params: list[str] = []
    plist = node.child_by_field_name("parameters")
    if plist is not None:
        for p in plist.children:
            if p.type in ("formal_parameter", "spread_parameter"):
                raw, args, many = _split_type(p.child_by_field_name("type"))
                if raw:
                    rendered = _render_type(raw, args, many or p.type == "spread_parameter")
                    if profile in {"public-api", "full"}:
                        param_name = p.child_by_field_name("name")
                        params.append(
                            f"{_text(param_name)}: {rendered}" if param_name is not None else rendered
                        )
                    else:
                        params.append(rendered)
    signature = f"{_text(name_node)}({', '.join(params)})"
    if profile not in {"public-api", "full"}:
        return signature
    type_node = node.child_by_field_name("type")
    raw, args, many = _split_type(type_node)
    result = f": {_render_type(raw, args, many)}" if raw else ""
    throws: list[str] = []
    for child in node.children:
        if child.type == "throws":
            throws.extend(_supertype_names(child))
    throws_suffix = f" throws {', '.join(_last(t) or t for t in throws)}" if throws else ""
    flags = []
    if "static" in mods:
        flags.append("static")
    if "abstract" in mods:
        flags.append("abstract")
    if implicit_public and not ({"default", "static", "private"} & mods):
        flags.append("abstract")
    prefix = "+" if implicit_public else _visibility(mods)
    suffix = f" {{{', '.join(flags)}}}" if flags else ""
    return f"{prefix} {signature}{result}{throws_suffix}{suffix}"


def _method_type_refs(node) -> list[MethodRef]:
    name_node = node.child_by_field_name("name")
    if name_node is None:
        return []
    name = _text(name_node)
    line = node.start_point[0] + 1
    refs: list[MethodRef] = []
    type_node = node.child_by_field_name("type")
    raw, args, _ = _split_type(type_node)
    if raw and raw != "void":
        declared = _render_type(raw, args, False)
        for target in _field_targets(raw, args):
            refs.append(MethodRef(name, target, declared, line))
    plist = node.child_by_field_name("parameters")
    if plist is not None:
        for param in plist.children:
            if param.type not in ("formal_parameter", "spread_parameter"):
                continue
            raw, args, many = _split_type(param.child_by_field_name("type"))
            if not raw:
                continue
            declared = _render_type(raw, args, many)
            for target in _field_targets(raw, args):
                refs.append(MethodRef(name, target, declared, line))
    return refs


def _common_package_prefix(packages: set[str]) -> int:
    """Anzahl der führenden Paketteile, die alle Pakete im Repo gemeinsam haben.

    Java-Pakete sind absolut (`de.firma.projekt.model`). Schneidet man das
    gemeinsame Präfix ab, werden die IDs kürzer, und `module.split(".")[0]`
    wird zu einer brauchbaren Paketgruppe statt immer nur zum Herstellerpräfix
    ("de"). Die Pipeline in Ordner 1 braucht diese Form, damit Java-IDs wie die
    repo-relativen Python-Module aussehen.
    """
    # Gibt es neben benannten Paketen auch das unbenannte, könnte das Kürzen
    # verschiedene Typen wie `Item` und `company.Item` auf dieselbe ID legen.
    if "" in packages:
        return 0
    real = [p for p in packages if p]
    if not real:
        return 0
    split = [p.split(".") for p in real]
    first = split[0]
    n = 0
    while n < len(first) and all(n < len(s) and s[n] == first[n] for s in split):
        n += 1
    return n


def _build_module(path: Path, root: Path) -> str:
    """Das Maven- oder Gradle-Modul so gut es geht bestimmen, für doppelte voll qualifizierte Namen."""
    try:
        rel = path.relative_to(root)
    except ValueError:
        return ""
    parts = rel.parts
    if "src" in parts:
        prefix = parts[:parts.index("src")]
        if prefix:
            return ".".join(re.sub(r"\W+", "_", p) for p in prefix)
    parent = path.parent
    while parent != root and root in parent.parents:
        if any((parent / marker).exists() for marker in ("pom.xml", "build.gradle", "build.gradle.kts")):
            return ".".join(parent.relative_to(root).parts)
        parent = parent.parent
    return ""


def _parse_file(
    parser, path: Path, root: Path, records: list[dict], member_profile: str
) -> bool:
    """Für jeden in `path` deklarierten Typ einen Eintrag anhängen. Gibt True zurück, wenn die Datei keine Syntaxfehler hatte."""
    data, _enc = read_source(path)
    tree = parser.parse(data)
    clean = not tree.root_node.has_error
    if not clean:
        logger.debug("Syntax errors in %s — extracting what parsed", path)

    package = ""
    imports: list[str] = []
    for node in tree.root_node.children:
        if node.type == "package_declaration":
            for child in node.children:
                if child.type in ("scoped_identifier", "identifier"):
                    package = _text(child)
        elif node.type == "import_declaration":
            # Statische Typimporte werden genauso qualifiziert geschrieben wie normale
            # Importe. Importierte Felder und Methoden passen nie zum Typindex.
            value = _text(node).removeprefix("import").strip()
            value = value.removeprefix("static ").rstrip(";").strip()
            imports.append(value)

    stack: list[str] = []

    def visit(node) -> None:
        pushed = False
        if node.type in _DECL_NODES:
            name_node = next((c for c in node.children if c.type == "identifier"), None)
            if name_node is not None:
                record = _build_record(
                    node, _text(name_node), package, stack, path, root, member_profile
                )
                record["imports"] = imports
                records.append(record)
                stack.append(_text(name_node))
                pushed = True
        for child in node.children:
            visit(child)
        if pushed:
            stack.pop()

    visit(tree.root_node)
    return clean


def _build_record(
    node, name: str, package: str, stack: list[str], path: Path,
    root: Path, member_profile: str,
) -> dict:
    keywords, annotations = _modifiers(node)
    kind = _DECL_NODES[node.type]
    if kind is None and "abstract" in keywords:
        kind = "abstract"

    extends: list[str] = []
    implements: list[str] = []
    for child in node.children:
        if child.type == "superclass":
            extends.extend(_supertype_names(child))
        elif child.type == "extends_interfaces":
            # Die Grammatik benutzt diesen Knoten nur bei interface_declaration, also für
            # `interface A extends B`. Das ist in UML eine Generalisierung. Eine
            # Realisierung liegt nur vor, wenn ein Klassifizierer ein Interface
            # implementiert. Klassen und Enums laufen unten über `super_interfaces`.
            extends.extend(_supertype_names(child))
        elif child.type in ("super_interfaces", "interfaces"):
            implements.extend(_supertype_names(child))

    attributes: list[str] = []
    refs: list[FieldRef] = []
    method_refs: list[MethodRef] = []
    plain_methods: list[str] = []
    accessors: list[str] = []

    # Record-Komponenten verhalten sich wie Felder: `record Circle(double radius)`.
    params = node.child_by_field_name("parameters")
    if node.type == "record_declaration" and params is not None:
        for p in params.children:
            if p.type != "formal_parameter":
                continue
            raw, args, many = _split_type(p.child_by_field_name("type"))
            pname_node = p.child_by_field_name("name")
            if raw and pname_node is not None:
                pname = _text(pname_node)
                rendered = _render_type(raw, args, many)
                if member_profile != "structure":
                    attributes.append(f"{pname}: {rendered}")
                for target in _field_targets(raw, args):
                    refs.append(FieldRef(
                        pname, target, many, declared_type=rendered,
                        line=p.start_point[0] + 1,
                        relation_type="aggregation" if many else "association",
                        target_card="0..*" if many else None,
                    ))

    body = node.child_by_field_name("body")
    if body is not None:
        members = list(body.children)
        # Felder und Methoden eines Enums folgen in einem Hüllknoten auf die Konstanten.
        members = [m for child in members for m in
                   (child.children if child.type == "enum_body_declarations" else [child])]
        for member in members:
            if member.type in ("field_declaration", "constant_declaration"):
                _collect_field(member, attributes, refs, member_profile, kind)
            elif member.type in ("method_declaration", "constructor_declaration"):
                mods, _ = _modifiers(member)
                method_refs.extend(_method_type_refs(member))
                if member_profile == "structure":
                    continue
                if member_profile == "summary" and (
                    "private" in mods or member.type == "constructor_declaration"
                ):
                    continue
                implicitly_public = kind in {"interface", "annotation"} and "private" not in mods
                if member_profile == "public-api" and not (
                    {"public", "protected"} & mods or implicitly_public
                ):
                    continue
                sig = _method_signature(member, member_profile, implicitly_public)
                if sig is None:
                    continue
                (accessors if _is_accessor(sig.split("(")[0]) else plain_methods).append(sig)

    outer = ".".join(stack)
    local = f"{outer}.{name}" if outer else name
    type_params = node.child_by_field_name("type_parameters")
    parameters = []
    if type_params is not None:
        for param in type_params.named_children:
            ident = next((c for c in param.named_children if c.type == "type_identifier"), None)
            if ident is not None:
                parameters.append(_text(ident))
    return {
        "name": name,
        "package": package,
        "local": local,
        "type_parameters": parameters,
        "kind": kind,
        "extends": extends,
        "implements": implements,
        "annotations": annotations,
        "attributes": attributes,
        # Die übrigen Methoden kommen vor Gettern und Settern. In einer Codebasis
        # voller Beans würden diese sonst das ganze Budget füllen und
        # verdecken, was die Klasse tut.
        "methods": (
            (plain_methods + accessors)[:15]
            if member_profile == "summary" else plain_methods + accessors
        ),
        "field_refs": refs,
        "method_refs": method_refs,
        "file": path,
        "source_file": str(path.relative_to(root)),
        "build_module": _build_module(path, root),
        "line_start": node.start_point[0] + 1,
        "line_end": node.end_point[0] + 1,
    }


def _collect_field(
    member, attributes: list[str], refs: list[FieldRef], member_profile: str,
    owner_kind: str | None = None,
) -> None:
    raw, args, many = _split_type(member.child_by_field_name("type"))
    modifiers, annotations = _modifiers(member)
    annotation_names = {a.rsplit(".", 1)[-1] for a in annotations}
    for decl in member.children:
        if decl.type != "variable_declarator":
            continue
        name_node = decl.child_by_field_name("name")
        if name_node is None:
            continue
        fname = _text(name_node)
        if fname in _FIELD_BLACKLIST:
            continue
        if raw:
            field_many = many or any(c.type == "dimensions" for c in decl.children)
            rendered = _render_type(raw, args, field_many)
            visible = member_profile == "summary" or (
                member_profile == "full"
                or (member_profile == "public-api" and (
                    bool({"public", "protected"} & modifiers)
                    or owner_kind in {"interface", "annotation"}
                ))
            )
            if visible and member_profile != "structure":
                if member_profile in {"public-api", "full"}:
                    flags = []
                    if "static" in modifiers or owner_kind in {"interface", "annotation"}:
                        flags.append("static")
                    if "final" in modifiers or owner_kind in {"interface", "annotation"}:
                        flags.append("final")
                    suffix = f" {{{', '.join(flags)}}}" if flags else ""
                    visibility = (
                        "+" if owner_kind in {"interface", "annotation"}
                        else _visibility(modifiers)
                    )
                    attributes.append(f"{visibility} {fname}: {rendered}{suffix}")
                else:
                    attributes.append(f"{fname}: {rendered}")
            # Bei einem Container zählen die Elementtypen, sonst der Feldtyp selbst.
            # Private Felder zählen mit, denn in Java bilden das private Feld und der
            # öffentliche Getter zusammen die Assoziation.
            relation_type = "aggregation" if field_many else "association"
            target_card = "0..*" if field_many else None
            if _last(raw) == "Optional":
                relation_type, target_card = "association", "0..1"
            if annotation_names & {"@OneToMany", "@ManyToMany", "OneToMany", "ManyToMany"}:
                relation_type, target_card = "aggregation", "0..*"
            if annotation_names & {"@OneToOne", "@ManyToOne", "OneToOne", "ManyToOne"}:
                relation_type, target_card = "association", "0..1"
            value = decl.child_by_field_name("value")
            owns_value = value is not None and "object_creation_expression" in {
                value.type, *(c.type for c in value.children)
            }
            if annotation_names & {"@Embedded", "@ElementCollection", "Embedded", "ElementCollection"}:
                relation_type = "composition"
                target_card = "0..*" if field_many else "1"
            elif "final" in modifiers and owns_value and not field_many:
                relation_type, target_card = "composition", "1"
            for target in _field_targets(raw, args):
                refs.append(FieldRef(
                    fname, target, field_many, declared_type=rendered,
                    line=decl.start_point[0] + 1, relation_type=relation_type,
                    target_card=target_card,
                ))
        else:
            if member_profile not in {"structure", "public-api"}:
                attributes.append(fname)


def analyze_java(
    java_files: list[Path],
    root: Path,
    member_profile: str = "summary",
) -> JavaParseResult:
    """Java-Deklarationen samt Diagnosen aus einem Repo holen."""
    if member_profile not in {"structure", "summary", "public-api", "full"}:
        raise ValueError(f"Unknown Java member profile: {member_profile}")

    parser = _get_parser()
    records: list[dict] = []
    diagnostics: list[Diagnostic] = []
    failed = 0

    for path in sorted(java_files):
        try:
            if not _parse_file(parser, path, root, records, member_profile):
                failed += 1
                diagnostics.append(Diagnostic(
                    code="partial-parse",
                    message="tree-sitter reported syntax errors; usable declarations were retained",
                    source=str(path.relative_to(root)),
                ))
        except OSError as exc:
            logger.warning("Skipping %s: %s", path, exc)
            failed += 1
            diagnostics.append(Diagnostic(
                code="unreadable-source", message=str(exc),
                source=str(path.relative_to(root)), severity="error",
            ))

    if failed:
        logger.info("%d/%d Java files had syntax errors (partial extraction)",
                    failed, len(java_files))

    # Ein rekursiver Durchlauf durch das Repo kann zwei Kopien desselben voll
    # qualifizierten Namens in einem Source-Set finden. Dann wird nach festen
    # Regeln eine Deklaration behalten und der Konflikt gemeldet. Sonst würde
    # einfach der letzte Eintrag im Dictionary gewinnen.
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for record in records:
        source_id = ".".join(
            p for p in (record["package"], record["local"]) if p
        )
        grouped[(record["build_module"], source_id)].append(record)
    selected: list[dict] = []
    for (build_module, source_id), candidates in grouped.items():
        candidates.sort(key=lambda r: (len(Path(r["source_file"]).parts), r["source_file"]))
        selected.append(candidates[0])
        if len(candidates) > 1:
            diagnostics.append(Diagnostic(
                code="duplicate-declaration",
                message=f"Multiple declarations of {source_id} in one source set; kept {candidates[0]['source_file']}",
                source=build_module or ".",
                reference=source_id,
                candidates=[r["source_file"] for r in candidates],
            ))
    records = selected

    full_counts = Counter(
        ".".join(p for p in (r["package"], r["local"]) if p) for r in records
    )
    for source_id, count in full_counts.items():
        if count > 1:
            candidates = [r["source_file"] for r in records if ".".join(
                p for p in (r["package"], r["local"]) if p
            ) == source_id]
            diagnostics.append(Diagnostic(
                code="cross-module-declaration",
                message=f"{source_id} is declared in {count} build modules; module-qualified graph ids were used",
                reference=source_id,
                candidates=candidates,
                severity="info",
            ))

    strip = _common_package_prefix({r["package"] for r in records})
    classes: list[ClassInfo] = []
    for r in records:
        # `module` bleibt auch bei verschachtelten Typen das (repo-relative) Paket.
        # Das Clustern und die Paketübersicht gruppieren danach, und eine äußere
        # Klasse ist kein Paket. Die Verschachtelung sieht man weiter in qualified_name.
        module = ".".join(r["package"].split(".")[strip:]) if r["package"] else ""
        source_id = ".".join(p for p in (r["package"], r["local"]) if p)
        if full_counts[source_id] > 1:
            build_module = r["build_module"] or "root"
            module_prefix = "modules." + re.sub(r"[^A-Za-z0-9_.]", "_", build_module)
            module = ".".join(p for p in (module_prefix, module) if p)
        qualified = f"{module}.{r['local']}" if module else r["local"]
        classes.append(ClassInfo(
            name=r["name"],
            qualified_name=qualified,
            module=module,
            bases=r["extends"],
            decorators=r["annotations"],
            attributes=(r["attributes"][:15] if member_profile == "summary" else r["attributes"]),
            methods=r["methods"],
            file=r["file"],
            line_start=r["line_start"],
            line_end=r["line_end"],
            kind=r["kind"],
            interfaces=r["implements"],
            field_refs=r["field_refs"],
            source_qualified_name=".".join(p for p in (r["package"], r["local"]) if p),
            source_package=r["package"],
            imports=r["imports"],
            type_parameters=r["type_parameters"],
            method_refs=r["method_refs"],
            build_module=r["build_module"],
            source_file=r["source_file"],
        ))

    logger.debug("Java pass: %d types from %d files (stripped %d package segments)",
                 len(classes), len(java_files), strip)
    return JavaParseResult(classes=classes, diagnostics=diagnostics)


def run_java_pass(
    java_files: list[Path],
    root: Path,
    member_profile: str = "summary",
) -> tuple[list[ClassInfo], list[FunctionInfo]]:
    """Alte Schnittstelle des Java-Parsers. Wer die Diagnosen braucht, nimmt ``analyze_java``."""
    result = analyze_java(java_files, root, member_profile)
    return result.classes, result.functions
