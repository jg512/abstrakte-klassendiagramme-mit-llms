"""Hilfen für die Tests, die aus Ordner 1 übernommen wurden.

Die Tests zur Typauflösung prüfen neben den Kanten auch den Paketgraphen und die
Vererbungstabelle, die in der Pipeline im ``CodeGraph`` stehen. ``code_graph``
baut dieselben Angaben so zusammen wie ``_build_java`` dort.
"""
from __future__ import annotations

from types import SimpleNamespace

from javauml.java.graph_builder import build_java_graph
from javauml.java.import_graph import build_import_graphs
from javauml.java.resolution import JavaTypeResolver
from javauml.java.ts_pass import analyze_java


def code_graph(root, files):
    analysis = analyze_java(files, root, "summary")
    classes = analysis.classes
    module_imports, package_imports = build_import_graphs(classes)
    static_graph = build_java_graph(classes, root.name, diagnostics=analysis.diagnostics)
    resolver = JavaTypeResolver(classes)
    inheritance = {
        c.qualified_name: sorted({r for base in c.bases
                                  if (r := resolver.resolve(base, c)) is not None})
        for c in classes
    }
    return SimpleNamespace(
        classes=classes, module_imports=module_imports, package_imports=package_imports,
        inheritance=inheritance, static_graph=static_graph, diagnostics=analysis.diagnostics,
    )
