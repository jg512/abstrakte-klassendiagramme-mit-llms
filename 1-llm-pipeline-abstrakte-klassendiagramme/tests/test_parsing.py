from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from src.parsing.python.ast_pass import ClassInfo, FunctionInfo, module_name, run_ast_pass
from src.parsing.python.import_graph import build_import_graphs
from src.parsing.python.inheritance_graph import build_inheritance_graph
from src.parsing.python.pyreverse_adapter import parse_pyreverse_output
from src.parsing.code_graph import CodeGraph, build_code_graph


# Feste pyreverse-Ausgabe für ein Modul mit zwei Klassen, so wie pyreverse sie
# typischerweise erzeugt. Damit brauchen diese Tests weder Netz noch pylint.

PYREVERSE_FIXTURE = textwrap.dedent("""\
    @startuml classes
    set namespaceSeparator none
    class "schedule.Job" as schedule.Job {
      cancel_after : NoneType
      interval : int
      job_func : NoneType
      next_run : datetime
      unit : str
      cancel()
      run()
      should_run()
    }
    class "schedule.Scheduler" as schedule.Scheduler {
      jobs : list
      cancel_job(job)
      clear(tag)
      run_all(delay_seconds)
      run_pending()
    }
    schedule.Scheduler o-- schedule.Job : jobs
    @enduml
""")

# Testdaten für die Ausgabe mit namespace-Blöcken
PYREVERSE_NAMESPACE_FIXTURE = textwrap.dedent("""\
    @startuml classes
    namespace myapp {
      class Foo <<dataclass>> {
        value : int
        compute()
      }
      class Bar <<interface>> {
        run()
      }
    }
    myapp.Foo --|> myapp.Bar
    @enduml
""")


# Hilfsfunktionen


def _write(tmp_path: Path, rel: str, src: str) -> Path:
    f = tmp_path / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(textwrap.dedent(src))
    return f


def _collect(tmp_path: Path) -> list[Path]:
    return sorted(tmp_path.rglob("*.py"))


# module_name


class TestModuleName:
    def test_simple_file(self, tmp_path):
        f = tmp_path / "foo.py"
        assert module_name(f, tmp_path) == "foo"

    def test_package_file(self, tmp_path):
        f = tmp_path / "pkg" / "mod.py"
        assert module_name(f, tmp_path) == "pkg.mod"

    def test_init_file(self, tmp_path):
        f = tmp_path / "pkg" / "__init__.py"
        assert module_name(f, tmp_path) == "pkg"

    def test_nested_init(self, tmp_path):
        f = tmp_path / "a" / "b" / "__init__.py"
        assert module_name(f, tmp_path) == "a.b"

    def test_deep_package(self, tmp_path):
        f = tmp_path / "a" / "b" / "c.py"
        assert module_name(f, tmp_path) == "a.b.c"


# run_ast_pass: ClassInfo


class TestAstPassClasses:
    def test_simple_class(self, tmp_path):
        _write(tmp_path, "mod.py", """\
            class Foo:
                x: int = 0
                def bar(self):
                    pass
        """)
        classes, _ = run_ast_pass(_collect(tmp_path), tmp_path)
        assert len(classes) == 1
        c = classes[0]
        assert c.name == "Foo"
        assert c.qualified_name == "mod.Foo"
        assert c.module == "mod"

    def test_class_attributes_from_init(self, tmp_path):
        _write(tmp_path, "mod.py", """\
            class Foo:
                def __init__(self):
                    self.value = 42
                    self.name: str = "x"
        """)
        classes, _ = run_ast_pass(_collect(tmp_path), tmp_path)
        c = classes[0]
        assert "value" in c.attributes
        assert "name: str" in c.attributes

    def test_class_level_annotation(self, tmp_path):
        _write(tmp_path, "mod.py", """\
            class Foo:
                count: int
                label: str
        """)
        classes, _ = run_ast_pass(_collect(tmp_path), tmp_path)
        attrs = classes[0].attributes
        assert "count: int" in attrs
        assert "label: str" in attrs

    def test_methods_extracted(self, tmp_path):
        _write(tmp_path, "mod.py", """\
            class Foo:
                def run(self):
                    pass
                def stop(self, reason):
                    pass
                def _private(self):
                    pass
        """)
        classes, _ = run_ast_pass(_collect(tmp_path), tmp_path)
        methods = classes[0].methods
        assert "run()" in methods
        assert "stop(reason)" in methods
        assert "_private()" not in methods

    def test_init_included_in_methods(self, tmp_path):
        _write(tmp_path, "mod.py", """\
            class Foo:
                def __init__(self, x):
                    self.x = x
        """)
        classes, _ = run_ast_pass(_collect(tmp_path), tmp_path)
        methods = classes[0].methods
        assert "__init__(x)" in methods

    def test_bases_extracted(self, tmp_path):
        _write(tmp_path, "mod.py", """\
            class Bar(Base, Mixin):
                pass
        """)
        classes, _ = run_ast_pass(_collect(tmp_path), tmp_path)
        assert classes[0].bases == ["Base", "Mixin"]

    def test_decorator_extracted(self, tmp_path):
        _write(tmp_path, "mod.py", """\
            from dataclasses import dataclass

            @dataclass
            class Config:
                host: str
        """)
        classes, _ = run_ast_pass(_collect(tmp_path), tmp_path)
        assert "dataclass" in classes[0].decorators

    def test_multiple_files(self, tmp_path):
        _write(tmp_path, "a.py", "class A: pass\n")
        _write(tmp_path, "b.py", "class B: pass\n")
        classes, _ = run_ast_pass(_collect(tmp_path), tmp_path)
        names = {c.name for c in classes}
        assert names == {"A", "B"}

    def test_syntax_error_file_skipped(self, tmp_path):
        _write(tmp_path, "bad.py", "def (:\n")
        _write(tmp_path, "good.py", "class Good: pass\n")
        classes, _ = run_ast_pass(_collect(tmp_path), tmp_path)
        assert len(classes) == 1
        assert classes[0].name == "Good"

    def test_nested_class_not_extracted(self, tmp_path):
        _write(tmp_path, "mod.py", """\
            class Outer:
                class Inner:
                    pass
        """)
        classes, _ = run_ast_pass(_collect(tmp_path), tmp_path)
        names = {c.name for c in classes}
        assert "Outer" in names
        assert "Inner" not in names

    def test_qualified_name_in_package(self, tmp_path):
        _write(tmp_path, "pkg/__init__.py", "")
        _write(tmp_path, "pkg/core.py", "class Core: pass\n")
        classes, _ = run_ast_pass(_collect(tmp_path), tmp_path)
        core = next(c for c in classes if c.name == "Core")
        assert core.qualified_name == "pkg.core.Core"
        assert core.module == "pkg.core"

    def test_line_range(self, tmp_path):
        _write(tmp_path, "mod.py", """\
            class Foo:
                pass
        """)
        classes, _ = run_ast_pass(_collect(tmp_path), tmp_path)
        c = classes[0]
        assert c.line_start == 1
        assert c.line_end >= 1

    def test_vararg_in_method_sig(self, tmp_path):
        _write(tmp_path, "mod.py", """\
            class Foo:
                def do(self, *args, **kwargs):
                    pass
        """)
        classes, _ = run_ast_pass(_collect(tmp_path), tmp_path)
        assert "do(*args, **kwargs)" in classes[0].methods


# run_ast_pass: FunctionInfo


class TestAstPassFunctions:
    def test_module_level_function(self, tmp_path):
        _write(tmp_path, "mod.py", """\
            def helper(x, y):
                return x + y
        """)
        _, functions = run_ast_pass(_collect(tmp_path), tmp_path)
        assert len(functions) == 1
        f = functions[0]
        assert f.name == "helper"
        assert f.qualified_name == "mod.helper"

    def test_class_method_not_in_functions(self, tmp_path):
        _write(tmp_path, "mod.py", """\
            class Foo:
                def bar(self): pass

            def top(): pass
        """)
        _, functions = run_ast_pass(_collect(tmp_path), tmp_path)
        assert len(functions) == 1
        assert functions[0].name == "top"


# build_import_graphs


class TestImportGraphs:
    def _setup(self, tmp_path: Path) -> list[Path]:
        _write(tmp_path, "pkg/__init__.py", "")
        _write(tmp_path, "pkg/a.py", "from pkg import b\n")
        _write(tmp_path, "pkg/b.py", "import os\n")
        _write(tmp_path, "pkg/c.py", "from pkg.a import something\n")
        return _collect(tmp_path)

    def test_internal_edge_present(self, tmp_path):
        files = self._setup(tmp_path)
        mi, _ = build_import_graphs(files, tmp_path)
        assert "pkg.b" in mi.get("pkg.a", [])

    def test_external_import_excluded(self, tmp_path):
        files = self._setup(tmp_path)
        mi, _ = build_import_graphs(files, tmp_path)
        assert "os" not in mi.get("pkg.b", [])

    def test_from_import_resolved(self, tmp_path):
        files = self._setup(tmp_path)
        mi, _ = build_import_graphs(files, tmp_path)
        assert "pkg.a" in mi.get("pkg.c", [])

    def test_package_imports_built(self, tmp_path):
        _write(tmp_path, "alpha/__init__.py", "")
        _write(tmp_path, "alpha/mod.py", "")
        _write(tmp_path, "beta/__init__.py", "")
        _write(tmp_path, "beta/mod.py", "from alpha import mod\n")
        files = _collect(tmp_path)
        _, pi = build_import_graphs(files, tmp_path)
        assert "alpha" in pi.get("beta", [])

    def test_relative_import_resolved(self, tmp_path):
        _write(tmp_path, "pkg/__init__.py", "")
        _write(tmp_path, "pkg/a.py", "from . import b\n")
        _write(tmp_path, "pkg/b.py", "")
        files = _collect(tmp_path)
        mi, _ = build_import_graphs(files, tmp_path)
        assert "pkg.b" in mi.get("pkg.a", [])

    def test_relative_parent_import(self, tmp_path):
        _write(tmp_path, "pkg/__init__.py", "")
        _write(tmp_path, "pkg/sub/__init__.py", "")
        _write(tmp_path, "pkg/sub/leaf.py", "from .. import utils\n")
        _write(tmp_path, "pkg/utils.py", "")
        files = _collect(tmp_path)
        mi, _ = build_import_graphs(files, tmp_path)
        assert "pkg.utils" in mi.get("pkg.sub.leaf", [])

    def test_all_modules_keyed(self, tmp_path):
        files = self._setup(tmp_path)
        mi, _ = build_import_graphs(files, tmp_path)
        modules = set(mi.keys())
        assert "pkg" in modules
        assert "pkg.a" in modules
        assert "pkg.b" in modules


# build_inheritance_graph


class TestInheritanceGraph:
    def _make_classes(self, specs: list[tuple[str, str, list[str]]]) -> list[ClassInfo]:
        """specs: (name, module, bases)"""
        result = []
        for name, module, bases in specs:
            result.append(ClassInfo(
                name=name,
                qualified_name=f"{module}.{name}",
                module=module,
                bases=bases,
                decorators=[],
                attributes=[],
                methods=[],
                file=Path("dummy.py"),
                line_start=1,
                line_end=1,
            ))
        return result

    def test_simple_inheritance(self):
        classes = self._make_classes([
            ("Animal", "zoo", []),
            ("Dog", "zoo", ["Animal"]),
        ])
        graph = build_inheritance_graph(classes)
        assert graph["zoo.Dog"] == ["zoo.Animal"]

    def test_unresolvable_base_dropped(self):
        classes = self._make_classes([("Foo", "mod", ["ExternalBase"])])
        graph = build_inheritance_graph(classes)
        assert graph["mod.Foo"] == []

    def test_no_bases(self):
        classes = self._make_classes([("Foo", "mod", [])])
        graph = build_inheritance_graph(classes)
        assert graph["mod.Foo"] == []

    def test_same_module_preferred(self):
        classes = self._make_classes([
            ("Base", "a", []),
            ("Base", "b", []),
            ("Child", "a", ["Base"]),
        ])
        graph = build_inheritance_graph(classes)
        assert graph["a.Child"] == ["a.Base"]

    def test_multiple_bases(self):
        classes = self._make_classes([
            ("A", "mod", []),
            ("B", "mod", []),
            ("C", "mod", ["A", "B"]),
        ])
        graph = build_inheritance_graph(classes)
        assert set(graph["mod.C"]) == {"mod.A", "mod.B"}


# parse_pyreverse_output


class TestPyreverseParser:
    def test_classes_parsed(self):
        graph = parse_pyreverse_output(PYREVERSE_FIXTURE, repo="schedule")
        ids = {n.id for n in graph.nodes}
        assert "schedule.Job" in ids
        assert "schedule.Scheduler" in ids

    def test_node_names(self):
        graph = parse_pyreverse_output(PYREVERSE_FIXTURE)
        job = next(n for n in graph.nodes if n.id == "schedule.Job")
        assert job.name == "Job"

    def test_attributes_parsed(self):
        graph = parse_pyreverse_output(PYREVERSE_FIXTURE)
        job = next(n for n in graph.nodes if n.id == "schedule.Job")
        assert any("interval" in a for a in job.attributes)
        assert any("unit" in a for a in job.attributes)

    def test_methods_parsed(self):
        graph = parse_pyreverse_output(PYREVERSE_FIXTURE)
        job = next(n for n in graph.nodes if n.id == "schedule.Job")
        assert any("run" in m for m in job.methods)

    def test_composition_edge_parsed(self):
        graph = parse_pyreverse_output(PYREVERSE_FIXTURE)
        edges = [(e.source, e.type, e.target) for e in graph.edges]
        assert ("schedule.Scheduler", "composition", "schedule.Job") in edges

    def test_packages_inferred(self):
        graph = parse_pyreverse_output(PYREVERSE_FIXTURE)
        pkg_names = {p.name for p in graph.packages}
        assert "schedule" in pkg_names

    def test_repo_name_set(self):
        graph = parse_pyreverse_output(PYREVERSE_FIXTURE, repo="myrepo")
        assert graph.repo == "myrepo"

    def test_namespace_style(self):
        graph = parse_pyreverse_output(PYREVERSE_NAMESPACE_FIXTURE)
        ids = {n.id for n in graph.nodes}
        assert "myapp.Foo" in ids
        assert "myapp.Bar" in ids

    def test_stereotype_dataclass(self):
        graph = parse_pyreverse_output(PYREVERSE_NAMESPACE_FIXTURE)
        foo = next(n for n in graph.nodes if n.name == "Foo")
        assert foo.stereotype == "dataclass"

    def test_stereotype_interface(self):
        graph = parse_pyreverse_output(PYREVERSE_NAMESPACE_FIXTURE)
        bar = next(n for n in graph.nodes if n.name == "Bar")
        assert bar.stereotype == "interface"

    def test_inheritance_edge(self):
        graph = parse_pyreverse_output(PYREVERSE_NAMESPACE_FIXTURE)
        edges = [(e.source, e.type, e.target) for e in graph.edges]
        assert ("myapp.Foo", "inheritance", "myapp.Bar") in edges

    def test_empty_puml(self):
        graph = parse_pyreverse_output("@startuml\n@enduml\n")
        assert graph.nodes == []
        assert graph.edges == []

    def test_class_without_body(self):
        puml = textwrap.dedent("""\
            @startuml classes
            class "mymod.Empty" as mymod.Empty
            @enduml
        """)
        graph = parse_pyreverse_output(puml)
        assert any(n.id == "mymod.Empty" for n in graph.nodes)

    def test_abstract_stereotype(self):
        puml = textwrap.dedent("""\
            @startuml classes
            abstract class "mod.Base" as mod.Base {
            }
            @enduml
        """)
        graph = parse_pyreverse_output(puml)
        base = next(n for n in graph.nodes if n.id == "mod.Base")
        assert base.stereotype == "abstract"

    def test_node_package_set(self):
        graph = parse_pyreverse_output(PYREVERSE_FIXTURE)
        job = next(n for n in graph.nodes if n.id == "schedule.Job")
        assert job.package == "schedule"

    def test_self_edge_dropped(self):
        puml = textwrap.dedent("""\
            @startuml classes
            class "a.A" as a.A {}
            a.A --|> a.A
            @enduml
        """)
        graph = parse_pyreverse_output(puml)
        assert graph.edges == []


# build_code_graph: Zusammenspiel


class TestBuildCodeGraph:
    def test_basic_integration(self, tmp_path):
        _write(tmp_path, "mypkg/__init__.py", "")
        _write(tmp_path, "mypkg/core.py", """\
            class Engine:
                speed: int
                def start(self): pass
        """)
        _write(tmp_path, "mypkg/utils.py", """\
            from mypkg import core
            def helper(): pass
        """)
        files = _collect(tmp_path)
        cg = build_code_graph(tmp_path, files, repo="test", use_static_graph=False)

        assert isinstance(cg, CodeGraph)
        assert cg.repo == "test"
        assert len(cg.classes) == 1
        assert cg.classes[0].name == "Engine"
        assert len(cg.functions) == 1
        assert "mypkg.utils" in cg.module_imports
        assert "mypkg.core" in cg.module_imports["mypkg.utils"]
        assert cg.static_graph is None  # use_static_graph=False

    def test_inheritance_graph_populated(self, tmp_path):
        _write(tmp_path, "mod.py", """\
            class Base: pass
            class Child(Base): pass
        """)
        files = _collect(tmp_path)
        cg = build_code_graph(tmp_path, files, use_static_graph=False)
        assert "mod.Child" in cg.inheritance
        assert "mod.Base" in cg.inheritance["mod.Child"]

    def test_empty_repo(self, tmp_path):
        cg = build_code_graph(tmp_path, [], use_static_graph=False)
        assert cg.classes == []
        assert cg.functions == []
