from __future__ import annotations

import json

import pytest

pytest.importorskip("tree_sitter_java", reason="tree-sitter-java fehlt")

from javauml.cli import main  # noqa: E402
from javauml.repo import is_url, repo_name  # noqa: E402


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "shop"
    (root / "src/main/java/de/shop").mkdir(parents=True)
    (root / "src/main/java/de/shop/Kunde.java").write_text(
        "package de.shop; import java.util.List;\n"
        "public class Kunde { private List<Bestellung> bestellungen; }\n")
    (root / "src/main/java/de/shop/Bestellung.java").write_text(
        "package de.shop; public class Bestellung {\n"
        "  Kunde kaeufer() { return new Kunde(); } }\n")
    return root


def test_writes_json_and_puml(repo, tmp_path, capsys):
    out = tmp_path / "out"
    assert main([str(repo), "-o", str(out)]) == 0
    graph = json.loads((out / "shop" / "klassendiagramm.json").read_text())
    assert {n["id"] for n in graph["nodes"]} == {"Kunde", "Bestellung"}
    assert "@startuml" in (out / "shop" / "klassendiagramm.puml").read_text()
    assert "2 Klassen" in capsys.readouterr().out


def test_intellij_mode_sees_method_bodies(repo, capsys):
    assert main([str(repo), "--stdout", "puml", "-m", "intellij"]) == 0
    puml = capsys.readouterr().out
    assert "Bestellung ..> Kunde : <<create>>" in puml
    assert 'Kunde "1" *-- "*" Bestellung : bestellungen' in puml


def test_class_selection_needs_intellij_mode(repo, tmp_path):
    classes = tmp_path / "klassen.txt"
    classes.write_text("de.shop.Kunde\n")
    assert main([str(repo), "--classes", str(classes)]) == 2


def test_name_option_renames_output(repo, tmp_path):
    out = tmp_path / "out"
    assert main([str(repo), "-o", str(out), "--name", "laden", "-f", "json"]) == 0
    assert (out / "laden" / "klassendiagramm.json").exists()
    assert not (out / "laden" / "klassendiagramm.puml").exists()


def test_missing_path_fails(tmp_path):
    assert main([str(tmp_path / "gibt-es-nicht"), "-o", str(tmp_path / "out")]) == 1


@pytest.mark.parametrize("text, url, name", [
    ("https://github.com/a/b.git", True, "b"),
    ("git@github.com:a/b.git", True, "b"),
    ("github.com/a/b", True, "b"),
    ("projekte/b", False, "b"),
])
def test_url_detection(text, url, name):
    assert is_url(text) is url
    assert repo_name(text) == name
