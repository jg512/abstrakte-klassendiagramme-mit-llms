from __future__ import annotations

from javauml.model import ClassInfo
from javauml.java.resolution import JavaTypeResolver


def build_import_graphs(
    classes: list[ClassInfo],
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """(module_imports, package_imports) für Java zurückgeben.

    Java-Imports taugen schlecht als Abhängigkeitssignal: Klassen im selben Paket
    brauchen gar keinen Import, und Stern-Importe nennen keine Typen. Deshalb wird
    der Graph aus *aufgelösten Typreferenzen* gebaut, also aus Obertypen und
    Feldtypen, die auf eine Klasse dieses Repos zeigen. Das ist genauer als das
    Lesen der Importzeilen und beruht auf denselben Informationen wie der
    Klassengraph.

    Schlüssel sind repo-relative Paketnamen, passend zu ClassInfo.module.
    """
    resolver = JavaTypeResolver(classes)
    module_of = {cls.qualified_name: cls.module for cls in classes}

    module_imports: dict[str, set[str]] = {c.module: set() for c in classes}
    for cls in classes:
        for target in _referenced_names(cls):
            resolved = resolver.resolve(target, cls)
            if resolved is not None:
                target_module = module_of[resolved]
                if target_module != cls.module:
                    module_imports[cls.module].add(target_module)

    package_imports: dict[str, set[str]] = {}
    for src, targets in module_imports.items():
        src_top = src.split(".")[0] if src else ""
        package_imports.setdefault(src_top, set())
        for tgt in targets:
            tgt_top = tgt.split(".")[0] if tgt else ""
            if tgt_top and tgt_top != src_top:
                package_imports[src_top].add(tgt_top)

    return (
        {k: sorted(v) for k, v in module_imports.items()},
        {k: sorted(v) for k, v in package_imports.items()},
    )


def _referenced_names(cls: ClassInfo) -> set[str]:
    names = set(cls.bases) | set(cls.interfaces)
    names.update(ref.type_name for ref in cls.field_refs)
    return names
