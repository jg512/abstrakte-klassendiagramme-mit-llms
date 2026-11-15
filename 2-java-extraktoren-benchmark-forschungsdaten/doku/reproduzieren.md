**Deutsch** · [English](reproduzieren.en.md)

# Messungen wiederholen

Diese Datei listet die Befehle, mit denen man die Messungen aus Ordner 2 auf
dem eigenen Rechner wiederholen kann. Die Befehle tippt man in ein Terminal.
Wie man den Rechner dafür vorbereitet, steht ausführlicher und auch für
Windows und Docker in [`INSTALLATION.md`](../../INSTALLATION.md). Fachbegriffe
erklärt das [Haupt-README](../../README.md#begriffe).

Grundlage ist die festgelegte Projektliste in `daten/lindholmen/manifest.json`.
Die Auswahl der Projekte sollte für eine Wiederholung nicht neu ausgeführt
werden, weil sich Branches und Inhalte der Repos seitdem geändert haben können.

Alle Befehle werden in diesem Ordner
(`2-java-extraktoren-benchmark-forschungsdaten/`) ausgeführt. Die Pipeline mit
dem eigenen Extraktor liegt in `../1-llm-pipeline-abstrakte-klassendiagramme`.

## Umgebung

Benötigt werden Python 3.13, ein JDK, `git` (lädt Repos herunter), `curl` (lädt
Dateien herunter) und `uv` (richtet Python-Umgebungen ein). Die Versionen der
Messumgebung und die Prüfsummen der Werkzeuge stehen in `werkzeuge/TOOLS.json`.
Eine Prüfsumme (hier SHA-256) ist eine Art Fingerabdruck einer Datei. Stimmt
sie, ist die Datei unverändert.

```bash
uv venv .venv --python 3.13
uv pip install --python .venv/bin/python -r werkzeuge/requirements.lock.txt
uv pip install --python .venv/bin/python --no-deps -e ../1-llm-pipeline-abstrakte-klassendiagramme
```

java2plantuml (mirajp1) liegt im vollständigen Projektordner bereits kompiliert
unter `werkzeuge/`, im GitHub-Repository nicht. So lässt es sich
neu bauen:

```bash
git clone https://github.com/mirajp1/java2plantuml.git werkzeuge/java2plantuml
git -C werkzeuge/java2plantuml checkout cadd0f0a06e87825472227381a37210763ae137c
curl -fL https://repo.maven.apache.org/maven2/com/github/javaparser/javaparser-core/3.4.0/javaparser-core-3.4.0.jar -o werkzeuge/javaparser-core-3.4.0.jar
mkdir -p werkzeuge/java2plantuml/classes
javac -cp werkzeuge/javaparser-core-3.4.0.jar -d werkzeuge/java2plantuml/classes \
  werkzeuge/java2plantuml/src/main/java/*.java werkzeuge/java2plantuml/src/main/java/source/*.java \
  werkzeuge/java2plantuml/src/main/java/translate/*.java werkzeuge/java2plantuml/src/main/java/visitors/*.java
```

Das Werkzeug wird dabei unverändert gegen JavaParser 3.4.0 kompiliert, der
veraltete Gradle-Wrapper wird nicht benötigt. Die Build-Skripte der untersuchten
Projekte sollten nicht ausgeführt werden.

Die vier übrigen Werkzeuge für die Messung mit sieben Werkzeugen sind in
[`werkzeuge.md`](werkzeuge.md) beschrieben.

## Lindholmen (30 Projekte)

```bash
.venv/bin/python skripte/restore.py                     # prüft die Eingaben, lädt Fehlendes nach
.venv/bin/python -m pytest -q skripte/test_benchmark.py
.venv/bin/python skripte/benchmark.py --label rerun --limit 30
```

Vor der Extraktion wird jede Java-Datei anhand ihrer SHA-256-Prüfsumme geprüft.
`restore.py` prüft auch die Modelle und beim Nachladen die Prüfsumme des
Archivs. Die Ergebnisse (Rohausgaben, JSON pro Projekt, CSV und Gesamtergebnis)
werden in `ergebnisse/messungen/rerun/` gespeichert. Jeder Adapter hat ein
Zeitlimit von 120 Sekunden, der Java-Prozess von 90 Sekunden. Das Skript setzt
diese Zeitlimits über POSIX-Signale, eine Funktion von Unix-Systemen, und läuft
daher nur unter Linux, macOS oder WSL (Linux unter Windows).

## Zhang/Hebig (9 Projekte)

Das Replikationspaket liegt unter `daten/zhang-hebig/`. Die Prüfsumme des
Quellarchivs ist
`11db4e9a45affaf80df627fa6604119e0c56b47aef66e0e1ceae58086a13f85e`. Die
Abschrift der Diagramme und die Prüfsummen der Quelldateien stehen in
`daten/zhang-hebig/reference.json` und `daten/zhang-hebig/manifest.json`.

```bash
.venv/bin/python -m pytest -q skripte/test_benchmark.py skripte/test_curated_hebig.py
PYTHONPATH=../1-llm-pipeline-abstrakte-klassendiagramme \
  .venv/bin/python skripte/curated_hebig_benchmark.py --label curated-rerun
```

Alle drei Extraktoren bekommen dieselben 72 Java-Dateien. Die Anzahl der
Beziehungen laut den Autoren (82, gerichtet) wird mit ausgegeben, bewertet
werden die 79 Beziehungen nach der Normalisierung.

Messung mit allen sieben Werkzeugen (die Werkzeuge aus `werkzeuge.md` müssen
vorhanden sein):

```bash
PYTHONPATH=../1-llm-pipeline-abstrakte-klassendiagramme \
  .venv/bin/python skripte/curated_tools_benchmark.py \
    --label curated-alltools \
    --workdir /tmp/java-uml-bytecode \
    --genuml /pfad/zum/genuml-venv/bin/genuml
```

Dabei wird jedes Projekt einmal mit `javac` kompiliert, alle sieben Werkzeuge
werden gemessen, die Ergebnisse landen in
`ergebnisse/messungen/curated-alltools/`, und jede Ausgabe wird als PlantUML und
PNG nach `ergebnisse/diagramme/` geschrieben.

## Auswahl der Projekte

`daten/lindholmen/Project_FileTypes_V2.0.csv` und
`daten/lindholmen/UMLFiles_List_V2.0.csv` sind die Lindholmen-Indizes vom
Spiegelserver der Uni Rostock (Link in
[`recherche-datensätze.md`](recherche-datensätze.md)).

```bash
.venv/bin/python skripte/discover.py --limit 1200
.venv/bin/python skripte/acquire.py --limit 220
.venv/bin/python skripte/benchmark.py --prepare
```

Diese Befehle wiederholen die Auswahl mit dem heutigen Stand der Repos.
`daten/lindholmen/eligible-manifest.json` enthält alle geeigneten Paare, davon
wurden die ersten 30 in `daten/lindholmen/manifest.json` übernommen, bevor ein
Extraktor gemessen wurde. Die ursprüngliche Auswahl ist in
`daten/lindholmen/discovery.json`, `daten/lindholmen/acquisition.json`,
`daten/lindholmen/preparation-exclusions.json` und den Logs in
`ergebnisse/protokolle/` dokumentiert.

## Vorher und nachher

`ergebnisse/messungen/before/` wurde vor den Korrekturen am Extraktor
aufgenommen, `ergebnisse/messungen/final/` danach. Die anderen Werkzeuge blieben
unverändert. `report.py` fasst die gespeicherten Ergebnisse zusammen
(`.venv/bin/python skripte/report.py`) und schreibt dabei eine kurze englische
`REPORT.md` nach `ergebnisse/messungen/`. Die ausführliche Auswertung steht in
[`ergebnisse-lindholmen.md`](ergebnisse-lindholmen.md).
`ergebnisse/messungen/verification/` enthält einen späteren vollständigen
Wiederholungslauf mit allen drei Werkzeugen.

## Pipeline prüfen

Die `.venv` aus diesem Ordner enthält Ordner 1 als editierbare Installation und
alle Abhängigkeiten, sie reicht also auch für die Pipeline:

```bash
cd ../1-llm-pipeline-abstrakte-klassendiagramme
../2-java-extraktoren-benchmark-forschungsdaten/.venv/bin/python -m pytest -q -m 'not network'
../2-java-extraktoren-benchmark-forschungsdaten/.venv/bin/python -m src ../2-java-extraktoren-benchmark-forschungsdaten/daten/lindholmen/corpus/jainebri__Super-Simple-Stocks/source \
  --language java --method all --dry-run --no-cleanup \
  --out ../2-java-extraktoren-benchmark-forschungsdaten/ergebnisse/pipeline-trockenlauf
```

Der Benchmark mit 20 kleinen Java-Fällen liegt in Ordner 3
([`benchmarks/java_literal/`](../../3-java-parser-klassendiagramme/benchmarks/java_literal/README.md),
Aufruf im README dort).

Der Trockenlauf verwendet statt eines LLM einen Platzhalter mit festen
Antworten. Er zeigt, dass Parser, Driver und Ausgabe bei allen acht Varianten
zusammenarbeiten, sagt aber nichts über die Qualität echter Diagramme aus. Die
Platzhalter erfindet bei den prune-Varianten zusätzliche Klassen, deshalb
meldet die Pipeline dort, dass das Diagramm zu viele Klassen hat. Das ist
erwartet.

Nur den aktuellen eigenen Extraktor auf denselben Eingaben messen:

```bash
PYTHONPATH=../1-llm-pipeline-abstrakte-klassendiagramme .venv/bin/python skripte/benchmark.py --label enhanced-rerun --limit 30 --tools ours
PYTHONPATH=../1-llm-pipeline-abstrakte-klassendiagramme .venv/bin/python skripte/curated_hebig_benchmark.py --label curated-enhanced-rerun --tools ours
```
