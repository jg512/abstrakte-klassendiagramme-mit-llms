from __future__ import annotations

import pytest

from src.methods.variants import ALIASES, VARIANTS, resolve


def test_grid_has_eight_variants():
    assert len(VARIANTS) == 8


def test_grid_covers_axes():
    # 4 Grundstrategien mal Peek an/aus
    peek_on = [v for v in VARIANTS.values() if v.peek]
    peek_off = [v for v in VARIANTS.values() if not v.peek]
    assert len(peek_on) == 4
    assert len(peek_off) == 4
    assert {v.seed for v in VARIANTS.values()} == {"empty", "pyreverse"}
    assert {v.context for v in VARIANTS.values()} == {"overview", "clusters", "graph"}
    assert {v.decomposition for v in VARIANTS.values()} == {"none", "per_cluster"}


@pytest.mark.parametrize(
    ("legacy", "canonical"),
    [
        ("m1a", "catalog"),
        ("m1b", "catalog-peek"),
        ("m2", "overview-peek"),
        ("m3", "cluster-peek"),
        ("m4a", "prune"),
        ("m4b", "prune-peek"),
    ],
)
def test_legacy_aliases_resolve(legacy, canonical):
    assert resolve(legacy) is VARIANTS[canonical]


def test_canonical_names_resolve_to_themselves():
    for name, variant in VARIANTS.items():
        assert resolve(name) is variant


def test_alias_axes_match_old_methods():
    m1a = resolve("m1a")
    assert (m1a.seed, m1a.context, m1a.peek) == ("empty", "graph", False)
    m4a = resolve("m4a")
    assert (m4a.seed, m4a.context, m4a.peek) == ("pyreverse", "graph", False)
    m2 = resolve("m2")
    assert (m2.seed, m2.context, m2.peek) == ("empty", "overview", True)
    m3 = resolve("m3")
    assert m3.decomposition == "per_cluster"


def test_needs_pyreverse():
    assert resolve("catalog").needs_pyreverse
    assert resolve("catalog-peek").needs_pyreverse
    assert resolve("prune").needs_pyreverse
    assert resolve("prune-peek").needs_pyreverse
    assert not resolve("overview").needs_pyreverse
    assert not resolve("overview-peek").needs_pyreverse
    assert not resolve("cluster").needs_pyreverse
    assert not resolve("cluster-peek").needs_pyreverse


def test_unknown_variant_raises():
    with pytest.raises(ValueError, match="Unknown variant"):
        resolve("m5x")
