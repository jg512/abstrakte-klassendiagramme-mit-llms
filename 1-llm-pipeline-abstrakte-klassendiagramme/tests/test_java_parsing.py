from __future__ import annotations

import pytest
import shutil

from src.config.models import FiltersConfig, JavaConfig, SizeCapsConfig
from src.io.filters import collect_source_files
from src.io.preflight import PreflightError, run_preflight
from src.parsing.languages import (
    UnknownLanguageError,
    resolve_language,
)
from src.schema.validator import validate

pytest.importorskip("tree_sitter_java", reason="Java support is an optional extra")

from src.parsing.code_graph import build_code_graph  # noqa: E402
from src.parsing.java import build_java_graph, run_java_pass  # noqa: E402
from src.parsing.java.graph_builder import EXTERNAL_PACKAGE  # noqa: E402
from src.parsing.java.import_graph import build_import_graphs  # noqa: E402
from src.parsing.java.ts_pass import read_source  # noqa: E402

PKG = "com.example.app"


def write(root, rel_path: str, body: str, encoding: str = "utf-8"):
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body.encode(encoding))
    return path


@pytest.fixture
def sample(tmp_path):
    """Ein kleines Repo im MVC-Stil, das die wichtigen Beziehungen abdeckt."""
    write(tmp_path, "src/com/example/app/model/User.java", f"""
package {PKG}.model;
public class User {{
    private String name;
    public String getName() {{ return name; }}
}}
""")
    write(tmp_path, "src/com/example/app/model/Session.java", f"""
package {PKG}.model;
public class Session {{
    private User[] users;
    private String key;
}}
""")
    write(tmp_path, "src/com/example/app/model/Registry.java", f"""
package {PKG}.model;
import java.util.List;
import javax.swing.ListModel;
public class Registry implements ListModel<Session> {{
    private List<Session> sessions;
    private java.util.Timer timer;
}}
""")
    write(tmp_path, "src/com/example/app/view/MainFrame.java", f"""
package {PKG}.view;
import javax.swing.JFrame;
import {PKG}.model.Registry;
public class MainFrame extends JFrame {{
    private Registry registry;
    private class Renderer extends JLabel {{ }}
}}
""")
    return tmp_path


def parse(root):
    files = collect_source_files(root, FiltersConfig((), ()), "java")
    return run_java_pass(files, root)[0]


# Extraktion

class TestExtraction:
    def test_finds_every_declared_type(self, sample):
        names = {c.name for c in parse(sample)}
        assert names == {"User", "Session", "Registry", "MainFrame", "Renderer"}

    def test_strips_common_package_prefix(self, sample):
        modules = {c.module for c in parse(sample)}
        # com.example.app haben alle Pakete gemeinsam, es trägt keine Information.
        assert modules == {"model", "view"}

    def test_qualified_name_is_repo_relative(self, sample):
        by_name = {c.name: c for c in parse(sample)}
        assert by_name["User"].qualified_name == "model.User"

    def test_nested_class_keeps_outer_in_id_but_not_in_module(self, sample):
        renderer = next(c for c in parse(sample) if c.name == "Renderer")
        assert renderer.qualified_name == "view.MainFrame.Renderer"
        assert renderer.module == "view"

    def test_extends_and_implements_are_separate(self, sample):
        by_name = {c.name: c for c in parse(sample)}
        assert by_name["MainFrame"].bases == ["JFrame"]
        assert by_name["MainFrame"].interfaces == []
        assert by_name["Registry"].bases == []
        assert by_name["Registry"].interfaces == ["ListModel"]

    def test_collection_field_refs_the_element_not_the_container(self, sample):
        registry = next(c for c in parse(sample) if c.name == "Registry")
        refs = {r.type_name: r.many for r in registry.field_refs}
        assert refs["Session"] is True
        assert "List" not in refs

    def test_qualified_container_is_still_a_container(self, tmp_path):
        """`java.util.List<X>` muss eine Aggregation von X bleiben, keine Verbindung zu List."""
        write(tmp_path, "X.java", "public class X {}")
        write(tmp_path, "Holder.java",
              "public class Holder { private java.util.List<X> items; }")
        holder = next(c for c in parse(tmp_path) if c.name == "Holder")
        refs = {r.type_name: r.many for r in holder.field_refs}
        assert refs["X"] is True
        assert "java.util.List" not in refs
        assert holder.attributes == ["items: List<X>"]

    def test_array_field_is_many(self, sample):
        session = next(c for c in parse(sample) if c.name == "Session")
        refs = {r.type_name: r.many for r in session.field_refs}
        assert refs["User"] is True
        assert refs["String"] is False

    def test_private_fields_are_kept(self, sample):
        """In Java bilden privates Feld und öffentlicher Getter zusammen die Assoziation."""
        user = next(c for c in parse(sample) if c.name == "User")
        assert any(r.type_name == "String" for r in user.field_refs)

    def test_serial_version_uid_is_dropped(self, tmp_path):
        write(tmp_path, "A.java",
              "public class A { private static final long serialVersionUID = 1L; }")
        cls = parse(tmp_path)[0]
        assert cls.attributes == []


class TestKinds:
    @pytest.mark.parametrize("decl,expected", [
        ("public interface Thing {}", "interface"),
        ("public enum Thing { A, B }", "enum"),
        ("public abstract class Thing {}", "abstract"),
        ("public record Thing(int x) {}", "record"),
        ("public class Thing {}", None),
    ])
    def test_kind_detection(self, tmp_path, decl, expected):
        write(tmp_path, "Thing.java", decl)
        assert parse(tmp_path)[0].kind == expected

    def test_record_components_become_fields(self, tmp_path):
        write(tmp_path, "Circle.java", "public record Circle(double radius, Point centre) {}")
        write(tmp_path, "Point.java", "public class Point {}")
        circle = next(c for c in parse(tmp_path) if c.name == "Circle")
        assert "radius: double" in circle.attributes
        assert any(r.type_name == "Point" for r in circle.field_refs)


class TestRobustness:
    def test_latin1_source_is_parsed(self, tmp_path):
        """Alter Java-Code ist häufig in ISO-8859-1 kodiert. Wer UTF-8 annimmt, verliert ganze Dateien."""
        write(tmp_path, "Beitrag.java",
              "public class Beitrag { private String einträge; }", encoding="latin-1")
        cls = parse(tmp_path)[0]
        assert cls.name == "Beitrag"
        assert any("einträge" in a for a in cls.attributes)

    def test_read_source_reports_utf8_for_ascii(self, tmp_path):
        p = write(tmp_path, "A.java", "public class A {}")
        data, enc = read_source(p)
        assert enc == "utf-8"
        assert b"class A" in data

    def test_modern_java_parses(self, tmp_path):
        """Hier steigt javalang aus. Die Grammatik muss auch Syntax nach Java 8 verstehen."""
        write(tmp_path, "Shape.java", """
package demo;
public sealed interface Shape permits Circle {}
record Circle(double radius) implements Shape {}
public class Modern {
    public String describe(Shape s) {
        return switch (s) {
            case Circle c -> \"\"\"
                circle\"\"\";
        };
    }
}
""")
        names = {c.name for c in parse(tmp_path)}
        assert {"Shape", "Circle", "Modern"} <= names

    def test_syntax_error_does_not_abort_the_repo(self, tmp_path):
        write(tmp_path, "Good.java", "public class Good {}")
        write(tmp_path, "Broken.java", "public class Broken { this is not java (((")
        assert "Good" in {c.name for c in parse(tmp_path)}


# Statischer Klassengraph

class TestGraphBuilder:
    def test_internal_relations_are_typed(self, sample):
        g = build_java_graph(parse(sample), "sample")
        edges = {(e.source, e.target): e for e in g.edges}
        assert edges[("model.Session", "model.User")].type == "aggregation"
        assert edges[("model.Registry", "model.Session")].type == "aggregation"
        assert edges[("view.MainFrame", "model.Registry")].type == "association"

    def test_aggregation_carries_cardinality(self, sample):
        g = build_java_graph(parse(sample), "sample")
        edge = next(e for e in g.edges
                    if (e.source, e.target) == ("model.Registry", "model.Session"))
        assert edge.target_card == "0..*"

    def test_edges_retain_field_evidence(self, sample):
        g = build_java_graph(parse(sample), "sample")
        edge = next(e for e in g.edges if e.label == "sessions")
        assert edge.evidence[0].kind == "field"
        assert edge.evidence[0].declared_type == "List<Session>"
        assert edge.evidence[0].file.endswith("Registry.java")
        assert edge.evidence[0].line

    def test_optional_and_owned_final_fields_have_richer_semantics(self, tmp_path):
        write(tmp_path, "Part.java", "public class Part {}")
        write(tmp_path, "Whole.java", """
import java.util.Optional;
public class Whole {
    private final Part owned = new Part();
    private Optional<Part> maybe;
}
""")
        g = build_java_graph(parse(tmp_path), "r")
        by_label = {e.label: e for e in g.edges}
        assert (by_label["owned"].type, by_label["owned"].target_card) == ("composition", "1")
        assert (by_label["maybe"].type, by_label["maybe"].target_card) == ("association", "0..1")

    def test_distinct_field_roles_to_same_type_remain_distinct(self, tmp_path):
        write(tmp_path, "Part.java", "public class Part {}")
        write(tmp_path, "Whole.java", """
import java.util.List;
public class Whole { private Part primary; private List<Part> history; }
""")
        g = build_java_graph(parse(tmp_path), "r")
        roles = {(e.label, e.type, e.target_card) for e in g.edges}
        assert roles == {
            ("primary", "association", None),
            ("history", "aggregation", "0..*"),
        }

    def test_method_dependencies_are_optional(self, tmp_path):
        write(tmp_path, "A.java", "public class A { public B convert(B value) { return value; } }")
        write(tmp_path, "B.java", "public class B {}")
        classes = run_java_pass(sorted(tmp_path.rglob("*.java")), tmp_path)[0]
        assert not any(e.type == "dependency" for e in build_java_graph(classes, "r").edges)
        g = build_java_graph(classes, "r", include_method_dependencies=True)
        edge = next(e for e in g.edges if e.type == "dependency")
        assert edge.label == "convert"
        assert edge.evidence[0].kind == "method"

    def test_full_member_profile_keeps_complete_signatures(self, tmp_path):
        write(tmp_path, "A.java", """
public class A {
    private final String value = "x";
    private A() {}
    public static B convert(A input) throws IllegalStateException { return null; }
}
class B {}
""")
        classes, _ = run_java_pass(sorted(tmp_path.rglob("*.java")), tmp_path, "full")
        a = next(c for c in classes if c.name == "A")
        assert "- value: String {final}" in a.attributes
        assert "- A()" in a.methods
        assert "+ convert(input: A): B throws IllegalStateException {static}" in a.methods

    def test_structure_profile_omits_members_but_keeps_relations(self, tmp_path):
        write(tmp_path, "A.java", "public class A { private B value; public B get() { return value; } }")
        write(tmp_path, "B.java", "public class B {}")
        classes, _ = run_java_pass(sorted(tmp_path.rglob("*.java")), tmp_path, "structure")
        a = next(c for c in classes if c.name == "A")
        assert a.attributes == [] and a.methods == []
        assert a.field_refs and a.method_refs

    def test_public_api_includes_implicit_interface_members(self, tmp_path):
        write(tmp_path, "Service.java", """
public interface Service {
    String NAME = "service";
    Result execute(Input input);
    private void helper() {}
}
class Input {}
class Result {}
""")
        classes, _ = run_java_pass(
            sorted(tmp_path.rglob("*.java")), tmp_path, "public-api"
        )
        service = next(c for c in classes if c.name == "Service")
        assert any("NAME: String" in value for value in service.attributes)
        assert any(
            value.startswith("+ execute(input: Input): Result")
            for value in service.methods
        )
        assert not any("helper" in value for value in service.methods)

    def test_cross_module_duplicate_fqns_remain_distinct(self, tmp_path):
        for module in ("one", "two"):
            write(tmp_path, f"{module}/src/main/java/p/A.java", "package p; public class A { B b; }")
            write(tmp_path, f"{module}/src/main/java/p/B.java", "package p; public class B {}")
        files = collect_source_files(
            tmp_path, FiltersConfig((), ()), "java", JavaConfig(source_sets="auto")
        )
        cg = build_code_graph(tmp_path, files, language="java", java_options=JavaConfig())
        ids = {n.id for n in cg.static_graph.nodes}
        assert {"modules.one.A", "modules.one.B", "modules.two.A", "modules.two.B"} == ids
        pairs = {(e.source, e.target) for e in cg.static_graph.edges}
        assert ("modules.one.A", "modules.one.B") in pairs
        assert ("modules.two.A", "modules.two.B") in pairs
        assert any(d.code == "cross-module-declaration" for d in cg.static_graph.diagnostics)
        assert any(d.code == "cross-module-declaration" for d in cg.diagnostics)

    @pytest.mark.skipif(not shutil.which("javac"), reason="JDK compiler unavailable")
    def test_optional_javac_solver_adds_provenance_and_partial_diagnostic(self, tmp_path):
        write(tmp_path, "p/A.java", "package p; public class A { B b; Missing unresolved; }")
        write(tmp_path, "p/B.java", "package p; public class B {}")
        files = sorted(tmp_path.rglob("*.java"))
        cg = build_code_graph(
            tmp_path, files, language="java",
            java_options=JavaConfig(symbol_solver="javac"),
        )
        edge = next(e for e in cg.static_graph.edges if e.source == "A" and e.target == "B")
        assert {item.resolver for item in edge.evidence} == {"source", "javac"}
        assert any(d.code == "javac-partial-resolution" for d in cg.static_graph.diagnostics)

    def test_interface_extending_interface_is_generalization(self, tmp_path):
        """`interface A extends B` ist Generalisierung, keine Realisierung.

        Realisierung heißt, ein Klassifizierer implementiert ein Interface. Der
        Grammatikknoten für diese Klausel heißt `extends_interfaces`. Das liest sich
        wie `implements`, und man landet leicht beim falschen Kantentyp.
        """
        write(tmp_path, "p/Base.java", "package r.p; public interface Base {}")
        write(tmp_path, "p/Derived.java", "package r.p; public interface Derived extends Base {}")
        write(tmp_path, "p/Impl.java", "package r.p; public class Impl implements Derived {}")
        g = build_java_graph(parse(tmp_path), "r")
        pairs = {(e.source, e.target): e.type for e in g.edges}
        assert pairs[("Derived", "Base")] == "inheritance"
        assert pairs[("Impl", "Derived")] == "realization"

    def test_interface_extending_several_interfaces(self, tmp_path):
        write(tmp_path, "p/A.java", "package r.p; public interface A {}")
        write(tmp_path, "p/B.java", "package r.p; public interface B {}")
        write(tmp_path, "p/C.java", "package r.p; public interface C extends A, B {}")
        g = build_java_graph(parse(tmp_path), "r")
        types = {(e.source, e.target): e.type for e in g.edges}
        assert types[("C", "A")] == "inheritance"
        assert types[("C", "B")] == "inheritance"

    def test_enum_and_record_implementing_an_interface_is_realization(self, tmp_path):
        """Nur `interface ... extends` ändert sich; Enums und Records realisieren weiterhin."""
        write(tmp_path, "p/Marker.java", "package r.p; public interface Marker {}")
        write(tmp_path, "p/Kind.java", "package r.p; public enum Kind implements Marker { A, B }")
        write(tmp_path, "p/Point.java", "package r.p; public record Point(int x) implements Marker {}")
        g = build_java_graph(parse(tmp_path), "r")
        types = {(e.source, e.target): e.type for e in g.edges}
        assert types[("Kind", "Marker")] == "realization"
        assert types[("Point", "Marker")] == "realization"

    def test_external_supertypes_are_kept(self, sample):
        """Dieser Fehler macht plantuml-generator für Swing- und Spring-Code unbrauchbar."""
        g = build_java_graph(parse(sample), "sample")
        pairs = {(e.source, e.target, e.type) for e in g.edges}
        assert ("view.MainFrame", f"{EXTERNAL_PACKAGE}.javax.swing.JFrame", "inheritance") in pairs
        assert ("model.Registry", f"{EXTERNAL_PACKAGE}.javax.swing.ListModel", "realization") in pairs

    def test_external_associations_are_dropped(self, sample):
        """Ein Feld vom Typ Timer oder String ist Infrastruktur, keine Architektur."""
        g = build_java_graph(parse(sample), "sample")
        targets = {e.target for e in g.edges}
        assert f"{EXTERNAL_PACKAGE}.Timer" not in targets
        assert f"{EXTERNAL_PACKAGE}.String" not in targets

    def test_external_supertypes_can_be_disabled(self, sample):
        g = build_java_graph(parse(sample), "sample", include_external_supertypes=False)
        assert not any(n.package == EXTERNAL_PACKAGE for n in g.nodes)

    def test_graph_survives_validation_unchanged(self, sample):
        """Stereotypen und Kantentypen müssen schon zum Schema passen."""
        g = build_java_graph(parse(sample), "sample")
        validated, warnings = validate(g)
        assert warnings == []
        assert len(validated.nodes) == len(g.nodes)
        assert len(validated.edges) == len(g.edges)

    def test_record_maps_to_dataclass_stereotype(self, tmp_path):
        write(tmp_path, "Circle.java", "public record Circle(double r) {}")
        g = build_java_graph(parse(tmp_path), "r")
        assert g.nodes[0].stereotype == "dataclass"   # ein Stereotyp, den das Schema erlaubt
        assert validate(g)[1] == []

    def test_ambiguous_name_prefers_same_package(self, tmp_path):
        write(tmp_path, "a/Item.java", "package r.a; public class Item {}")
        write(tmp_path, "b/Item.java", "package r.b; public class Item {}")
        write(tmp_path, "a/Box.java", "package r.a; public class Box { private Item item; }")
        g = build_java_graph(parse(tmp_path), "r")
        edge = next(e for e in g.edges if e.source == "a.Box")
        assert edge.target == "a.Item"

    def test_qualified_external_type_does_not_hit_a_same_named_class(self, tmp_path):
        """`java.util.Comparator` darf sich nicht auf einen `Comparator` aus dem Projekt auflösen.

        Ohne Qualifizierung sind beide Namen gleich, die Klasse löst sich auf sich
        selbst auf, und die Beziehung verschwindet als Kante auf sich selbst.
        """
        write(tmp_path, "io/Comparator.java", """
package r.io;
public abstract class Comparator<T> implements java.util.Comparator<T> {}
""")
        write(tmp_path, "io/ByName.java",
              "package r.io; public class ByName extends Comparator<String> {}")
        g = build_java_graph(parse(tmp_path), "r")
        pairs = {(e.source, e.target, e.type) for e in g.edges}
        assert ("Comparator", f"{EXTERNAL_PACKAGE}.java.util.Comparator", "realization") in pairs
        # die unqualifizierte Referenz löst sich weiterhin auf die Projektklasse auf
        assert ("ByName", "Comparator", "inheritance") in pairs
        assert not any(e.source == e.target for e in g.edges)

    def test_external_node_is_labelled_with_the_simple_name(self, tmp_path):
        write(tmp_path, "A.java",
              "public class A implements java.util.Comparator<String> {}")
        g = build_java_graph(parse(tmp_path), "r")
        node = next(n for n in g.nodes if n.package == EXTERNAL_PACKAGE)
        assert node.id == f"{EXTERNAL_PACKAGE}.java.util.Comparator"
        assert node.name == "Comparator"

    def test_qualified_nested_reference_picks_that_outer_class(self, tmp_path):
        write(tmp_path, "p/Alpha.java", "package r.p; public class Alpha { public class Row {} }")
        write(tmp_path, "p/Beta.java", """
package r.p;
import java.util.List;
public class Beta {
    public class Row {}
    private List<Alpha.Row> foreign;
}
""")
        g = build_java_graph(parse(tmp_path), "r")
        edge = next(e for e in g.edges if e.source == "Beta" and e.type == "aggregation")
        assert edge.target == "Alpha.Row"

    def test_recursive_field_keeps_self_association(self, tmp_path):
        write(tmp_path, "Node.java", "public class Node { private Node next; }")
        g = build_java_graph(parse(tmp_path), "r")
        assert [(e.source, e.target, e.type) for e in g.edges] == [("Node", "Node", "association")]

    def test_nested_type_resolves_to_its_own_outer_class(self, tmp_path):
        """Java-Scopes: In Beta heißt ein nacktes `Row` Beta.Row, nicht Alpha.Row.

        Verschachtelte Klassen haben ihr *Paket* als Modul, ein Vergleich über das
        Paket kann sie also nicht trennen. Ohne eigenen Schritt für den Scope fällt
        jedes `Row` im Repo auf das, das zuerst geparst wurde.
        """
        write(tmp_path, "p/Alpha.java", """
package r.p;
import java.util.List;
public class Alpha { private List<Row> rows; public class Row {} }
""")
        write(tmp_path, "p/Beta.java", """
package r.p;
import java.util.List;
public class Beta { private List<Row> rows; public class Row {} }
""")
        # Alle Klassen liegen im Paket r.p. Das gemeinsame Präfix wird deshalb
        # abgeschnitten, und die IDs sind nackt: Alpha, Alpha.Row, Beta, Beta.Row
        g = build_java_graph(parse(tmp_path), "r")
        targets = {e.source: e.target for e in g.edges if e.type == "aggregation"}
        assert targets["Alpha"] == "Alpha.Row"
        assert targets["Beta"] == "Beta.Row"

    def test_nested_type_resolves_from_a_sibling_nested_class(self, tmp_path):
        """Eine verschachtelte Klasse sieht die anderen verschachtelten Typen ihrer umschließenden Klasse."""
        write(tmp_path, "p/Alpha.java", "package r.p; public class Alpha { public class Row {} }")
        write(tmp_path, "p/Beta.java", """
package r.p;
public class Beta {
    public class Row {}
    public class Header extends Row {}
}
""")
        g = build_java_graph(parse(tmp_path), "r")
        edge = next(e for e in g.edges if e.source == "Beta.Header")
        assert edge.target == "Beta.Row"
        assert edge.type == "inheritance"


class TestImportGraph:
    def test_edges_come_from_resolved_references(self, sample):
        module_imports, _ = build_import_graphs(parse(sample))
        assert "model" in module_imports["view"]

    def test_same_package_use_is_not_an_edge(self, sample):
        module_imports, _ = build_import_graphs(parse(sample))
        assert "model" not in module_imports["model"]

    def test_external_types_are_not_edges(self, sample):
        module_imports, _ = build_import_graphs(parse(sample))
        assert all("swing" not in t for targets in module_imports.values() for t in targets)


# Einbindung in die Pipeline

class TestLanguageSelection:
    def test_resolve_is_case_insensitive(self):
        assert resolve_language("JAVA").name == "java"

    def test_default_is_python(self):
        assert resolve_language(None).name == "python"

    def test_unknown_language_raises(self):
        with pytest.raises(UnknownLanguageError):
            resolve_language("cobol")

    def test_collect_picks_only_matching_extension(self, tmp_path):
        write(tmp_path, "A.java", "public class A {}")
        write(tmp_path, "b.py", "class B: pass")
        java = collect_source_files(tmp_path, FiltersConfig((), ()), "java")
        python = collect_source_files(tmp_path, FiltersConfig((), ()), "python")
        assert [p.name for p in java] == ["A.java"]
        assert [p.name for p in python] == ["b.py"]

    def test_build_code_graph_dispatches_on_language(self, sample):
        files = collect_source_files(sample, FiltersConfig((), ()), "java")
        cg = build_code_graph(sample, files, repo="sample", language="java")
        assert cg.language == "java"
        assert cg.static_graph is not None
        # Java hat keine Funktionen auf Modulebene.
        assert cg.functions == []
        # Alias aus Kompatibilitätsgründen, den das Variantenraster benutzt.
        assert cg.pyreverse_graph is cg.static_graph


class TestPreflight:
    def test_counts_java_types(self, sample):
        files = collect_source_files(sample, FiltersConfig((), ()), "java")
        result = run_preflight(sample, files, SizeCapsConfig(10_000, 100), "java")
        assert result.class_count == 5
        assert result.loc > 0

    def test_empty_repo_names_the_language(self, tmp_path):
        with pytest.raises(PreflightError, match="Java"):
            run_preflight(tmp_path, [], SizeCapsConfig(10_000, 100), "java")

    def test_cap_is_enforced(self, sample):
        files = collect_source_files(sample, FiltersConfig((), ()), "java")
        with pytest.raises(PreflightError, match="max_classes"):
            run_preflight(sample, files, SizeCapsConfig(10_000, 2), "java")


class TestCacheKey:
    def test_language_is_part_of_the_key(self, tmp_path):
        """Dasselbe Verzeichnis, als zwei Sprachen geparst, darf keinen gemeinsamen Cache-Eintrag haben."""
        from src.parsing.cache import manifest_hash
        f = write(tmp_path, "A.java", "public class A {}")
        assert manifest_hash([f], "java") != manifest_hash([f], "python")
