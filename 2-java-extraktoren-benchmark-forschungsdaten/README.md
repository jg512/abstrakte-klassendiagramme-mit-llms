**Deutsch** · [English](README.en.md)

# Benchmark der Java-Extraktoren auf Forschungsdaten (September/Oktober 2026)

Ein Extraktor ist hier ein Werkzeug, das aus Java-Code automatisch ein
Klassendiagramm erzeugt. In diesem Ordner werden sieben solche Werkzeuge,
darunter der eigene Parser des Projekts, an echten Projekten verglichen, zu
denen Menschen Klassendiagramme gezeichnet haben. Wer die Grundbegriffe
(Klassendiagramm, Parser, Benchmark, Ground Truth, Precision, Recall, F1) noch
nicht kennt, findet sie im [Haupt-README](../README.md#begriffe) erklärt.

Warum dieser Vergleich nötig ist: Mit einer Ground Truth aus dem Bytecode lässt
sich prüfen, ob ein Parser den Code richtig liest. Für das Projekt ist aber
wichtiger, wie gut ein Klassengraph zu einem Diagramm passt, das ein Mensch
gezeichnet hat. Dafür braucht man öffentliche Java-Projekte, zu denen es
passende UML-Diagramme gibt. Dieser Ordner enthält die Suche nach solchen
Daten, die Daten selbst und die Messungen. Später sollen dieselben Daten zeigen,
wie gut das LLM aus Ordner 1 abstrahiert.

## Fragestellung

1. Gibt es einen Forschungsdatensatz mit Java-Projekten und passenden
   Klassendiagrammen, der mindestens 20 brauchbare Paare enthält?
2. Wie schneidet der eigene Extraktor (Ordner 1, `src/parsing/java/`) auf diesen
   Daten im Vergleich zu anderen Werkzeugen ab?
3. Welche Fehler im eigenen Extraktor fallen dabei auf, und lassen sie sich
   beheben und mit Tests absichern?

## Ergebnisse

- Daten: Verwendet werden 30 Projekte aus dem Lindholmen-Datensatz, einer
  Sammlung von GitHub-Projekten, die UML-Dateien enthalten (zusammen 4.040
  Java-Dateien, Quelltext und Modell jeweils aus demselben Commit). Dazu kommen
  die neun Projekte aus der Studie von Zhang/Hebig (2025), deren Diagramme von
  Hand abstrahiert wurden. "Modell" heißt hier das gezeichnete Diagramm in
  maschinenlesbarer Form. Mehr dazu in
  [`doku/recherche-datensätze.md`](doku/recherche-datensätze.md).
- Auf den 30 Lindholmen-Projekten liegen der eigene Extraktor und javalang
  gleichauf (Micro-F1 0,646), java2plantuml (mirajp1) erreicht 0,577. Alle drei
  liefen auf allen 30 Projekten. Micro-F1 ist der F1-Wert über alle Linien
  aller Projekte zusammen. Dass der eigene Extraktor und javalang genau
  dieselben Werte haben, ist zu erwarten: javalang ist nur ein Parser, und der
  Adapter, der daraus einen Klassengraphen macht, wurde in diesem Projekt
  geschrieben und wertet dieselben Deklarationen aus. Der eigene Extraktor
  unterscheidet sich dort, wo diese Projekte ihn nicht fordern: neueres Java,
  alte Encodings, Fundstellen und der IntelliJ-Modus. Mit "Java2PlantUML" (groß
  geschrieben) ist in diesem Ordner ein anderes Werkzeug gemeint, das von
  juanmf stammt und Bytecode liest.
- Auf den Zhang/Hebig-Projekten wurden sieben Extraktoren verglichen. Die drei
  Werkzeuge, die Quelltext lesen, laufen auf allen neun Projekten (eigener
  Extraktor und javalang F1 0,711, java2plantuml 0,656). Die Bytecode-Werkzeuge
  laufen auf höchstens drei Projekten, weil sich nur drei überhaupt kompilieren
  lassen. Auch auf diesen drei liegen sie mit F1 zwischen 0,41 und 0,53 unter
  den Quelltext-Werkzeugen (0,63 bis 0,71). genuml gibt gar keine Beziehungen
  aus.
- Im eigenen Extraktor wurden mehrere Fehler gefunden und behoben (Imports,
  Stern-Importe, geerbte verschachtelte Typen, Enum-Rümpfe, generische
  Wrapper-Klassen, Selbstassoziationen). Danach kamen weitere Funktionen dazu:
  Erkennung der Maven/Gradle-Struktur, Fundstellen pro Kante, Kardinalitäten und
  ein optionaler javac-Modus.
- Im Oktober kam ein zweiter Modus dazu, der die Klassendiagramme von IntelliJ
  nachbildet, einschließlich der Abhängigkeiten aus Methodenrümpfen und über
  Aufrufketten. Auf sieben der neun Projekte stimmt er vollständig mit dem
  IntelliJ-Diagramm überein, auf den anderen beiden in allen Kanten, die sich im
  Bild prüfen ließen. Mehr dazu in
  [`doku/intellij-nachbildung.md`](doku/intellij-nachbildung.md).
- Die Werte messen nur, wie gut die Ausgabe zu den Diagrammen passt. Ob der
  Code richtig gelesen wurde, zeigen sie nicht. In den Fallstudien stellte sich
  heraus, dass manche Referenzdiagramme einen Entwurf beschreiben, der im Code
  anders umgesetzt wurde.

## Aufbau

```
README.md
doku/                     Berichte zu Recherche, Ergebnissen und Fallstudien
skripte/                  alle Python-Skripte und ihre Tests
daten/
  lindholmen/             die 30 Lindholmen-Projekte und alles zu ihrer Auswahl
  zhang-hebig/            Replikationspaket von Zhang/Hebig mit Abschrift der Diagramme
  intellij/               Klassenauswahl und aus den IntelliJ-Bildern abgelesene Kanten
  recherche/              Material zu anderen Datensätzen und Werkzeugen
ergebnisse/
  messungen/              alle Messläufe als JSON und CSV
  diagramme/              gerenderte Diagramme pro Zhang/Hebig-Projekt, Referenz und alle Werkzeuge
  diagramme-intellij/     IntelliJ-Bild neben der Ausgabe des IntelliJ-Modus
  pipeline-trockenlauf/   Lauf der Pipeline mit allen acht Varianten, ohne LLM
  protokolle/             Logs der Läufe und Tests
werkzeuge/                gebaute Fremdwerkzeuge, Messumgebung, Python-Abhängigkeiten
```

Die Skripte werden aus diesem Ordner heraus aufgerufen, zum Beispiel
`.venv/bin/python skripte/intellij_abgleich.py`. Die genauen Befehle stehen in
[`doku/reproduzieren.md`](doku/reproduzieren.md). `daten/` und `ergebnisse/`
sind größtenteils zu groß für GitHub. Im Repository liegen nur die eigenen
Metadaten (Auswahl, Prüfsummen, Abschriften, Referenzen), alles andere liegt im
vollständigen Projektordner oder lässt sich nach
[`INSTALLATION.md`](../INSTALLATION.md) neu laden.

## Dokumente

Eine sinnvolle Lesereihenfolge ist: Recherche, dann die beiden
Ergebnisberichte, dann die Fallstudien und die IntelliJ-Nachbildung. Werkzeuge
und Reproduktion braucht man nur zum Nachmessen.

| Datei | Inhalt |
| :--- | :--- |
| [`doku/recherche-datensätze.md`](doku/recherche-datensätze.md) | verfügbare Datensätze, Auswahl und Begründung, Regeln der Auswertung |
| [`doku/ergebnisse-lindholmen.md`](doku/ergebnisse-lindholmen.md) | 30 Projekte und die Zhang/Hebig-Suite mit drei Extraktoren, behobene Fehler, Tabelle pro Projekt |
| [`doku/ergebnisse-zhang-hebig.md`](doku/ergebnisse-zhang-hebig.md) | alle sieben Extraktoren auf der Zhang/Hebig-Suite, warum die Bytecode-Werkzeuge ausfielen |
| [`doku/fallstudien.md`](doku/fallstudien.md) | RaiseMeUp, NeurophChanges und PatrickFromTheMOOC im Detail |
| [`doku/intellij-nachbildung.md`](doku/intellij-nachbildung.md) | Regeln von IntelliJ, Umgebung pro Projekt, Abgleich mit den IntelliJ-Diagrammen |
| [`doku/werkzeuge.md`](doku/werkzeuge.md) | Herkunft, Versionen, Prüfsummen und Bau der Werkzeuge |
| [`doku/reproduzieren.md`](doku/reproduzieren.md) | Befehle zum Nachstellen der Messungen |
| [`daten/zhang-hebig/README.md`](daten/zhang-hebig/README.md) | Replikationspaket von Zhang/Hebig |
| [`ergebnisse/diagramme/README.md`](ergebnisse/diagramme/README.md) | Erklärung der gezeichneten Diagramme (nur im vollständigen Projektordner) |

## Skripte

| Datei | Aufgabe |
| :--- | :--- |
| `skripte/discover.py`, `skripte/acquire.py` | Auswahl und Download der Lindholmen-Teilmenge |
| `skripte/restore.py` | prüft die Eingaben anhand von Prüfsummen und lädt Fehlendes nach |
| `skripte/benchmark.py` | Messung auf den 30 Lindholmen-Projekten (drei Extraktoren) |
| `skripte/curated_hebig_benchmark.py` | dasselbe für die Zhang/Hebig-Projekte |
| `skripte/curated_tools_benchmark.py` | alle sieben Extraktoren auf den Zhang/Hebig-Projekten, mit Kompilieren und Rendern |
| `skripte/intellij_abgleich.py` | IntelliJ-Modus des eigenen Extraktors gegen die IntelliJ-Diagramme |
| `skripte/report.py` | erzeugt Tabellen und Referenzgraphen neu aus den gespeicherten Läufen |
| `skripte/test_benchmark.py`, `skripte/test_curated_hebig.py` | Tests für Normalisierung und Referenzdaten |

## Daten im Einzelnen

| Pfad | Inhalt |
| :--- | :--- |
| `daten/lindholmen/manifest.json` | die 30 festgelegten Paare aus Projekt, Commit, Modell und Quelldateien |
| `daten/lindholmen/corpus/` | heruntergeladene Projekte, Quelltext und Modell |
| `daten/lindholmen/reference-graphs/` | normalisierte Referenzgraphen pro Projekt (JSON und PlantUML) |
| `daten/lindholmen/model-probes/` | 850 UML-Modelle, die bei der Auswahl geprüft wurden |
| `daten/lindholmen/discovery.json`, `acquisition.json`, `eligible-manifest.json`, `preparation-exclusions.json` | Zwischenstände und Ausschlüsse der Auswahl |
| `daten/lindholmen/UMLFiles_List_V2.0.csv`, `Project_FileTypes_V2.0.csv`, `lindholmen.html` | Indizes des Lindholmen-Datensatzes und Seite des Spiegelservers |
| `daten/lindholmen/syntax-audit.json` | Syntaxprüfung der Eingaben |
| `daten/intellij/projekte.json` | pro Projekt die Klassen im IntelliJ-Diagramm und wie das Projekt in IntelliJ geöffnet war |
| `daten/intellij/referenz/` | die aus den IntelliJ-Bildern abgelesenen Kanten |
| `daten/recherche/` | `siala-*.json`, `palladio-tree.json`, `java2plantuml-repo.json` aus der Suche nach Datensätzen und Werkzeugen |
| `ergebnisse/messungen/reproduction-verification.json` | Abgleich der Wiederholungsläufe |
| `werkzeuge/TOOLS.json`, `werkzeuge/requirements.lock.txt` | Messumgebung und Python-Abhängigkeiten |

Die Pfade in den JSON-Dateien unter `daten/lindholmen/` sind relativ zu diesem
Unterordner, die in `daten/intellij/projekte.json` relativ zu `daten/`.

Heruntergeladener Projektcode wurde nie ausgeführt.
