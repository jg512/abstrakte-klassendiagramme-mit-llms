**Deutsch** · [English](README.en.md)

# Java-Parser als eigenes Werkzeug (November 2026)

`javauml` ist ein kleines Programm, das für ein beliebiges Java-Projekt ein
vollständiges Klassendiagramm zeichnet, ohne LLM. Man gibt ihm den Ordner eines
Projekts oder dessen Adresse auf GitHub und bekommt das Diagramm als Text und,
wenn gewünscht, als Bild. Es ist der Parser aus der LLM-Pipeline, herausgelöst
als eigenes Werkzeug. Was ein Klassendiagramm, ein Parser oder PlantUML ist,
erklärt das [Haupt-README](../README.md#begriffe).

Genauer: `javauml` macht aus einem Java-Repo ein Klassendiagramm als PlantUML und JSON,
auf Wunsch auch gleich als Bild im Format PNG oder SVG. Es liest nur den Quelltext. Das Projekt
muss also weder gebaut noch kompiliert werden, und fehlende Bibliotheken stören
nicht.

Der Parser ist derselbe wie in der LLM-Pipeline in
[Ordner 1](../1-llm-pipeline-abstrakte-klassendiagramme/README.md)
(`src/parsing/java/`). Dort ist er nur ein Teil der Pipeline und hängt an deren
Konfiguration, Cache und LLM-Abhängigkeiten. Hier steht er für sich und braucht
nur `tree-sitter` und `tree-sitter-java`.

## Installation

Die Befehle tippt man in ein Terminal, im Ordner `3-java-parser-klassendiagramme`.
Sie richten eine eigene Python-Umgebung (`.venv`) ein und installieren das
Werkzeug darin. Eine ausführlichere Anleitung, auch für Windows und Docker,
steht in [`INSTALLATION.md`](../INSTALLATION.md).

```bash
python3 -m venv .venv
.venv/bin/pip install -e .          # mit Tests: -e '.[dev]'
```

Danach gibt es den Befehl `.venv/bin/javauml`. Für PNG und SVG wird PlantUML
gebraucht, entweder als JAR-Datei (dann muss auch Java installiert sein) oder
als Befehl `plantuml`, den das Terminal findet (im `PATH`). Die JAR aus Ordner 2
reicht:

```bash
export PLANTUML_JAR=../2-java-extraktoren-benchmark-forschungsdaten/werkzeuge/plantuml-1.2025.4.jar
```

## Benutzung

```bash
# lokales Repo, schreibt uml-ausgabe/<repo>/klassendiagramm.json und .puml
javauml pfad/zum/repo

# direkt von GitHub, mit Bild
javauml https://github.com/nutzer/projekt.git -f json,puml,svg

# mehrere Repos in einen Ordner
javauml repo-a repo-b https://github.com/nutzer/repo-c -o diagramme

# nur PlantUML auf die Standardausgabe
javauml pfad/zum/repo --stdout puml > diagramm.puml
```

Git-URLs werden flach (nur der neueste Stand, ohne Geschichte) in ein
temporäres Verzeichnis kopiert (geklont) und danach gelöscht.
Mit `--keep-clone` bleibt der Klon unter `<ausgabe>/<repo>/quelle` liegen,
mit `--ref` lässt sich ein Branch oder Tag wählen. Der geklonte Code wird nur
gelesen und nie ausgeführt.

Aus einem eigenen Python-Programm heraus (als Bibliothek):

```python
from javauml import Options, extract

result = extract("pfad/zum/repo", Options(mode="intellij"))
print(result.plantuml())
graph = result.graph          # Knoten, Kanten, Fundstellen, Diagnosen
```

## Zwei Modi

Der Modus `literal` (wörtlich, der Standard) zeigt, was in den Deklarationen
steht: Klassen mit Attributen und Methoden, Vererbung (`extends`), Realisierung
(`implements`) und Felder, deren Typ eine Klasse des Projekts ist. Die Art der
Feldbeziehung (Assoziation, Aggregation, Komposition) und die Kardinalität (wie
viele Objekte am anderen Ende hängen) werden aus Typ, `final`, Initialisierung
und JPA-Annotationen (Angaben für Datenbanken wie `@OneToMany`) geschätzt. Externe Obertypen wie `JFrame` bleiben als Knoten
stehen, weil sie viel über die Rolle einer Klasse sagen.

Der Modus `intellij` bildet das Klassendiagramm der Programmierumgebung IntelliJ
IDEA nach. Dafür wird auch der Code innerhalb der Methoden gelesen. Jeder Verweis im Code wird eine Abhängigkeit,
auch über Aufrufketten wie `RaiseMeUp.getCurrentJob().getImpactenergy()`, wo die
Zielklasse `Job` gar nicht im Text steht. `new X()` wird `«create»`, Felder
bekommen "1" oder "*", innere Klassen eine eigene Kante. Mit `--classes DATEI`
(ein voll qualifizierter Name pro Zeile) wählt man wie in IntelliJ die Klassen
aus, die im Diagramm stehen. Ohne Auswahl kommen alle hinein, was bei großen
Projekten schnell unübersichtlich wird.

Die Regeln des IntelliJ-Modus stammen aus den neun IntelliJ-Diagrammen von
Zhang/Hebig und sind in Ordner 2 unter
[`doku/intellij-nachbildung.md`](../2-java-extraktoren-benchmark-forschungsdaten/doku/intellij-nachbildung.md)
beschrieben. Den Aufbau des Parsers beschreibt
[`doku/java-parser.md`](../1-llm-pipeline-abstrakte-klassendiagramme/doku/java-parser.md)
in Ordner 1.

## Optionen

| Option | Bedeutung |
| :--- | :--- |
| `-o`, `--output` | Ausgabeordner, Standard `uml-ausgabe` |
| `-f`, `--format` | Auswahl aus `json`, `puml`, `png`, `svg`, Standard `json,puml` |
| `--name` | Name in der Ausgabe statt Ordner- oder Repo-Name |
| `--stdout puml\|json` | Ergebnis ausgeben statt Dateien zu schreiben |
| `-m`, `--mode` | `literal` oder `intellij` |
| `--members` | wie viel in den Klassenkästen steht, im Modus `literal`: `structure`, `summary` (Standard), `public-api`, `full` |
| `--source-sets` | `auto` nimmt `src/main/java` bzw. die Verzeichnisse aus `pom.xml` und `build.gradle`, `all` alles |
| `--include-generated` | generierte Quellen mitlesen |
| `--exclude-dir`, `--exclude-file` | weitere Muster ausschließen |
| `--no-default-excludes` | Testordner, `target/`, `*Test.java` usw. doch lesen |
| `--no-external-supertypes` | externe Obertypen weglassen (`literal`) |
| `--method-dependencies` | Abhängigkeiten aus Methodensignaturen (`literal`) |
| `--javac`, `--classpath` | Typen zusätzlich über den JDK-Compiler auflösen (`literal`) |
| `--classes` | Klassenauswahl (`intellij`) |
| `--ide-no-jdk`, `--ide-no-same-package` | IntelliJ ohne JDK bzw. mit falschem Source-Root nachbilden (`intellij`) |
| `--ref`, `--keep-clone` | beim Klonen |
| `--plantuml` | PlantUML-JAR für PNG und SVG |
| `-v`, `--verbose` | Fortschritt und Hinweise ausgeben |

## Ausgabe

Pro Repo ein Ordner mit:

- `klassendiagramm.puml`: PlantUML-Text.
- `klassendiagramm.json`: der Graph mit Paketen, Knoten, Kanten und der
  Fundstelle jeder Kante (Datei, Zeile, Feld oder Methode). Das Format ist
  dasselbe wie `javagraph.json` in Ordner 1, die Pipeline kann es also direkt
  lesen.
- `klassendiagramm.diagnostics.json`: nur wenn es etwas zu melden gibt, etwa
  Dateien mit Syntaxfehlern, doppelte Klassen oder Typen, die sich nicht
  eindeutig auflösen ließen.
- `klassendiagramm.png` bzw. `.svg`, wenn angefordert.

Die Klassen-IDs sind um das gemeinsame Paketpräfix gekürzt. Aus
`de.firma.app.model.Kunde` wird `model.Kunde`.

## Wie gut der Parser ist

Gemessen wurde in Ordner 2, mit dem Code aus Ordner 1. Die Ergebnisse gelten
hier unverändert, siehe "Gleichheit mit Ordner 1" unten.

- Gegen von Menschen gezeichnete Diagramme (30 Lindholmen-Projekte und 9
  Projekte von Zhang/Hebig) liegt der Modus `literal` gleichauf mit javalang und
  vor den anderen getesteten Werkzeugen. Die Werkzeuge, die Bytecode lesen,
  liefen auf den meisten Projekten gar nicht, weil sie sich nicht kompilieren
  ließen.
- Gegen IntelliJ: Auf sieben der neun Projekte erzeugt der Modus `intellij`
  genau dasselbe Diagramm wie IntelliJ, keine Kante fehlt, keine ist zu viel.
  Bei Orekit und Neuroph stimmen alle Kanten, die sich im Bild prüfen ließen
  (28 von 35 bzw. 16 von 103). Dafür braucht es dieselbe Klassenauswahl und
  dieselbe Umgebung (JDK ja oder nein, Source-Root richtig oder falsch), mit der
  das jeweilige Projekt in IntelliJ geöffnet war.

## Grenzen

- Ohne Build gibt es keine Informationen aus Bibliotheken. Ein Rückgabetyp aus
  einer Bibliothek beendet eine Aufrufkette, außer bei den gängigen
  JDK-Collections.
- Überladene Methoden werden nur über die Zahl der Argumente unterschieden.
  Lambdas ohne Typangabe und schwer bestimmbare `var` beenden eine Aufrufkette.
- Mehrdeutige Typen werden weggelassen und gemeldet. Das kostet im Zweifel eine
  richtige Kante, vermeidet aber falsche.
- Der Modus `literal` sieht nur Deklarationen. Dass eine Klasse eine andere
  erzeugt oder aufruft, zeigt nur der Modus `intellij`.
- Ob ein Feld in UML eine Komposition, Aggregation oder Assoziation ist, steht
  so nicht im Code. Der Modus `literal` schätzt es.

## Tests

Tests sind kleine Prüfprogramme, die automatisch kontrollieren, ob der Parser
noch das Erwartete liefert.

```bash
.venv/bin/python -m pytest
```

| Datei | Prüft |
| :--- | :--- |
| `tests/test_java_parsing.py` | Syntaxbaum, Felder und Kardinalitäten, Encodings, Präfix, Module, wörtlicher Graph, javac, Dateiauswahl |
| `tests/test_java_resolution.py` | Auflösung von Typnamen: Imports, verschachtelte und geerbte Typen, Mehrdeutigkeit |
| `tests/test_java_intellij.py` | IntelliJ-Modus: Aufrufketten, Schleifen, Felder mit "1" und "*", Umgebungen |
| `tests/test_java_literal_benchmark.py` | die 20 kleinen Projekte aus [`benchmarks/java_literal/`](benchmarks/java_literal/README.md) mit von Hand geprüftem Graphen |
| `tests/test_cli.py` | Kommandozeile, Ausgabedateien, URL-Erkennung |

Die ersten vier stammen aus Ordner 1 und prüfen dort dasselbe.

## Aufbau

| Pfad | Inhalt |
| :--- | :--- |
| `javauml/cli.py` | Kommandozeile |
| `javauml/api.py` | `extract` und `Options`, setzt die Schritte zusammen |
| `javauml/repo.py` | lokaler Pfad oder Git-URL |
| `javauml/sources.py` | welche `.java`-Dateien gelesen werden |
| `javauml/java/ts_pass.py` | Syntaxbaum mit tree-sitter, Klassen, Felder, Methoden |
| `javauml/java/resolution.py` | Typnamen auf Klassen im Projekt abbilden |
| `javauml/java/graph_builder.py` | Modus `literal` |
| `javauml/java/intellij.py` | Modus `intellij` |
| `javauml/java/javac_solver.py` | Ergänzung über den JDK-Compiler |
| `javauml/java/import_graph.py` | Paketabhängigkeiten, nur für die Tests aus Ordner 1 |
| `javauml/model.py` | Datenklassen für Klassen und Felder |
| `javauml/schema/` | Graph-Modell, JSON, PlantUML |
| `javauml/render.py` | PNG und SVG über PlantUML |
| `benchmarks/java_literal/` | kleine Testprojekte mit erwartetem Graphen |
