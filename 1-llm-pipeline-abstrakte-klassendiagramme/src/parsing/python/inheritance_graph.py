from __future__ import annotations

from src.parsing.python.ast_pass import ClassInfo


def build_inheritance_graph(classes: list[ClassInfo]) -> dict[str, list[str]]:
    """{qualifizierter_name: [aufgelöste_basisklasse, ...]} für interne Klassen zurückgeben.

    Basisklassen, die sich keiner bekannten internen Klasse zuordnen lassen, fallen
    weg. Die Zuordnung geht nur über den Kurznamen: Gibt es genau einen Treffer,
    wird er genommen. Bei mehreren gewinnt der aus demselben Modul, danach der aus
    demselben obersten Paket, sonst der erste Kandidat.
    """
    by_short: dict[str, list[str]] = {}
    for c in classes:
        by_short.setdefault(c.name, []).append(c.qualified_name)

    result: dict[str, list[str]] = {}
    for c in classes:
        resolved: list[str] = []
        for base in c.bases:
            short = base.split(".")[-1]
            candidates = by_short.get(short, [])
            if not candidates:
                continue
            if len(candidates) == 1:
                resolved.append(candidates[0])
            else:
                # Zuerst eine Basisklasse im selben Modul, dann im selben Paket oberster Ebene.
                same_mod = [q for q in candidates if q.startswith(c.module + ".")]
                if same_mod:
                    resolved.append(same_mod[0])
                else:
                    src_pkg = c.module.split(".")[0]
                    same_pkg = [q for q in candidates if q.split(".")[0] == src_pkg]
                    resolved.append((same_pkg or candidates)[0])
        result[c.qualified_name] = resolved

    return result
