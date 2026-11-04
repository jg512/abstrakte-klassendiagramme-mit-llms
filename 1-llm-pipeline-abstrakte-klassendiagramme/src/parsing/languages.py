from __future__ import annotations

from dataclasses import dataclass


class UnknownLanguageError(ValueError):
    pass


@dataclass(frozen=True)
class LanguageSpec:
    """Alles, was die Pipeline über eine Quellsprache wissen muss.

    Enthält nur, was sich zwischen den Sprachen unterscheidet und wonach die
    sprachneutralen Schritte (Dateien sammeln, Preflight, Benennung der Läufe)
    verzweigen müssen. Das Parsen selbst wird in
    code_graph.build_code_graph verteilt.
    """
    name: str
    extensions: tuple[str, ...]
    # Dateiname des statischen Klassengraphen, der pro Repo geschrieben wird
    # (pyreverse.json / javagraph.json). catalog und prune lesen diesen Graphen.
    static_graph_basename: str = "static_graph"


# Die Ausschlüsse stehen in configs/default.yaml. Dort sind alle Filter an
# einer Stelle, man sieht sie und kann sie ändern. Eine eigene Config erbt sie,
# solange sie `filters` nicht ganz überschreibt. Stünden sie fest im Code,
# würde sich unbemerkt ändern, was ein leeres FiltersConfig bedeutet.
PYTHON = LanguageSpec(
    name="python",
    extensions=(".py",),
    static_graph_basename="pyreverse",
)

JAVA = LanguageSpec(
    name="java",
    extensions=(".java",),
    static_graph_basename="javagraph",
)

LANGUAGES: dict[str, LanguageSpec] = {PYTHON.name: PYTHON, JAVA.name: JAVA}

DEFAULT_LANGUAGE = PYTHON.name


def resolve_language(name: str | None) -> LanguageSpec:
    """LanguageSpec über den Namen suchen, ohne auf Groß- und Kleinschreibung zu achten."""
    key = (name or DEFAULT_LANGUAGE).strip().lower()
    if key not in LANGUAGES:
        raise UnknownLanguageError(
            f"Unknown language {name!r}; expected one of {', '.join(sorted(LANGUAGES))}"
        )
    return LANGUAGES[key]
