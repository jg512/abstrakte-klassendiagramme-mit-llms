from __future__ import annotations

import logging
from collections import defaultdict

import community as community_louvain
import networkx as nx

from src.parsing.code_graph import CodeGraph
from src.schema.graph import AbstractGraph, Edge

log = logging.getLogger(__name__)


def cluster_modules(
    code_graph: CodeGraph,
    max_cluster_size: int = 40,
    min_cluster_size: int = 3,
    seed: int = 42,
) -> list[set[str]]:
    """Teilt die Module per Louvain-Community-Erkennung in Cluster auf.

    Für das Clustern gilt der Importgraph als ungerichtet. Danach werden zu große
    Cluster geteilt und zu kleine zusammengelegt.
    """
    # Die Modulnamen kommen aus den geparsten Klassen und dem Importgraphen. Das
    # funktioniert deshalb unverändert für Java (dort ist "Modul" das repo-relative Paket).
    modules = set()
    for cls in code_graph.classes:
        modules.add(cls.module)
    for src, targets in code_graph.module_imports.items():
        modules.add(src)
        modules.update(targets)

    # Ungerichteter Graph über die Module dieses Repos
    G: nx.Graph = nx.Graph()
    G.add_nodes_from(modules)
    for src, targets in code_graph.module_imports.items():
        if src not in modules:
            continue
        for tgt in targets:
            if tgt in modules and tgt != src:
                G.add_edge(src, tgt)

    if G.number_of_nodes() == 0:
        return []

    # Louvain auf dem ganzen (eventuell unzusammenhängenden) Graphen
    partition: dict[str, int] = community_louvain.best_partition(G, random_state=seed)

    # Module nach Community-ID gruppieren
    community_map: dict[int, set[str]] = defaultdict(set)
    for mod, cid in partition.items():
        community_map[cid].add(mod)

    clusters: list[set[str]] = list(community_map.values())
    log.debug("[clustering] Louvain produced %d communities over %d modules", len(clusters), G.number_of_nodes())

    # Zu große Cluster teilen
    clusters = _split_large(clusters, G, max_cluster_size, seed)

    # Zu kleine Cluster zusammenlegen
    clusters = _merge_small(clusters, G, min_cluster_size)

    log.info("[clustering] final: %d clusters (sizes: %s)", len(clusters), sorted(len(c) for c in clusters))
    return clusters


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _split_large(clusters: list[set[str]], G: nx.Graph, max_size: int, seed: int = 42) -> list[set[str]]:
    result: list[set[str]] = []
    for cluster in clusters:
        if len(cluster) <= max_size:
            result.append(cluster)
        else:
            result.extend(_recursive_split(cluster, G, max_size, seed))
    return result


def _recursive_split(cluster: set[str], G: nx.Graph, max_size: int, seed: int = 42) -> list[set[str]]:
    if len(cluster) <= max_size:
        return [cluster]
    sub = G.subgraph(cluster)
    sub_partition = community_louvain.best_partition(sub.to_undirected(), random_state=seed)
    sub_communities: dict[int, set[str]] = defaultdict(set)
    for mod, cid in sub_partition.items():
        sub_communities[cid].add(mod)
    sub_clusters = list(sub_communities.values())
    if len(sub_clusters) <= 1:
        # Weiter teilen geht nicht, der Cluster bleibt dann zu groß
        return [cluster]
    out: list[set[str]] = []
    for sc in sub_clusters:
        out.extend(_recursive_split(sc, G, max_size, seed))
    return out


def _merge_small(clusters: list[set[str]], G: nx.Graph, min_size: int) -> list[set[str]]:
    # Wiederholen, bis keine kleinen Cluster mehr übrig sind oder sich nichts mehr ändert
    for _ in range(len(clusters)):
        small = [c for c in clusters if len(c) < min_size]
        if not small:
            break
        large = [c for c in clusters if len(c) >= min_size]
        if not large:
            # Alle Cluster sind klein, also alles zusammenlegen
            merged: set[str] = set()
            for c in clusters:
                merged.update(c)
            return [merged]

        # Für jeden kleinen Cluster den großen suchen, zu dem die meisten Kanten führen
        for sc in small:
            best_idx, best_count = 0, -1
            for i, lc in enumerate(large):
                count = sum(
                    1 for m in sc for n in lc
                    if G.has_edge(m, n)
                )
                if count > best_count:
                    best_count = count
                    best_idx = i
            large[best_idx] = large[best_idx] | sc

        clusters = large

    return clusters


def inter_cluster_edges(
    code_graph: CodeGraph,
    clusters: list[set[str]],
) -> list[dict]:
    """Gibt die Importkanten zurück, die über Clustergrenzen gehen."""
    module_to_cluster: dict[str, int] = {}
    for idx, cluster in enumerate(clusters):
        for mod in cluster:
            module_to_cluster[mod] = idx

    edges: list[dict] = []
    seen: set[tuple[int, int, str, str]] = set()
    for src_mod, targets in code_graph.module_imports.items():
        src_cid = module_to_cluster.get(src_mod)
        if src_cid is None:
            continue
        for tgt_mod in targets:
            tgt_cid = module_to_cluster.get(tgt_mod)
            if tgt_cid is None or tgt_cid == src_cid:
                continue
            key = (src_cid, tgt_cid, src_mod, tgt_mod)
            if key not in seen:
                seen.add(key)
                edges.append({
                    "from_cluster": src_cid,
                    "to_cluster": tgt_cid,
                    "from_module": src_mod,
                    "to_module": tgt_mod,
                })
    return edges


_EDGE_STRENGTH: dict[str, int] = {
    "inheritance": 6, "realization": 5, "composition": 4,
    "aggregation": 3, "association": 2, "dependency": 1,
}


def naive_merge(
    sub_graphs: list[AbstractGraph],
    repo: str,
    target_nodes: int | None,
) -> AbstractGraph:
    """Führt die Teilgraphen zusammen.

    Doppelte Knoten und Pakete fallen weg, pro Knotenpaar bleibt die stärkste Kante.
    """
    merged = AbstractGraph(repo=repo, target_nodes=target_nodes)
    seen_nodes: set[str] = set()
    seen_pkgs: set[str] = set()
    seen_edges: dict[tuple[str, str], Edge] = {}  # (src, tgt) -> stärkste Kante

    for sg in sub_graphs:
        for pkg in sg.packages:
            if pkg.name not in seen_pkgs:
                seen_pkgs.add(pkg.name)
                merged.packages.append(pkg)
        for node in sg.nodes:
            if node.id not in seen_nodes:
                seen_nodes.add(node.id)
                merged.nodes.append(node)
        for edge in sg.edges:
            key = (edge.source, edge.target)
            if key not in seen_edges or (
                _EDGE_STRENGTH.get(edge.type, 0) > _EDGE_STRENGTH.get(seen_edges[key].type, 0)
            ):
                seen_edges[key] = edge

    merged.edges = list(seen_edges.values())
    return merged
