import pytest

pytest.importorskip("tree_sitter_java")

from src.parsing.code_graph import build_code_graph


def graph(tmp_path, sources):
    for filename, text in sources.items():
        path = tmp_path / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return build_code_graph(tmp_path, sorted(tmp_path.rglob("*.java")), language="java")


def pairs(cg):
    return {(e.source, e.target, e.type) for e in cg.static_graph.edges}


def test_fully_qualified_internal_type_survives_package_stripping(tmp_path):
    cg = graph(tmp_path, {
        "a/Item.java": "package company.app.a; public class Item {}",
        "b/Box.java": "package company.app.b; public class Box { company.app.a.Item item; }",
    })
    assert ("b.Box", "a.Item", "association") in pairs(cg)
    assert cg.module_imports["b"] == ["a"]


def test_explicit_import_wins_over_unrelated_same_name(tmp_path):
    cg = graph(tmp_path, {
        "a/Item.java": "package company.a; public class Item {}",
        "b/Item.java": "package company.b; public class Item {}",
        "c/Box.java": "package company.c; import company.b.Item; public class Box { Item item; }",
    })
    assert ("c.Box", "b.Item", "association") in pairs(cg)
    assert ("c.Box", "a.Item", "association") not in pairs(cg)
    assert cg.module_imports["c"] == ["b"]


def test_external_import_does_not_bind_to_project_class(tmp_path):
    cg = graph(tmp_path, {
        "a/Timer.java": "package company.a; public class Timer {}",
        "b/Box.java": "package company.b; import java.util.Timer; public class Box extends Timer { Timer timer; }",
    })
    assert not any(t == "a.Timer" for _, t, _ in pairs(cg))
    assert ("b.Box", "external.java.util.Timer", "inheritance") in pairs(cg)
    assert cg.module_imports["b"] == []
    assert cg.inheritance["b.Box"] == []


def test_wildcard_import_and_inheritance_use_same_resolution(tmp_path):
    cg = graph(tmp_path, {
        "a/Base.java": "package company.a; public class Base {}",
        "b/Base.java": "package company.b; public class Base {}",
        "c/Box.java": "package company.c; import company.b.*; public class Box extends Base {}",
    })
    assert ("c.Box", "b.Base", "inheritance") in pairs(cg)
    assert cg.inheritance["c.Box"] == ["b.Base"]
    assert cg.module_imports["c"] == ["b"]


def test_ambiguous_imports_are_reported_and_not_guessed(tmp_path, caplog):
    cg = graph(tmp_path, {
        "a/Item.java": "package company.a; public class Item {}",
        "b/Item.java": "package company.b; public class Item {}",
        "c/Box.java": "package company.c; import company.a.*; import company.b.*; public class Box { Item item; }",
    })
    assert not any(s == "c.Box" for s, _, _ in pairs(cg))
    assert "Ambiguous" in caplog.text


def test_inherited_nested_type(tmp_path):
    cg = graph(tmp_path, {
        "b/Base.java": "package company.b; public class Base { public static class Item {} }",
        "a/Other.java": "package company.a; public class Other { public static class Item {} }",
        "c/Box.java": "package company.c; import company.b.Base; public class Box extends Base { Item item; }",
    })
    assert ("c.Box", "b.Base.Item", "association") in pairs(cg)


def test_array_dimensions_after_variable_name(tmp_path):
    cg = graph(tmp_path, {
        "Item.java": "public class Item {}",
        "Box.java": "public class Box { Item one, many[]; }",
    })
    assert ("Box", "Item", "association") in pairs(cg)
    assert ("Box", "Item", "aggregation") in pairs(cg)


def test_enum_body_fields_are_extracted(tmp_path):
    cg = graph(tmp_path, {
        "Item.java": "public class Item {}",
        "Kind.java": "public enum Kind { FIRST; private Item item; public void run() {} }",
    })
    assert ("Kind", "Item", "association") in pairs(cg)
    assert "run()" in next(c.methods for c in cg.classes if c.name == "Kind")


def test_interface_singleton_reference_is_preserved(tmp_path):
    cg = graph(tmp_path, {
        "Factory.java": "public interface Factory { Factory INSTANCE = null; }",
    })
    assert ("Factory", "Factory", "association") in pairs(cg)


def test_named_and_unnamed_packages_do_not_collapse(tmp_path):
    cg = graph(tmp_path, {
        "Item.java": "public class Item {}",
        "company/Item.java": "package company; public class Item {}",
    })
    assert {c.qualified_name for c in cg.classes} == {"Item", "company.Item"}


def test_generic_parameter_does_not_resolve_to_project_class(tmp_path):
    cg = graph(tmp_path, {
        "T.java": "public class T {}",
        "Box.java": "public class Box<T> { T item; }",
    })
    assert not pairs(cg)


def test_custom_generic_wrapper_retains_declared_type_argument(tmp_path):
    cg = graph(tmp_path, {
        "Item.java": "public class Item {}",
        "SpecialList.java": "public class SpecialList<T> {}",
        "Box.java": "public class Box { SpecialList<Item> items; }",
    })
    assert ("Box", "SpecialList", "association") in pairs(cg)
    assert ("Box", "Item", "association") in pairs(cg)
    box = next(c for c in cg.classes if c.name == "Box")
    assert "items: SpecialList<Item>" in box.attributes


def test_cyclic_invalid_inheritance_does_not_recurse_forever(tmp_path):
    cg = graph(tmp_path, {
        "A.java": "public class A extends B { Missing item; }",
        "B.java": "public class B extends A {}",
    })
    assert len(cg.classes) == 2
