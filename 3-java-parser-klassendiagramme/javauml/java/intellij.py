"""Klassendiagramm nach den Regeln von IntelliJ IDEA.

Der normale Extraktor liest nur Deklarationen: Felder, ``extends`` und
``implements``. IntelliJ liest zusätzlich die Methodenrümpfe und ordnet jeden
aufgelösten Verweis der Klasse zu, die das Ziel deklariert. Dadurch tauchen
Abhängigkeiten auf, die über eine dritte Klasse laufen. Beispiel aus RaiseMeUp:
``PetObserver`` erwähnt ``Job`` nirgends, ruft aber
``RaiseMeUp.getCurrentJob().getImpactenergy()`` auf. ``getImpactenergy`` ist in
``Job`` deklariert, also hängt ``PetObserver`` von ``Job`` ab.

Die Regeln sind aus den Diagrammen abgeleitet, die IntelliJ für die neun
Projekte von Zhang/Hebig erzeugt hat:

* Vererbung (``extends``) und Realisierung (``implements``) wie gewohnt.
* Ein Feld, dessen Typ direkt eine Klasse im Diagramm ist, wird zu einer
  Komposition mit "1" an beiden Enden und dem Feldnamen als Rolle. Ein Feld, das
  eine Collection oder ein Array davon ist, bekommt "*" am Ziel. Maps zählen
  nicht als Collection.
* Eine verschachtelte Klasse hängt mit ihrer äußeren Klasse über eine eigene
  Kante zusammen (bei IntelliJ rot mit Kreis und Plus an der äußeren Klasse).
* Jeder Verweis im Code wird zur Abhängigkeit: Typen in Signaturen, Feldern,
  lokalen Variablen, Casts, ``instanceof``, Klassenliterale, statische Zugriffe
  über den Klassennamen und Methodenaufrufe. Ein Methodenaufruf zählt für die
  Klasse, die die Methode deklariert, auch über Aufrufketten hinweg. Zugriffe
  auf Felder zählen nicht.
* ``new X()`` macht daraus eine Abhängigkeit mit ``«create»``.
* Eine einfache Abhängigkeit wird nicht gezeichnet, wenn zwischen denselben
  Klassen in derselben Richtung schon eine Vererbung, eine Realisierung oder
  eine Feldbeziehung besteht, oder wenn eine innere Klasse ihre äußere benutzt.
  ``«create»`` bleibt immer stehen.
* Eine Klasse hängt von sich selbst ab, wenn sie eigene Methoden aufruft oder
  ihren eigenen Typ benutzt (Cast, ``instanceof``, Rückgabetyp), nicht aber,
  wenn sie nur eigene Felder liest.

Welche Klassen im Diagramm stehen, entscheidet der Mensch, der es in IntelliJ
anlegt. Diese Auswahl wird deshalb übergeben. Ohne Auswahl kommen alle Klassen
des Projekts hinein.

IntelliJ zeichnet nur, was es auflösen kann. Wie viel das ist, hängt davon ab,
wie das Projekt geöffnet wurde. ``IdeEnvironment`` bildet die Fälle ab, die in
den Diagrammen vorkommen: kein JDK eingerichtet (dann sind ``List`` und
``LinkedList`` unbekannt und Collection-Felder bekommen keine Linie) und ein
falsch gesetztes Source-Root (dann findet IntelliJ Klassen aus demselben Paket
nicht mehr, Klassen mit ausdrücklichem ``import`` aber schon).
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from javauml.model import ClassInfo
from javauml.java.graph_builder import EXTERNAL_PACKAGE, _STEREOTYPE_MAP, _packages
from javauml.java.resolution import JavaTypeResolver
from javauml.java.ts_pass import (
    _DECL_NODES,
    _get_parser,
    _modifiers,
    _text,
    analyze_java,
    read_source,
)
from javauml.schema.graph import AbstractGraph, Edge, EdgeEvidence, Node

logger = logging.getLogger(__name__)

# Collections aus dem JDK, bei denen IntelliJ "*" an das Feld schreibt. Alle sind
# Iterable. Maps fehlen, weil IntelliJ für sie keine Linie zeichnet.
_JDK_ITERABLES = frozenset({
    "Iterable", "Collection", "List", "ArrayList", "LinkedList", "Set", "HashSet",
    "LinkedHashSet", "TreeSet", "SortedSet", "NavigableSet", "Queue", "Deque",
    "ArrayDeque", "PriorityQueue", "Vector", "Stack", "CopyOnWriteArrayList",
    "CopyOnWriteArraySet", "ConcurrentLinkedQueue", "ConcurrentLinkedDeque",
    "BlockingQueue", "LinkedBlockingQueue", "ArrayBlockingQueue", "EnumSet",
    "AbstractList", "AbstractSet", "AbstractCollection",
})
_JDK_MAPS = frozenset({
    "Map", "HashMap", "LinkedHashMap", "TreeMap", "SortedMap", "NavigableMap",
    "ConcurrentHashMap", "ConcurrentMap", "Hashtable", "EnumMap", "WeakHashMap",
    "IdentityHashMap",
})
_JDK_ITERATORS = frozenset({"Iterator", "ListIterator", "Enumeration"})
_JDK_OTHER = frozenset({"Optional"})
_JDK_LANG = frozenset({
    "Object", "String", "Integer", "Long", "Double", "Float", "Short", "Byte",
    "Character", "Boolean", "Number", "Iterable", "Comparable", "Runnable",
    "Thread", "Exception", "RuntimeException", "Error", "Throwable", "Class",
    "Math", "System", "StringBuilder", "StringBuffer", "Enum", "Void",
})
_JDK_KNOWN = _JDK_ITERABLES | _JDK_MAPS | _JDK_ITERATORS | _JDK_OTHER

# Methoden, die ein Element der Collection liefern.
_ELEMENT_METHODS = frozenset({
    "get", "remove", "getFirst", "getLast", "removeFirst", "removeLast", "poll",
    "pollFirst", "pollLast", "peek", "peekFirst", "peekLast", "pop", "element",
    "first", "last", "firstElement", "lastElement", "elementAt", "take",
    "next", "previous", "nextElement", "orElse", "orElseThrow", "orElseGet",
    "ceiling", "floor", "higher", "lower",
})


@dataclass(frozen=True)
class IdeEnvironment:
    """Wie das Projekt in IntelliJ geöffnet war.

    Attributes:
        jdk: Ob ein JDK eingerichtet war. Ohne JDK kennt IntelliJ ``List``,
            ``Set`` usw. nicht und erkennt Collection-Felder nicht als "viele".
        same_package: Ob Klassen aus demselben Paket ohne ``import`` gefunden
            wurden. Bei falsch gesetztem Source-Root ist das nicht der Fall.
            Dann lösen sich nur Klassen derselben Datei und ausdrücklich
            importierte Klassen auf.
    """

    jdk: bool = True
    same_package: bool = True


@dataclass(frozen=True)
class JType:
    """Ein aufgelöster Typ.

    ``kind`` ist ``project`` (``name`` ist dann die Knoten-ID), ``jdk`` (Kurzname
    einer bekannten JDK-Klasse) oder ``external`` (alles andere).
    """

    kind: str
    name: str
    args: tuple["JType | None", ...] = ()
    dims: int = 0

    def element(self) -> "JType | None":
        if self.dims:
            return JType(self.kind, self.name, self.args, self.dims - 1)
        return None


@dataclass
class _Member:
    name: str
    owner: ClassInfo
    type_node: object | None        # Rückgabetyp bzw. Feldtyp
    params: list[object] = field(default_factory=list)
    static: bool = False
    varargs: bool = False
    type_params: tuple[str, ...] = ()
    line: int | None = None


@dataclass
class _ClassBody:
    cls: ClassInfo
    node: object
    file: Path
    fields: dict[str, list[_Member]] = field(default_factory=lambda: defaultdict(list))
    methods: dict[str, list[_Member]] = field(default_factory=lambda: defaultdict(list))
    static_imports: list[str] = field(default_factory=list)


@dataclass
class _Usage:
    kinds: set[str] = field(default_factory=set)      # use | create
    evidence: list[EdgeEvidence] = field(default_factory=list)


class _Model:
    """Symboltabelle über das ganze Projekt plus Typbestimmung für Ausdrücke."""

    def __init__(self, classes: list[ClassInfo], bodies: dict[str, _ClassBody],
                 env: IdeEnvironment):
        self.classes = {c.qualified_name: c for c in classes}
        self.by_source = {c.source_qualified_name: c for c in classes}
        self.bodies = bodies
        self.env = env
        self.resolver = JavaTypeResolver(classes)

    # Sichtbarkeit nach Umgebung

    def visible(self, source: ClassInfo, target: ClassInfo) -> bool:
        if source.file == target.file or self.env.same_package:
            return True
        if target.source_package != source.source_package:
            return True
        top = target.source_qualified_name
        while top and top not in source.imports and "." in top:
            top = top.rsplit(".", 1)[0]
        return top in source.imports

    # Typnamen

    def resolve_name(self, name: str, ctx: ClassInfo,
                     type_params: tuple[str, ...] = ()) -> JType | None:
        first = name.split(".", 1)[0]
        if first in type_params:
            return None
        target_id = self.resolver.resolve(name, ctx)
        if target_id is not None:
            target = self.classes.get(target_id)
            if target is not None and self.visible(ctx, target):
                return JType("project", target_id)
            return JType("external", name)
        if first in ctx.type_parameters:
            return None
        full = self.resolver.external_name(name, ctx)
        short = name.rsplit(".", 1)[-1]
        if self.env.jdk and self._is_jdk(full, short, ctx):
            return JType("jdk", short)
        return JType("external", full)

    def _is_jdk(self, full: str, short: str, ctx: ClassInfo) -> bool:
        if full.startswith("java."):
            return True
        if short in _JDK_LANG:
            return True
        if short in _JDK_KNOWN:
            return any(i in ("java.util.*", "java.util.concurrent.*") for i in ctx.imports) or \
                f"java.util.{short}" in ctx.imports or f"java.util.concurrent.{short}" in ctx.imports
        return False

    def type_of_node(self, node, ctx: ClassInfo,
                     type_params: tuple[str, ...] = ()) -> JType | None:
        if node is None:
            return None
        t = node.type
        if t == "array_type":
            inner = self.type_of_node(node.child_by_field_name("element"), ctx, type_params)
            dims = sum(_text(c).count("[") for c in node.children if c.type == "dimensions") or 1
            if inner is None:
                return None
            return JType(inner.kind, inner.name, inner.args, inner.dims + dims)
        if t == "generic_type":
            base = None
            args: list[JType | None] = []
            for child in node.children:
                if child.type in ("type_identifier", "scoped_type_identifier") and base is None:
                    base = self.type_of_node(child, ctx, type_params)
                elif child.type == "type_arguments":
                    for arg in child.named_children:
                        if arg.type == "wildcard":
                            bound = next((c for c in arg.named_children), None)
                            args.append(self.type_of_node(bound, ctx, type_params))
                        else:
                            args.append(self.type_of_node(arg, ctx, type_params))
            if base is None:
                return None
            return JType(base.kind, base.name, tuple(args), base.dims)
        if t == "type_identifier":
            return self.resolve_name(_text(node), ctx, type_params)
        if t == "scoped_type_identifier":
            return self.resolve_name(_scoped_name(node), ctx, type_params)
        return None

    # Hierarchie

    def supertypes(self, cls: ClassInfo) -> list[ClassInfo]:
        result = []
        for name in cls.bases + cls.interfaces:
            jt = self.resolve_name(name, cls)
            if jt is not None and jt.kind == "project":
                result.append(self.classes[jt.name])
        return result

    def lineage(self, cls: ClassInfo) -> list[ClassInfo]:
        """Die Klasse selbst und alle Obertypen im Projekt, breitenweise."""
        seen: list[ClassInfo] = []
        queue = [cls]
        while queue:
            current = queue.pop(0)
            if any(current is s for s in seen):
                continue
            seen.append(current)
            queue.extend(self.supertypes(current))
        return seen

    def outer(self, cls: ClassInfo) -> ClassInfo | None:
        full = cls.source_qualified_name
        prefix = full.rsplit(".", 1)[0] if "." in full else ""
        return self.by_source.get(prefix)

    def extends_jdk_iterable(self, cls: ClassInfo) -> bool:
        for c in self.lineage(cls):
            for name in c.bases + c.interfaces:
                jt = self.resolve_name(name, c)
                if jt is not None and jt.kind == "jdk" and jt.name in _JDK_ITERABLES:
                    return True
        return False

    # Member-Suche

    def find_method(self, cls: ClassInfo, name: str, argc: int) -> _Member | None:
        for c in self.lineage(cls):
            body = self.bodies.get(c.qualified_name)
            if body is None:
                continue
            candidates = body.methods.get(name, [])
            exact = [m for m in candidates if len(m.params) == argc or (m.varargs and argc >= len(m.params) - 1)]
            if exact:
                return exact[0]
            if candidates:
                return candidates[0]
        return None

    def find_field(self, cls: ClassInfo, name: str) -> _Member | None:
        for c in self.lineage(cls):
            body = self.bodies.get(c.qualified_name)
            if body is not None and body.fields.get(name):
                return body.fields[name][0]
        return None

    def member_type(self, member: _Member, receiver: JType | None) -> JType | None:
        """Typ eines Felds oder Rückgabetyp einer Methode, mit einfacher Ersetzung von Typparametern."""
        node = member.type_node
        if node is None:
            return None
        owner = member.owner
        if node.type in ("type_identifier",) and receiver is not None and receiver.args:
            name = _text(node)
            if name in owner.type_parameters:
                idx = owner.type_parameters.index(name)
                if idx < len(receiver.args):
                    return receiver.args[idx]
        return self.type_of_node(node, owner, member.type_params)

    def jdk_member_type(self, receiver: JType, name: str) -> JType | None:
        """Rückgabetyp der wenigen JDK-Methoden, die für Aufrufketten wichtig sind."""
        if not self.env.jdk or receiver.kind != "jdk":
            return None
        args = receiver.args
        if receiver.name in _JDK_ITERABLES or receiver.name in _JDK_ITERATORS or receiver.name == "Optional":
            elem = args[0] if args else None
            if name in _ELEMENT_METHODS:
                return elem
            if name in ("iterator", "listIterator", "descendingIterator"):
                return JType("jdk", "Iterator", (elem,))
        if receiver.name in _JDK_MAPS:
            key = args[0] if len(args) > 0 else None
            val = args[1] if len(args) > 1 else None
            if name in ("get", "put", "remove", "getOrDefault", "putIfAbsent",
                        "computeIfAbsent", "computeIfPresent", "compute", "merge", "replace"):
                return val
            if name == "values":
                return JType("jdk", "Collection", (val,))
            if name in ("keySet", "navigableKeySet"):
                return JType("jdk", "Set", (key,))
            if name in ("firstKey", "lastKey"):
                return key
        return None

    def iterable_element(self, t: JType | None) -> JType | None:
        if t is None:
            return None
        if t.dims:
            return t.element()
        if t.kind == "jdk" and t.name in _JDK_ITERABLES:
            return t.args[0] if t.args else None
        if t.kind == "project" and self.env.jdk:
            cls = self.classes.get(t.name)
            if cls is not None and self.extends_jdk_iterable(cls) and t.args:
                return t.args[-1]
        return None


def _scoped_name(node) -> str:
    ids: list[str] = []

    def collect(n) -> None:
        for child in n.children:
            if child.type == "type_identifier":
                ids.append(_text(child))
            elif child.type == "scoped_type_identifier":
                collect(child)

    collect(node)
    return ".".join(ids)


def _type_params_of(node) -> tuple[str, ...]:
    tp = node.child_by_field_name("type_parameters")
    if tp is None:
        return ()
    names = []
    for param in tp.named_children:
        ident = next((c for c in param.named_children if c.type in ("type_identifier", "identifier")), None)
        if ident is not None:
            names.append(_text(ident))
    return tuple(names)


# Erster Durchlauf: Member jeder Klasse einsammeln

def _collect_bodies(classes: list[ClassInfo], java_files: list[Path]) -> dict[str, _ClassBody]:
    parser = _get_parser()
    by_source: dict[tuple[str, str], ClassInfo] = {}
    for c in classes:
        by_source[(str(c.file), c.source_qualified_name)] = c
    bodies: dict[str, _ClassBody] = {}

    for path in sorted(java_files):
        try:
            data, _ = read_source(path)
        except OSError:
            continue
        tree = parser.parse(data)
        package = ""
        static_imports: list[str] = []
        for node in tree.root_node.children:
            if node.type == "package_declaration":
                for child in node.children:
                    if child.type in ("scoped_identifier", "identifier"):
                        package = _text(child)
            elif node.type == "import_declaration" and "static" in _text(node).split():
                value = _text(node).removeprefix("import").strip().removeprefix("static").strip()
                static_imports.append(value.rstrip(";").strip())

        stack: list[str] = []

        def visit(node) -> None:
            pushed = False
            if node.type in _DECL_NODES:
                name_node = next((c for c in node.children if c.type == "identifier"), None)
                if name_node is not None:
                    local = ".".join(stack + [_text(name_node)])
                    full = f"{package}.{local}" if package else local
                    cls = by_source.get((str(path), full))
                    if cls is not None:
                        body = _ClassBody(cls=cls, node=node, file=path,
                                          static_imports=static_imports)
                        _collect_members(node, cls, body)
                        bodies[cls.qualified_name] = body
                    stack.append(_text(name_node))
                    pushed = True
            for child in node.children:
                visit(child)
            if pushed:
                stack.pop()

        visit(tree.root_node)
    return bodies


def _collect_members(node, cls: ClassInfo, body: _ClassBody) -> None:
    decl_body = node.child_by_field_name("body")
    params = node.child_by_field_name("parameters")
    if node.type == "record_declaration" and params is not None:
        for p in params.named_children:
            if p.type == "formal_parameter":
                name = p.child_by_field_name("name")
                if name is not None:
                    member = _Member(_text(name), cls, p.child_by_field_name("type"),
                                     line=p.start_point[0] + 1)
                    body.fields[member.name].append(member)
                    body.methods[member.name].append(member)
    if decl_body is None:
        return
    members = list(decl_body.children)
    members = [m for child in members for m in
               (child.children if child.type == "enum_body_declarations" else [child])]
    for member in members:
        if member.type == "enum_constant":
            name = member.child_by_field_name("name")
            if name is not None:
                body.fields[_text(name)].append(_Member(_text(name), cls, None, static=True))
        elif member.type in ("field_declaration", "constant_declaration"):
            mods, _ = _modifiers(member)
            type_node = member.child_by_field_name("type")
            for decl in member.named_children:
                if decl.type != "variable_declarator":
                    continue
                name = decl.child_by_field_name("name")
                if name is None:
                    continue
                dims = next((c for c in decl.children if c.type == "dimensions"), None)
                body.fields[_text(name)].append(_Member(
                    _text(name), cls, type_node, static="static" in mods
                    or cls.kind in {"interface", "annotation"},
                    line=decl.start_point[0] + 1,
                    varargs=dims is not None,   # bei Feldern Merker für `Typ name[]`
                ))
        elif member.type in ("method_declaration", "constructor_declaration"):
            mods, _ = _modifiers(member)
            name = member.child_by_field_name("name")
            if name is None:
                continue
            plist = member.child_by_field_name("parameters")
            ps = []
            varargs = False
            if plist is not None:
                for p in plist.named_children:
                    if p.type in ("formal_parameter", "spread_parameter"):
                        ps.append(p)
                        varargs = varargs or p.type == "spread_parameter"
            is_ctor = member.type == "constructor_declaration"
            entry = _Member(
                "<init>" if is_ctor else _text(name), cls,
                None if is_ctor else member.child_by_field_name("type"),
                params=ps, static="static" in mods, varargs=varargs,
                type_params=_type_params_of(member), line=member.start_point[0] + 1,
            )
            body.methods[entry.name].append(entry)


# Zweiter Durchlauf: Verweise in den Rümpfen

class _BodyScanner:
    """Sammelt alle Verweise einer Klasse und bestimmt dabei die Typen von Ausdrücken."""

    def __init__(self, model: _Model, body: _ClassBody):
        self.model = model
        self.body = body
        self.cls = body.cls
        self.usages: dict[str, _Usage] = defaultdict(_Usage)
        # Lokale Variablen: (Name, Beginn, Ende des Gültigkeitsbereichs, Typ)
        self.locals: list[tuple[str, int, int, JType | None]] = []
        self.type_params: tuple[str, ...] = ()

    def note(self, target: JType | None, kind: str, node, member: str | None = None) -> None:
        if target is None:
            return
        usage = self.usages[_node_key(target)]
        usage.kinds.add(kind)
        if len(usage.evidence) < 5:
            usage.evidence.append(EdgeEvidence(
                kind="create" if kind == "create" else "reference",
                member=member,
                declared_type=_text(node)[:80] if node is not None else None,
                file=self.cls.source_file or str(self.cls.file),
                line=node.start_point[0] + 1 if node is not None else None,
            ))

    # Einstieg

    def scan(self) -> dict[str, _Usage]:
        node = self.body.node
        for child in node.children:
            if child.type in ("superclass", "super_interfaces", "extends_interfaces", "interfaces"):
                self._walk(child)
        params = node.child_by_field_name("parameters")
        if params is not None:
            self._walk(params)
        decl_body = node.child_by_field_name("body")
        if decl_body is not None:
            self._walk(decl_body)
        return self.usages

    def _walk(self, node) -> None:
        t = node.type
        if t in _DECL_NODES and node is not self.body.node:
            return   # verschachtelte Klasse: hat ihren eigenen Durchlauf
        if t in ("method_declaration", "constructor_declaration", "lambda_expression"):
            saved = self.type_params
            if t != "lambda_expression":
                self.type_params = saved + _type_params_of(node)
            self._declare_params(node)
            for child in node.children:
                self._walk(child)
            self.type_params = saved
            return
        if t in ("type_identifier", "scoped_type_identifier"):
            if node.parent is not None and node.parent.type == "scoped_type_identifier":
                return
            self.note(self.model.type_of_node(node, self.cls, self.type_params), "use", node)
            return
        if t == "local_variable_declaration":
            self._declare_locals(node)
        elif t == "enhanced_for_statement":
            self._declare_foreach(node)
        elif t in ("catch_formal_parameter", "resource"):
            self._declare_simple(node)
        elif t == "instanceof_expression":
            self._declare_pattern(node)
        elif t == "method_invocation":
            self._invocation(node)
            return
        elif t == "object_creation_expression":
            self._creation(node)
            return
        elif t == "explicit_constructor_invocation":
            self._explicit_ctor(node)
        elif t == "method_reference":
            self._method_reference(node)
        elif t == "field_access":
            self.type_of(node)
            return
        elif t == "identifier" and node.parent is not None and node.parent.type in (
            "expression_statement", "argument_list", "return_statement", "binary_expression",
            "assignment_expression", "variable_declarator", "array_access", "parenthesized_expression",
            "ternary_expression", "unary_expression", "update_expression",
        ):
            self.type_of(node)
        for child in node.children:
            self._walk(child)

    # Gültigkeitsbereiche

    def _scope_end(self, node) -> int:
        p = node.parent
        while p is not None and p.type not in (
            "block", "method_declaration", "constructor_declaration", "lambda_expression",
            "for_statement", "enhanced_for_statement", "catch_clause", "try_with_resources_statement",
            "switch_block_statement_group", "constructor_body", "class_body",
        ):
            p = p.parent
        return p.end_byte if p is not None else node.end_byte

    def _add_local(self, name_node, jtype: JType | None, scope_node) -> None:
        if name_node is None:
            return
        self.locals.append((_text(name_node), name_node.start_byte, self._scope_end(scope_node), jtype))

    def _declare_params(self, node) -> None:
        plist = node.child_by_field_name("parameters")
        if plist is None:
            if node.type == "lambda_expression":
                params = node.child_by_field_name("parameters")
                if params is not None and params.type == "identifier":
                    self.locals.append((_text(params), params.start_byte, node.end_byte, None))
            return
        if plist.type == "identifier":
            self.locals.append((_text(plist), plist.start_byte, node.end_byte, None))
            return
        for p in plist.named_children:
            if p.type in ("formal_parameter", "spread_parameter"):
                type_node = p.child_by_field_name("type")
                if type_node is None:
                    type_node = next((c for c in p.named_children if c.type in (
                        "type_identifier", "generic_type", "array_type", "scoped_type_identifier")), None)
                jt = self.model.type_of_node(type_node, self.cls, self.type_params)
                if p.type == "spread_parameter" and jt is not None:
                    jt = JType(jt.kind, jt.name, jt.args, jt.dims + 1)
                name = p.child_by_field_name("name")
                if name is None:
                    decl = next((c for c in p.named_children if c.type == "variable_declarator"), None)
                    name = decl.child_by_field_name("name") if decl is not None else None
                if name is not None:
                    self.locals.append((_text(name), name.start_byte, node.end_byte, jt))
            elif p.type == "identifier":
                self.locals.append((_text(p), p.start_byte, node.end_byte, None))

    def _declare_locals(self, node) -> None:
        type_node = node.child_by_field_name("type")
        is_var = type_node is not None and _text(type_node) == "var"
        jt = None if is_var else self.model.type_of_node(type_node, self.cls, self.type_params)
        for decl in node.named_children:
            if decl.type != "variable_declarator":
                continue
            name = decl.child_by_field_name("name")
            value = decl.child_by_field_name("value")
            t = jt
            if is_var and value is not None:
                t = self.type_of(value)
            self._add_local(name, t, node)

    def _declare_foreach(self, node) -> None:
        type_node = node.child_by_field_name("type")
        name = node.child_by_field_name("name")
        value = node.child_by_field_name("value")
        if type_node is not None and _text(type_node) != "var":
            jt = self.model.type_of_node(type_node, self.cls, self.type_params)
        else:
            jt = self.model.iterable_element(self.type_of(value)) if value is not None else None
        if name is not None:
            self.locals.append((_text(name), name.start_byte, node.end_byte, jt))

    def _declare_simple(self, node) -> None:
        type_node = node.child_by_field_name("type")
        if type_node is None:
            type_node = next((c for c in node.named_children if c.type in (
                "catch_type", "type_identifier", "generic_type", "scoped_type_identifier")), None)
            if type_node is not None and type_node.type == "catch_type":
                type_node = next((c for c in type_node.named_children), None)
        name = node.child_by_field_name("name")
        jt = self.model.type_of_node(type_node, self.cls, self.type_params)
        if name is not None:
            self.locals.append((_text(name), name.start_byte, self._scope_end(node), jt))

    def _declare_pattern(self, node) -> None:
        name = node.child_by_field_name("name")
        type_node = node.child_by_field_name("right")
        if name is not None and type_node is not None:
            jt = self.model.type_of_node(type_node, self.cls, self.type_params)
            self.locals.append((_text(name), name.start_byte, self._scope_end(node), jt))

    def _local(self, name: str, pos: int) -> tuple[bool, JType | None]:
        best = None
        for entry in self.locals:
            if entry[0] == name and entry[1] <= pos < entry[2]:
                if best is None or entry[1] > best[1]:
                    best = entry
        if best is None:
            return False, None
        return True, best[3]

    # Ausdrücke

    def _class_ref(self, name: str, node) -> JType | None:
        jt = self.model.resolve_name(name, self.cls, self.type_params)
        if jt is not None and jt.kind == "project":
            return jt
        return None

    def _field_in_scope(self, name: str) -> tuple[_Member | None, ClassInfo | None]:
        current: ClassInfo | None = self.cls
        while current is not None:
            member = self.model.find_field(current, name)
            if member is not None:
                return member, current
            current = self.model.outer(current)
        return None, None

    def type_of(self, node) -> JType | None:
        """Typ eines Ausdrucks bestimmen. Verweise unterwegs werden notiert."""
        if node is None:
            return None
        t = node.type
        if t == "parenthesized_expression":
            inner = next((c for c in node.named_children), None)
            return self.type_of(inner)
        if t == "this":
            return JType("project", self.cls.qualified_name)
        if t == "super":
            sup = self.model.supertypes(self.cls)
            return JType("project", sup[0].qualified_name) if sup else None
        if t == "identifier":
            name = _text(node)
            found, jt = self._local(name, node.start_byte)
            if found:
                return jt
            member, owner = self._field_in_scope(name)
            if member is not None:
                return self.model.member_type(member, None)
            ref = self._class_ref(name, node)
            if ref is not None:
                self.note(ref, "use", node)
                return JType(ref.kind, ref.name, (), 0) if ref else None
            return None
        if t == "field_access":
            obj = node.child_by_field_name("object")
            fname = node.child_by_field_name("field")
            receiver = self.type_of(obj)
            if fname is None:
                return None
            if _text(fname) == "length" and receiver is not None and receiver.dims:
                return None
            if receiver is not None and receiver.kind == "project" and not receiver.dims:
                member = self.model.find_field(self.model.classes[receiver.name], _text(fname))
                if member is not None:
                    return self.model.member_type(member, receiver)
            return None
        if t == "method_invocation":
            return self._invocation(node)
        if t == "object_creation_expression":
            return self._creation(node)
        if t == "cast_expression":
            type_node = node.child_by_field_name("type")
            jt = self.model.type_of_node(type_node, self.cls, self.type_params)
            self.note(jt, "use", type_node)
            value = node.child_by_field_name("value")
            if value is not None:
                self._walk(value)
            return jt
        if t == "array_access":
            arr = self.type_of(node.child_by_field_name("array"))
            index = node.child_by_field_name("index")
            if index is not None:
                self._walk(index)
            return arr.element() if arr is not None else None
        if t == "ternary_expression":
            for part in ("condition",):
                c = node.child_by_field_name(part)
                if c is not None:
                    self._walk(c)
            first = self.type_of(node.child_by_field_name("consequence"))
            second = self.type_of(node.child_by_field_name("alternative"))
            return first or second
        if t == "assignment_expression":
            left = self.type_of(node.child_by_field_name("left"))
            right = node.child_by_field_name("right")
            if right is not None:
                self.type_of(right) if right.type in ("method_invocation", "object_creation_expression",
                                                       "field_access", "cast_expression") else self._walk(right)
            return left
        if t == "array_creation_expression":
            type_node = node.child_by_field_name("type")
            jt = self.model.type_of_node(type_node, self.cls, self.type_params)
            self.note(jt, "use", type_node)
            for child in node.children:
                if child is not type_node:
                    self._walk(child)
            if jt is None:
                return None
            dims = _text(node).count("[")
            return JType(jt.kind, jt.name, jt.args, jt.dims + max(dims, 1))
        if t == "class_literal":
            self._walk(node)
            return None
        self._walk(node)
        return None

    def _invocation(self, node) -> JType | None:
        obj = node.child_by_field_name("object")
        name_node = node.child_by_field_name("name")
        args = node.child_by_field_name("arguments")
        argc = len(args.named_children) if args is not None else 0
        if args is not None:
            for a in args.named_children:
                self.type_of(a) if a.type in ("method_invocation", "object_creation_expression",
                                              "field_access", "cast_expression", "identifier",
                                              "parenthesized_expression", "array_access",
                                              "ternary_expression") else self._walk(a)
        tparams = node.child_by_field_name("type_arguments")
        if tparams is not None:
            self._walk(tparams)
        if name_node is None:
            return None
        name = _text(name_node)

        if obj is None:
            current: ClassInfo | None = self.cls
            while current is not None:
                member = self.model.find_method(current, name, argc)
                if member is not None:
                    self.note(JType("project", member.owner.qualified_name), "use", node, name)
                    return self.model.member_type(member, None)
                current = self.model.outer(current)
            for imp in self.body.static_imports:
                owner_name, _, member_name = imp.rpartition(".")
                if member_name in (name, "*"):
                    owner = self.model.resolve_name(owner_name, self.cls)
                    if owner is not None and owner.kind == "project":
                        member = self.model.find_method(self.model.classes[owner.name], name, argc)
                        if member is not None:
                            self.note(JType("project", member.owner.qualified_name), "use", node, name)
                            return self.model.member_type(member, None)
            return None

        if obj.type == "super":
            sup = self.model.supertypes(self.cls)
            receiver = JType("project", sup[0].qualified_name) if sup else None
        else:
            receiver = self.type_of(obj)
        if receiver is None:
            return None
        if receiver.dims:
            return None
        if receiver.kind == "project":
            cls = self.model.classes.get(receiver.name)
            if cls is None:
                return None
            member = self.model.find_method(cls, name, argc)
            if member is None:
                return None
            self.note(JType("project", member.owner.qualified_name), "use", node, name)
            return self.model.member_type(member, receiver)
        return self.model.jdk_member_type(receiver, name)

    def _creation(self, node) -> JType | None:
        type_node = node.child_by_field_name("type")
        jt = self.model.type_of_node(type_node, self.cls, self.type_params)
        self.note(jt, "create", type_node)
        if type_node is not None:
            for child in type_node.named_children:
                if child.type == "type_arguments":
                    self._walk(child)
        args = node.child_by_field_name("arguments")
        if args is not None:
            for a in args.named_children:
                self.type_of(a)
        body = next((c for c in node.children if c.type == "class_body"), None)
        if body is not None:
            self._walk(body)
        obj = next((c for c in node.children if c.type not in (
            "new", "type_identifier", "generic_type", "scoped_type_identifier", "argument_list",
            "class_body", ".", "type_arguments")), None)
        if obj is not None and obj.is_named:
            self.type_of(obj)
        return jt

    def _explicit_ctor(self, node) -> None:
        ctor = next((c for c in node.children if c.type in ("this", "super")), None)
        if ctor is None:
            return
        if ctor.type == "this":
            self.note(JType("project", self.cls.qualified_name), "use", node, "this")
        else:
            sup = self.model.supertypes(self.cls)
            if sup:
                self.note(JType("project", sup[0].qualified_name), "use", node, "super")

    def _method_reference(self, node) -> None:
        first = next((c for c in node.named_children), None)
        if first is not None and first.type == "identifier":
            ref = self._class_ref(_text(first), first)
            if ref is not None:
                self.note(ref, "use", first)


# Kanten nach IntelliJ

def _field_relation(model: _Model, member: _Member) -> tuple[str | None, str | None]:
    """(Ziel-ID, "1" oder "*") für ein Feld, oder (None, None)."""
    jt = model.type_of_node(member.type_node, member.owner)
    if jt is None:
        return None, None
    if member.varargs:   # `Typ name[]`
        jt = JType(jt.kind, jt.name, jt.args, jt.dims + 1)
    if jt.dims:
        base = JType(jt.kind, jt.name, jt.args, 0)
        return (_node_key(base), "*") if base.kind != "jdk" else (None, None)
    many = model.iterable_element(jt)
    if many is not None and many.dims == 0:
        return _node_key(many), "*"
    if jt.kind == "jdk":
        return None, None
    return _node_key(jt), "1"


def _node_key(jt: JType) -> str:
    # Externe Klassen über den Kurznamen: Bei einem Stern-Import ist der volle
    # Name aus dem Quelltext allein nicht bestimmbar.
    if jt.kind == "project":
        return jt.name
    return f"{EXTERNAL_PACKAGE}.{jt.name.rsplit('.', 1)[-1]}"


def build_intellij_graph(
    java_files: list[Path],
    root: Path,
    repo: str,
    env: IdeEnvironment | None = None,
    diagram: list[str] | None = None,
) -> AbstractGraph:
    """Klassendiagramm so erzeugen, wie IntelliJ es für dieselben Klassen zeichnet.

    Args:
        java_files: Alle Java-Dateien des Projekts. Auch Klassen außerhalb des
            Diagramms werden gebraucht, um Aufrufketten aufzulösen.
        root: Wurzel des Projekts.
        repo: Name für den Graphen.
        env: Wie das Projekt in IntelliJ geöffnet war.
        diagram: Voll qualifizierte Namen der Klassen im Diagramm (z. B.
            ``raisemeup.model.beans.Pet`` oder ``javax.swing.Icon``). ``None``
            heißt: alle Klassen des Projekts.

    Returns:
        Den Graphen mit den Kantenarten ``inheritance``, ``realization``,
        ``composition`` (Feld, Kardinalität am Ziel "1" oder "*"),
        ``dependency`` (Bezeichnung ``«create»`` bei ``new``) und ``nesting``
        (von der äußeren zur inneren Klasse).
    """
    env = env or IdeEnvironment()
    analysis = analyze_java(java_files, root, "full")
    classes = analysis.classes
    bodies = _collect_bodies(classes, java_files)
    model = _Model(classes, bodies, env)

    # Knoten: Projektklassen mit ihrer normalen ID, externe als "external.<Kurzname>"
    selected: dict[str, str] = {}          # Knoten-ID -> Anzeigename
    if diagram is None:
        for c in classes:
            selected[c.qualified_name] = c.name
    else:
        missing = []
        for full in diagram:
            cls = model.by_source.get(full)
            if cls is not None:
                selected[cls.qualified_name] = cls.name
            else:
                selected[f"{EXTERNAL_PACKAGE}.{full.rsplit('.', 1)[-1]}"] = full.rsplit(".", 1)[-1]
                if not full.startswith(("java.", "javax.")):
                    missing.append(full)
        if missing:
            logger.warning("Diagram classes not found in sources (treated as external): %s",
                           ", ".join(missing))

    edges: list[Edge] = []
    structural: set[tuple[str, str]] = set()

    def add(edge: Edge) -> None:
        edges.append(edge)

    # Vererbung und Realisierung. Steht ein Obertyp nicht im Diagramm, geht
    # IntelliJ weiter nach oben bis zum nächsten Obertyp, der drinsteht. In Orekit
    # implementiert `AdaptedStepInterpolator` das nicht gezeigte
    # `OrekitStepInterpolator`, und IntelliJ zeichnet die Realisierung direkt zu
    # dessen Obertyp `PVCoordinatesProvider`.
    def is_interface(key: str) -> bool | None:
        target = model.classes.get(key)
        return None if target is None else target.kind in {"interface", "annotation"}

    for cls in classes:
        if cls.qualified_name not in selected:
            continue
        source_is_interface = cls.kind in {"interface", "annotation"}
        found: list[tuple[str, str, str]] = []      # (Ziel, Art, geschriebener Name)
        visited: set[str] = {cls.qualified_name}
        queue: list[tuple[ClassInfo, str, str, bool]] = []
        for name in cls.bases:
            queue.append((cls, name, name, False))
        for name in cls.interfaces:
            queue.append((cls, name, name, True))
        while queue:
            owner, name, written, via_implements = queue.pop(0)
            jt = model.resolve_name(name, owner)
            if jt is None:
                continue
            key = _node_key(jt)
            if key in visited:
                continue
            visited.add(key)
            if key in selected:
                target_iface = is_interface(key)
                if target_iface is None:
                    type_ = "realization" if via_implements and not source_is_interface else "inheritance"
                elif target_iface and not source_is_interface:
                    type_ = "realization"
                else:
                    type_ = "inheritance"
                found.append((key, type_, written))
                continue
            parent = model.classes.get(key) if jt.kind == "project" else None
            if parent is not None:
                for base in parent.bases:
                    queue.append((parent, base, written, via_implements))
                for iface in parent.interfaces:
                    queue.append((parent, iface, written, True))
        for key, type_, written in found:
            structural.add((cls.qualified_name, key))
            add(Edge(source=cls.qualified_name, target=key, type=type_,
                     evidence=[EdgeEvidence(kind="extends" if type_ == "inheritance" else "implements",
                                            declared_type=written, file=cls.source_file,
                                            line=cls.line_start)]))

    # Felder
    for cls in classes:
        if cls.qualified_name not in selected:
            continue
        body = bodies.get(cls.qualified_name)
        if body is None:
            continue
        for fname, members in body.fields.items():
            for member in members:
                if member.type_node is None:
                    continue
                target, card = _field_relation(model, member)
                if target is None or target not in selected:
                    continue
                structural.add((cls.qualified_name, target))
                add(Edge(source=cls.qualified_name, target=target, type="composition",
                         source_card="1", target_card=card, label=fname,
                         evidence=[EdgeEvidence(kind="field", member=fname,
                                                declared_type=_text(member.type_node),
                                                file=cls.source_file, line=member.line)]))

    # Verschachtelung
    nested_pairs: set[tuple[str, str]] = set()
    for cls in classes:
        if cls.qualified_name not in selected:
            continue
        outer = model.outer(cls)
        if outer is not None and outer.qualified_name in selected:
            nested_pairs.add((cls.qualified_name, outer.qualified_name))
            add(Edge(source=outer.qualified_name, target=cls.qualified_name, type="nesting",
                     evidence=[EdgeEvidence(kind="nested", file=cls.source_file, line=cls.line_start)]))

    # Abhängigkeiten
    for cls in classes:
        if cls.qualified_name not in selected:
            continue
        body = bodies.get(cls.qualified_name)
        if body is None:
            continue
        usages = _BodyScanner(model, body).scan()
        for target, usage in sorted(usages.items()):
            if target not in selected:
                continue
            create = "create" in usage.kinds
            pair = (cls.qualified_name, target)
            if not create:
                if pair in structural or pair in nested_pairs:
                    continue
            add(Edge(source=cls.qualified_name, target=target, type="dependency",
                     label="«create»" if create else None, evidence=usage.evidence))

    by_id = {c.qualified_name: c for c in classes}
    nodes: list[Node] = []
    modules: set[str] = set()
    for node_id, name in selected.items():
        cls = by_id.get(node_id)
        if cls is None:
            nodes.append(Node(id=node_id, name=name, package=EXTERNAL_PACKAGE))
            modules.add(EXTERNAL_PACKAGE)
            continue
        modules.add(cls.module)
        nodes.append(Node(
            id=cls.qualified_name, name=cls.name, package=cls.module,
            stereotype=_STEREOTYPE_MAP.get(cls.kind or ""),
            attributes=list(cls.attributes), methods=list(cls.methods),
            source_file=cls.source_file or str(cls.file), source_line=cls.line_start,
        ))

    return AbstractGraph(
        repo=repo, target_nodes=None, packages=_packages(modules),
        nodes=nodes, edges=edges, diagnostics=list(analysis.diagnostics),
    )
