"""Die acht Varianten des Drivers und wie sie sich unterscheiden.

Alle Varianten laufen durch dieselbe Driver-Schleife. Sie unterscheiden sich
nur in drei Einstellungen, dazu kommt ein Schalter für die Zerlegung:

  seed          "empty"     der Graph startet leer, das Modell baut ihn auf
                "pyreverse" der Graph startet mit dem vollen Klassengraphen
                            (pyreverse bzw. Java-Parser), das Modell streicht (prune)
  context       "overview"  Paketbaum, qualifizierte Klassennamen und Importkanten
                "clusters"  Module und Klassen pro Cluster, jeweils zusammen mit
                            der Übersicht über das ganze Repo
                "graph"     der volle Klassengraph als JSON (catalog)
  peek          ob das Modell den Quelltext lesen darf
  decomposition "none" oder "per_cluster" (ein Teillauf pro Cluster, danach
                eine Zusammenführung)

Vier Grundstrategien, jeweils mit und ohne Peek, ergeben acht Varianten. Die
alten Methodennamen (m1a bis m4b) bildet ALIASES auf die passende Variante ab.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Variant:
    name: str
    seed: str            # "empty" | "pyreverse"
    context: str         # "overview" | "clusters" | "graph"
    peek: bool
    decomposition: str   # "none" | "per_cluster"

    @property
    def needs_pyreverse(self) -> bool:
        return self.seed == "pyreverse" or self.context == "graph"


VARIANTS: dict[str, Variant] = {
    v.name: v
    for v in (
        Variant("overview",      seed="empty",     context="overview", peek=False, decomposition="none"),
        Variant("overview-peek", seed="empty",     context="overview", peek=True,  decomposition="none"),
        Variant("cluster",       seed="empty",     context="clusters", peek=False, decomposition="per_cluster"),
        Variant("cluster-peek",  seed="empty",     context="clusters", peek=True,  decomposition="per_cluster"),
        Variant("catalog",       seed="empty",     context="graph",    peek=False, decomposition="none"),
        Variant("catalog-peek",  seed="empty",     context="graph",    peek=True,  decomposition="none"),
        Variant("prune",         seed="pyreverse", context="graph",    peek=False, decomposition="none"),
        Variant("prune-peek",    seed="pyreverse", context="graph",    peek=True,  decomposition="none"),
    )
}

# Alte Methodennamen aus der Zeit vor der Vereinheitlichung.
ALIASES: dict[str, str] = {
    "m1a": "catalog",
    "m1b": "catalog-peek",
    "m2": "overview-peek",
    "m3": "cluster-peek",
    "m4a": "prune",
    "m4b": "prune-peek",
}


def resolve(name: str) -> Variant:
    canonical = ALIASES.get(name, name)
    variant = VARIANTS.get(canonical)
    if variant is None:
        known = sorted(VARIANTS) + sorted(ALIASES)
        raise ValueError(f"Unknown variant {name!r}; known: {known}")
    return variant
