"""Vorsichtige Auflösung von Java-Typen allein aus dem Quelltext, für alle Java-Graphen.

Das ist kein Symbol-Solver wie im Compiler: Abhängigkeits-JARs, Zugriffsprüfungen
und lokale Methodenscopes stehen nicht zur Verfügung. Mehrdeutige Referenzen
werden weggelassen und gemeldet.
"""
from __future__ import annotations

from collections import defaultdict
import logging

from src.parsing.models import ClassInfo

log = logging.getLogger(__name__)


class JavaTypeResolver:
    def __init__(self, classes: list[ClassInfo]):
        self.by_full: dict[str, list[ClassInfo]] = defaultdict(list)
        self.by_id = {c.qualified_name: c for c in classes}
        for c in classes:
            self.by_full[c.source_qualified_name or c.qualified_name].append(c)
        self.ambiguous: set[tuple[str, str]] = set()
        self._cache: dict[tuple[str, str], str | None] = {}

    def _select(self, names: list[str], source: ClassInfo, ref: str) -> str | None:
        candidates = [c for n in dict.fromkeys(names) for c in self.by_full.get(n, ())]
        # Gleiche voll qualifizierte Namen können in getrennten Maven- oder
        # Gradle-Modulen durchaus vorkommen. Eine Referenz wird deshalb zuerst im
        # eigenen Modul aufgelöst, bevor sie im ganzen Repo als mehrdeutig gilt.
        same_module = [c for c in candidates if c.build_module == source.build_module]
        if len(same_module) == 1:
            return same_module[0].qualified_name
        if len(candidates) == 1:
            return candidates[0].qualified_name
        if len(candidates) > 1:
            key = (source.qualified_name, ref)
            if key not in self.ambiguous:
                log.warning("Ambiguous Java type %r from %s; omitting relation (%s)",
                            ref, source.qualified_name,
                            ", ".join(c.source_qualified_name or c.qualified_name for c in candidates))
            self.ambiguous.add(key)
        return None

    def resolve(self, name: str, source: ClassInfo) -> str | None:
        key = (source.qualified_name, name)
        if key not in self._cache:
            self._cache[key] = self._resolve(name, source, set())
        return self._cache[key]

    def _resolve(self, name: str, source: ClassInfo,
                 seen: set[tuple[str, str]]) -> str | None:
        key = (source.qualified_name, name)
        if key in seen:
            return None
        seen = seen | {key}
        first, _, suffix = name.partition(".")
        if first in source.type_parameters:
            return None

        full = source.source_qualified_name or source.qualified_name
        package = source.source_package if source.source_qualified_name else source.module
        local = full[len(package) + 1:] if package else full
        parts = local.split(".")
        # Member des eigenen und der umschließenden Typen, auch geerbte
        # verschachtelte Typen, haben Vorrang vor Imports. Durchlaufen werden nur
        # echte Typscopes.
        for end in range(len(parts), 0, -1):
            scope = ".".join(p for p in (package, ".".join(parts[:end])) if p)
            candidate = f"{scope}.{name}"
            if candidate in self.by_full:
                return self._select([candidate], source, name)
            owners = self.by_full.get(scope, ())
            if len(owners) == 1:
                owner = owners[0]
                if first in owner.type_parameters:
                    return None
                # Wer eine Oberklasse nachschlägt, darf dabei nicht rekursiv in den
                # Membern derselben Oberklasse suchen. Das ergäbe einen Zyklus, und
                # weil es für jeden Vorfahren passiert, würde der Aufwand bei tiefen
                # Hierarchien exponentiell.
                inherited = ([] if name in owner.bases + owner.interfaces else
                             self._inherited(owner, name, seen, set()))
                if inherited:
                    return self._select(inherited, source, name)

        # Ein expliziter Import gilt, auch wenn er auf einen Bibliothekstyp zeigt und
        # ein anderer Projekttyp denselben Kurznamen hat.
        imports = [i for i in source.imports if not i.endswith(".*") and i.rsplit(".", 1)[-1] == first]
        if imports:
            return self._select([i + ("." + suffix if suffix else "") for i in imports], source, name)

        candidate = f"{package}.{name}" if package else name
        if candidate in self.by_full:
            return self._select([candidate], source, name)
        if "." in name and name in self.by_full:
            return self._select([name], source, name)
        wildcard = [i[:-2] + "." + name for i in source.imports if i.endswith(".*")]
        wildcard.append("java.lang." + name)
        return self._select(wildcard, source, name)

    def _inherited(self, owner: ClassInfo, name: str,
                   resolving: set[tuple[str, str]], ancestors: set[str]) -> list[str]:
        if owner.qualified_name in ancestors:
            return []
        ancestors = ancestors | {owner.qualified_name}
        found = []
        for base in owner.bases + owner.interfaces:
            resolved = self._resolve(base, owner, resolving)
            parent = self.by_id.get(resolved)
            if parent is None:
                continue
            full = parent.source_qualified_name or parent.qualified_name
            candidate = full + "." + name
            if candidate in self.by_full:
                found.append(candidate)
            else:
                found.extend(self._inherited(parent, name, resolving, ancestors))
        return list(dict.fromkeys(found))

    def external_name(self, name: str, source: ClassInfo) -> str:
        first, _, suffix = name.partition(".")
        imports = [i for i in source.imports if not i.endswith(".*") and i.rsplit(".", 1)[-1] == first]
        if len(imports) == 1:
            return imports[0] + ("." + suffix if suffix else "")
        return name
