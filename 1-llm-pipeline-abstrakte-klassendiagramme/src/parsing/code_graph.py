from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from src.config.models import JavaConfig
from src.parsing.python.ast_pass import run_ast_pass
from src.parsing.python.import_graph import build_import_graphs
from src.parsing.python.inheritance_graph import build_inheritance_graph
from src.parsing.languages import DEFAULT_LANGUAGE, resolve_language
from src.parsing.models import ClassInfo, FunctionInfo
from src.parsing.python.pyreverse_adapter import run_pyreverse
from src.schema.graph import AbstractGraph, Diagnostic

logger = logging.getLogger(__name__)


@dataclass
class CodeGraph:
    repo: str
    root: Path
    source_files: list[Path]
    classes: list[ClassInfo]
    functions: list[FunctionInfo]
    module_imports: dict[str, list[str]]
    package_imports: dict[str, list[str]]
    inheritance: dict[str, list[str]]
    # Der vollständige Klassengraph, so wie er im Code steht: pyreverse für
    # Python, der tree-sitter-Extraktor für Java. Er ist der Startgraph der prune-Varianten und der
    # Kontext der catalog-Varianten.
    static_graph: AbstractGraph | None = None
    language: str = DEFAULT_LANGUAGE
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def pyreverse_graph(self) -> AbstractGraph | None:
        """Alias aus Kompatibilitätsgründen. Das Variantenraster nennt diesen Startgraphen
        weiterhin 'pyreverse', und vorhandene Laufausgaben sind unter diesem Namen abgelegt."""
        return self.static_graph


def build_code_graph(
    root: Path,
    source_files: list[Path],
    repo: str = "",
    use_static_graph: bool = True,
    language: str = DEFAULT_LANGUAGE,
    java_options: JavaConfig | None = None,
) -> CodeGraph:
    """Alle Parser-Durchläufe für `language` ausführen und einen gesammelten CodeGraph zurückgeben."""
    spec = resolve_language(language)
    logger.debug("%s pass on %d files in %s", spec.name, len(source_files), root)

    if spec.name == "java":
        return _build_java(
            root, source_files, repo or root.name, use_static_graph,
            java_options or JavaConfig(),
        )
    return _build_python(root, source_files, repo or root.name, use_static_graph)


def _build_python(
    root: Path, files: list[Path], repo: str, use_static_graph: bool
) -> CodeGraph:
    classes, functions = run_ast_pass(files, root)
    module_imports, package_imports = build_import_graphs(files, root)

    static_graph: AbstractGraph | None = None
    if use_static_graph:
        logger.debug("Running pyreverse on %s", root)
        static_graph = run_pyreverse(root)
        if static_graph is None:
            logger.info("pyreverse unavailable or failed for %s — "
                        "catalog/prune variants skipped", root)

    return CodeGraph(
        repo=repo,
        root=root,
        source_files=files,
        classes=classes,
        functions=functions,
        module_imports=module_imports,
        package_imports=package_imports,
        inheritance=build_inheritance_graph(classes),
        static_graph=static_graph,
        language="python",
    )


def _build_java(
    root: Path, files: list[Path], repo: str, use_static_graph: bool,
    options: JavaConfig,
) -> CodeGraph:
    from src.parsing.java import analyze_java, build_java_graph
    from src.parsing.java.import_graph import build_import_graphs as java_imports
    from src.parsing.java.resolution import JavaTypeResolver

    analysis = analyze_java(files, root, options.member_profile)
    classes, functions = analysis.classes, analysis.functions
    module_imports, package_imports = java_imports(classes)

    compiler_edges = []
    if options.symbol_solver == "javac":
        from src.parsing.java.javac_solver import resolve_with_javac
        compiler_edges, compiler_diagnostics = resolve_with_javac(
            files, root, classes, options.classpath
        )
        analysis.diagnostics.extend(compiler_diagnostics)

    # Anders als pyreverse braucht das kein externes Werkzeug und kann nicht
    # getrennt vom Parsen ausfallen, ist also immer verfügbar.
    static_graph = None
    if use_static_graph and options.relation_style == "intellij":
        from src.parsing.java.intellij import IdeEnvironment, build_intellij_graph
        static_graph = build_intellij_graph(
            files, root, repo,
            IdeEnvironment(jdk=options.ide_jdk, same_package=options.ide_same_package),
            list(options.diagram_classes) or None,
        )
    elif use_static_graph:
        static_graph = build_java_graph(
            classes,
            repo,
            include_external_supertypes=options.include_external_supertypes,
            include_method_dependencies=options.include_method_dependencies,
            diagnostics=analysis.diagnostics,
            compiler_edges=compiler_edges,
        )
    resolver = JavaTypeResolver(classes)
    inheritance = {
        c.qualified_name: sorted({resolved for base in c.bases
                                 if (resolved := resolver.resolve(base, c)) is not None})
        for c in classes
    }

    return CodeGraph(
        repo=repo,
        root=root,
        source_files=files,
        classes=classes,
        functions=functions,
        module_imports=module_imports,
        package_imports=package_imports,
        inheritance=inheritance,
        static_graph=static_graph,
        language="java",
        diagnostics=analysis.diagnostics,
    )
