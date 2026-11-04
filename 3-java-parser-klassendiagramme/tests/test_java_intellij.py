"""Tests für den IntelliJ-Modus des Java-Extraktors.

Jede Regel stammt aus einem der Diagramme, die IntelliJ für die Projekte von
Zhang/Hebig erzeugt hat. Die Testprojekte sind klein nachgebaut.
"""
from __future__ import annotations

import pytest

pytest.importorskip("tree_sitter_java", reason="Java support is an optional extra")

from javauml.java.intellij import IdeEnvironment, build_intellij_graph  # noqa: E402
from javauml.schema.plantuml import check_plantuml, to_plantuml  # noqa: E402


def write(root, rel_path: str, body: str):
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def edges(root, diagram=None, env=None):
    graph = build_intellij_graph(sorted(root.rglob("*.java")), root, root.name, env, diagram)
    names = {n.id: n.name for n in graph.nodes}
    result = set()
    for e in graph.edges:
        label = e.label if e.type in {"composition", "dependency"} else None
        card = e.target_card if e.type == "composition" else None
        result.add((e.type, names[e.source], names[e.target], label, card))
    return result, graph


@pytest.fixture
def game(tmp_path):
    """Nachbau des Musters aus RaiseMeUp mit Controller, Observer und Beans."""
    write(tmp_path, "src/game/control/Game.java", """
package game.control;
import game.model.Pet;
import game.model.Job;
public class Game {
    private static Pet currentPet;
    private static Job currentJob;
    public static Pet getCurrentPet() { return currentPet; }
    public static Job getCurrentJob() { return currentJob; }
}
""")
    write(tmp_path, "src/game/model/Pet.java", """
package game.model;
public class Pet {
    private int hunger;
    public int getHunger() { return hunger; }
}
""")
    write(tmp_path, "src/game/model/Job.java", """
package game.model;
public class Job {
    private int reward;
    public int getReward() { return reward; }
}
""")
    write(tmp_path, "src/game/model/PetObserver.java", """
package game.model;
import game.control.Game;
public class PetObserver {
    private int prevHunger;
    private int prevReward;
    public PetObserver() {
        prevHunger = Game.getCurrentPet().getHunger();
        prevReward = Game.getCurrentJob().getReward();
    }
}
""")
    write(tmp_path, "src/game/model/PetBuilder.java", """
package game.model;
public class PetBuilder {
    private String name;
    public PetBuilder setName(String n) { this.name = n; return this; }
    public Pet createPet() { return new Pet(); }
}
""")
    return tmp_path


def test_call_chain_reaches_class_never_named(game):
    """`PetObserver` erwähnt `Job` nicht, ruft aber `Game.getCurrentJob().getReward()` auf."""
    result, _ = edges(game)
    assert ("dependency", "PetObserver", "Job", None, None) in result
    assert ("dependency", "PetObserver", "Pet", None, None) in result
    assert ("dependency", "PetObserver", "Game", None, None) in result


def test_reading_own_fields_is_no_self_dependency(game):
    """`PetObserver` schreibt nur eigene Felder. Dafür zeichnet IntelliJ keine Schleife."""
    result, _ = edges(game)
    assert ("dependency", "PetObserver", "PetObserver", None, None) not in result


def test_own_type_in_signature_is_self_dependency(game):
    """Setter, die `PetBuilder` zurückgeben, ergeben eine Schleife an `PetBuilder`."""
    result, _ = edges(game)
    assert ("dependency", "PetBuilder", "PetBuilder", None, None) in result


def test_new_is_create_dependency(game):
    result, _ = edges(game)
    assert ("dependency", "PetBuilder", "Pet", "«create»", None) in result


def test_static_field_is_composition_with_role(game):
    result, _ = edges(game)
    assert ("composition", "Game", "Pet", "currentPet", "1") in result
    assert ("composition", "Game", "Job", "currentJob", "1") in result


def test_dependency_hidden_when_field_relation_exists(game):
    """`Game` benutzt `Pet` auch in einer Signatur, gezeichnet wird nur das Feld."""
    result, _ = edges(game)
    assert ("dependency", "Game", "Pet", None, None) not in result


def test_diagram_selection_limits_nodes_and_edges(game):
    result, graph = edges(game, diagram=["game.model.PetObserver", "game.model.Job"])
    assert {n.name for n in graph.nodes} == {"PetObserver", "Job"}
    assert result == {("dependency", "PetObserver", "Job", None, None)}


@pytest.fixture
def social(tmp_path):
    """Nachbau von PatrickFromTheMOOC."""
    write(tmp_path, "avis/Member.java", """
package avis;
import java.util.LinkedList;
public class Member {
    private LinkedList<Review> reviews;
    private String pseudo;
    public void addReview(Review r) { reviews.add(r); }
    public boolean is(String p) { return this.hasPseudo(p); }
    private boolean hasPseudo(String p) { return pseudo.equals(p); }
}
""")
    write(tmp_path, "avis/Review.java", """
package avis;
public class Review {
    private Member member;
    public Review(Member member) { this.member = member; }
    public boolean memberIs(Member m) { return this.member.equals(m); }
    public boolean equals(Object o) { return o instanceof Review && ((Review) o).member == member; }
}
""")
    write(tmp_path, "avis/EvaluationReview.java", """
package avis;
public class EvaluationReview {
    private Member member;
    private float note;
    public float getNote() { return note; }
    public void modify(float n) { this.note = n; }
}
""")
    return tmp_path


def test_collection_field_without_jdk_is_only_dependency(social):
    """Ohne JDK kennt IntelliJ `LinkedList` nicht: keine Linie mit "*", nur eine Abhängigkeit."""
    result, _ = edges(social, env=IdeEnvironment(jdk=False))
    assert not any(e[0] == "composition" and e[1] == "Member" for e in result)
    assert ("dependency", "Member", "Review", None, None) in result


def test_collection_field_with_jdk_is_many(social):
    result, _ = edges(social, env=IdeEnvironment(jdk=True))
    assert ("composition", "Member", "Review", "reviews", "*") in result
    assert ("dependency", "Member", "Review", None, None) not in result


def test_self_dependency_rules(social):
    result, _ = edges(social)
    assert ("dependency", "Review", "Review", None, None) in result          # Cast und instanceof
    assert ("dependency", "Member", "Member", None, None) in result          # eigener Methodenaufruf
    assert ("dependency", "EvaluationReview", "EvaluationReview", None, None) not in result


def test_map_field_is_not_many(tmp_path):
    write(tmp_path, "p/Item.java", "package p; public class Item {}")
    write(tmp_path, "p/Pet.java", """
package p;
import java.util.Map;
public class Pet { private Map<Item, Integer> items; private Item[] slots; }
""")
    result, _ = edges(tmp_path)
    assert ("composition", "Pet", "Item", "items", "*") not in result
    assert ("composition", "Pet", "Item", "slots", "*") in result
    assert ("dependency", "Pet", "Item", None, None) not in result


def test_create_stays_next_to_field_relation(tmp_path):
    """In ZooTypers hat `SinglePlayer` ein Feld `model` und erzeugt es auch: beides wird gezeichnet."""
    write(tmp_path, "z/Model.java", "package z; public class Model {}")
    write(tmp_path, "z/Player.java", """
package z;
public class Player { private Model model; public void start() { model = new Model(); } }
""")
    result, _ = edges(tmp_path)
    assert ("composition", "Player", "Model", "model", "1") in result
    assert ("dependency", "Player", "Model", "«create»", None) in result


def test_inner_class_and_class_literal(tmp_path):
    write(tmp_path, "z/Title.java", "package z; public class Title {}")
    write(tmp_path, "z/Player.java", """
package z;
public class Player {
    private Timer timer;
    void go() { Object o = Title.class; timer = new Timer(); show(); }
    void show() {}
    public class Timer { void tick() { show(); } }
}
""")
    result, _ = edges(tmp_path)
    assert ("nesting", "Player", "Timer", None, None) in result
    assert ("dependency", "Player", "Title", None, None) in result
    assert ("dependency", "Player", "Timer", "«create»", None) in result
    # Die innere Klasse ruft eine Methode der äußeren auf. IntelliJ zeigt das nicht extra.
    assert ("dependency", "Timer", "Player", None, None) not in result


def test_supertype_through_hidden_interface(tmp_path):
    """Orekit: Realisierung zum nächsten gezeigten Obertyp, über ein nicht gezeigtes Interface hinweg."""
    write(tmp_path, "o/Provider.java", "package o; public interface Provider {}")
    write(tmp_path, "o/Interpolator.java", "package o; public interface Interpolator extends Provider {}")
    write(tmp_path, "o/Adapted.java", "package o; public class Adapted implements Interpolator {}")
    result, _ = edges(tmp_path, diagram=["o.Provider", "o.Adapted"])
    assert ("realization", "Adapted", "Provider", None, None) in result


def test_wrong_source_root_hides_same_package_only(tmp_path):
    """Artemis: Klassen aus demselben Paket ohne import fehlen, importierte bleiben."""
    write(tmp_path, "a/core/Repo.java", "package a.core; public class Repo {}")
    write(tmp_path, "a/core/Service.java", "package a.core; public class Service { private Repo repo; }")
    write(tmp_path, "a/web/Resource.java", """
package a.web;
import a.core.Service;
public class Resource { private Service service; }
""")
    result, _ = edges(tmp_path, env=IdeEnvironment(same_package=False))
    assert ("composition", "Resource", "Service", "service", "1") in result
    assert not any(e[1] == "Service" and e[2] == "Repo" for e in result)
    normal, _ = edges(tmp_path)
    assert ("composition", "Service", "Repo", "repo", "1") in normal


def test_plantuml_output_is_valid(game):
    _, graph = edges(game)
    puml = to_plantuml(graph)
    assert check_plantuml(puml) == []
    assert "<<create>>" in puml
