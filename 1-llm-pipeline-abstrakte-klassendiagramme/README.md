**Deutsch** · [English](README.en.md)

# LLM-Pipeline für abstrakte Klassendiagramme

Dieser Ordner enthält das eigentliche Programm des Projekts. Es liest ein
Softwareprojekt ein, lässt ein Sprachmodell (LLM) die wichtigen Klassen
auswählen und zeichnet daraus ein übersichtliches Klassendiagramm. Wer noch
nicht weiß, was Klassen, Klassendiagramme oder LLMs sind, liest zuerst das
[Haupt-README](../README.md). Dort sind alle Fachbegriffe unter
[Begriffe](../README.md#begriffe) erklärt.

Genauer: Die Pipeline liest ein Repository (Python oder Java) ein und lässt ein
Sprachmodell daraus ein abstraktes Klassendiagramm im Textformat PlantUML
erstellen. Das Diagramm soll nur die zentralen Klassen zeigen, also
Fachklassen (die Dinge, um die es in der Software geht, etwa Kunde oder
Bestellung), Klassen mit steuernder Rolle und wichtige Schnittstellen.
Hilfsklassen, reine Datenbehälter, Code aus Frameworks (vorgefertigten
Grundgerüsten, auf denen eine Software aufbaut) und Tests werden weggelassen.

Das Python-Paket heißt `abstract-uml`. Die Vorgeschichte des Projekts steht im
[Haupt-README](../README.md#verlauf-des-projekts).

## Stand

- Die Pipeline läuft für Python und Java vollständig durch.
- Alle Arbeitsweisen laufen über ein gemeinsames Steuerprogramm (den Driver) mit
  acht Varianten.
- Die letzten Läufe mit echtem LLM waren im Juli 2026 mit `deepseek-chat` auf den
  Python-Repos `schedule` und `loguru`.
- Der Java-Teil ist getestet und auf Forschungsdaten gemessen, lief aber bisher
  nur als Trockenlauf ohne LLM.
- Der Java-Parser kann zusätzlich Klassendiagramme wie IntelliJ erzeugen
  (IntelliJ-Modus, siehe unten).
- Alle Tests mit `pytest -m 'not network'` bestehen. Tests sind kleine
  Prüfprogramme, die automatisch kontrollieren, ob der Code noch das Erwartete
  tut. `not network` lässt die Tests aus, die Internet brauchen.

## Ablauf

```
Repo (Pfad, GitHub-URL oder Liste)
  -> Dateien sammeln, Vorprüfung der Größe (Preflight)
  -> statische Analyse: Klassen, Member, Importgraph, voller Klassengraph
  -> Driver: das LLM baut mit Tools einen Arbeitsgraphen
  -> Prüfung und Reparatur (Validator), optional Aufräumen durch das LLM (Cleanup)
  -> graph.json, diagram.puml, Protokoll (Trace) und Kennzahlen pro Lauf
```

"Member" sind die Attribute und Methoden einer Klasse. Der Arbeitsgraph ist das
Diagramm, an dem das LLM gerade arbeitet. Intern wird mit einem Graphen im
JSON-Format gearbeitet (`src/schema/`), das PlantUML wird erst am Schluss daraus
erzeugt.

### Statische Analyse

Die statische Analyse liest den Code, ohne ihn auszuführen. Für die beiden
Sprachen werden unterschiedliche Werkzeuge benutzt:

| | Python | Java |
| :--- | :--- | :--- |
| Dateien | `*.py` | `*.java` |
| Klassen und Member | `ast` (eingebauter Python-Parser) | `tree-sitter-java` |
| Abhängigkeiten | Importzeilen | aufgelöste Typverweise |
| voller Klassengraph | `pyreverse` (aus pylint) | eigener Parser |
| Datei pro Repo | `pyreverse.json/.puml` | `javagraph.json/.puml` |

Ab hier ist der Ablauf für beide Sprachen gleich, nur die Eingabedaten der
statischen Analyse unterscheiden sich.

### Java-Parser

Der Parser liegt in `src/parsing/java/`:

| Datei | Aufgabe |
| :--- | :--- |
| `ts_pass.py` | liest den Syntaxbaum (die zerlegte Struktur jeder Datei) und sammelt Typen, Felder, Methoden und Obertypen |
| `resolution.py` | findet heraus, welche Klasse mit einem Namen gemeint ist, über Pakete, Imports und verschachtelte Typen |
| `graph_builder.py` | baut daraus den vollständigen Klassengraphen |
| `import_graph.py` | Abhängigkeiten zwischen Paketen für die Gruppierung in Cluster |
| `javac_solver.py` | optionale Ergänzung über den Java-Compiler |
| `intellij.py` | Klassendiagramm nach den Regeln von IntelliJ (siehe unten) |

Wie die einzelnen Schritte zusammenspielen, steht ausführlich und mit einem
durchgerechneten Beispiel in [`doku/java-parser.md`](doku/java-parser.md).

Einige Entscheidungen beim Bau des Parsers:

- Der Parser liest nur Quelltext und keinen Bytecode. Projekte müssen also nicht
  kompilierbar sein. An diesem Punkt sind die Bytecode-Werkzeuge im Vergleich
  gescheitert (siehe [Ordner 2](../2-java-extraktoren-benchmark-forschungsdaten/README.md)).
- Das Encoding wird pro Datei bestimmt (UTF-8, dann CP1252, dann Latin-1). Ältere
  Java-Projekte sind oft nicht in UTF-8 gespeichert.
- Paketnamen werden relativ zum Repo angegeben, der gemeinsame Anfang wird
  entfernt (`de.firma.app.model` wird zu `model`).
- Externe Oberklassen und Interfaces, also solche aus fremden Bibliotheken,
  bleiben im Paket `external` erhalten, weil zum Beispiel die Vererbung von
  `JFrame` (der Klasse für Programmfenster) etwas über die Rolle einer Klasse
  aussagt. Felder mit externen Typen wie `String` (Text) oder `Timer` erzeugen
  dagegen keine Kante.
- Ist ein Typname mehrdeutig, weil mehrere Klassen so heißen könnten, wird er
  gemeldet und weggelassen.
- Zu jeder Beziehung wird die Fundstelle gespeichert (Feld oder Methode, Typ,
  Datei, Zeile). Mehrdeutigkeiten, doppelte Deklarationen und Dateien, die sich
  nicht fehlerfrei lesen ließen, stehen in `javagraph.diagnostics.json`.
- Einstellbar sind, wie viel von jeder Klasse gezeigt wird
  (`--java-member-profile structure|summary|public-api|full`), ob Abhängigkeiten
  aus Methodensignaturen dazukommen (`--java-method-dependencies`) und die
  Auflösung über javac (`--java-symbol-solver javac` mit `--java-classpath`).

Warum ein eigener Parser geschrieben wurde, steht im
[Haupt-README](../README.md#phase-3-wechsel-zu-java-und-auswahl-des-parsers-august-2026)
und in Ordner 2.

### IntelliJ-Modus

Mit `--java-relations intellij` (in der Konfiguration `java.relation_style:
intellij`) erzeugt der Parser das Klassendiagramm nach den Regeln der
Programmierumgebung IntelliJ IDEA (`src/parsing/java/intellij.py`). Dabei wird
auch der Inhalt der Methoden gelesen. Jeder Verweis im Code wird zur
Abhängigkeit. Methodenaufrufe zählen für die Klasse, in der die Methode
geschrieben steht, auch über Aufrufketten wie
`RaiseMeUp.getCurrentJob().getImpactenergy()`. `new` (das Erzeugen eines
Objekts) ergibt eine Abhängigkeit mit `«create»`, Felder werden zu Kompositionen
mit "1" oder "*", innere Klassen bekommen eine eigene Kante (`nesting`).
Vererbung und Realisierung laufen über Typen hinweg, die nicht im Diagramm
stehen.

| Option | Bedeutung |
| :--- | :--- |
| `--java-diagram-classes DATEI` | Klassen im Diagramm, ein voll qualifizierter Name (mit Paket, etwa `de.firma.Kunde`) pro Zeile. Ohne Datei alle |
| `--java-ide-no-jdk` | so tun, als sei in IntelliJ kein JDK eingerichtet gewesen |
| `--java-ide-no-same-package` | so tun, als habe IntelliJ Klassen aus demselben Paket nicht gefunden |

Die Regeln und der Abgleich mit den neun IntelliJ-Diagrammen von Zhang/Hebig
stehen in Ordner 2 unter
[`doku/intellij-nachbildung.md`](../2-java-extraktoren-benchmark-forschungsdaten/doku/intellij-nachbildung.md).

### Varianten

Alle Varianten nutzen dieselbe Schleife im Driver mit denselben Tools, Prompts,
Budgets und Abbruchregeln. Sie unterscheiden sich in drei Einstellungen:

- seed: Der Arbeitsgraph startet leer (additiv, das Modell trägt ein) oder mit
  dem vollständigen Klassengraphen, aus dem das Modell streicht (subtraktiv).
  Dieses "seed" (Ausgangsmaterial) hat nichts mit dem Zufalls-Seed der
  Wiederholungen zu tun.
- context: Was in der ersten Nachricht an das Modell steht, also eine
  Übersicht der Pakete, die Cluster des Importgraphen oder der vollständige
  Klassengraph.
- peek: Ob das Modell den Quelltext selbst lesen darf (Tools `read_file`,
  `search_code`).

| Variante | seed | context | peek | alter Name |
| :--- | :--- | :--- | :--- | :--- |
| `overview` | leer | Übersicht | nein | |
| `overview-peek` | leer | Übersicht | ja | `m2` |
| `cluster` | leer | Cluster | nein | |
| `cluster-peek` | leer | Cluster | ja | `m3` |
| `catalog` | leer | Klassengraph | nein | `m1a` |
| `catalog-peek` | leer | Klassengraph | ja | `m1b` |
| `prune` | voller Graph | Klassengraph | nein | `m4a` |
| `prune-peek` | voller Graph | Klassengraph | ja | `m4b` |

Bei den `cluster`-Varianten wird der Lauf zusätzlich pro Cluster aufgeteilt, die
Teildiagramme werden danach in einem eigenen Schritt (Synthese) zusammengeführt.
Die alten Namen `m1a` bis `m4b` stammen aus der ersten Version, in der jede
Methode ein eigenes Programm war. Sie funktionieren weiterhin als zweiter Name
(Alias).

Das Modell hat drei Tools: `inspect_class` (eine Klasse ansehen), `apply_edits`
(Klassen entfernen, Klassen und Linien hinzufügen, alles in einem Aufruf) und
`emit_diagram` (das fertige Diagramm abgeben). Bei den Peek-Varianten kommen
`read_file` und `search_code` dazu, die aber erst freigeschaltet werden, wenn
ein erster Entwurf existiert. Kurz vor Ende des Budgets bekommt das Modell den
Hinweis, den Lauf abzuschließen.

Mehrere dieser Regeln kamen durch Probleme in früheren Läufen (`runs/old/`)
dazu:

- Als Klassen und Linien noch über getrennte Tools angelegt wurden, war das
  Budget oft zwischen beiden Schritten aufgebraucht, und die Diagramme hatten
  keine Linien.
- Modelle mit Lesezugriff haben häufig nur gelesen und nie etwas angelegt. Eine
  Anweisung im Prompt hat das nicht verhindert, deshalb sind die Lesetools jetzt
  gesperrt, solange das Diagramm leer ist.
- Ohne Rückmeldung zur aktuellen Größe lagen die Modelle oft deutlich über oder
  unter der Zielgröße. Jede Antwort auf eine Änderung enthält jetzt den Stand.
- Ein Hinweis, der nach einem festen Anteil des verbrauchten Budgets kam, war zu
  spät, weil spätere Schritte durch den mitgeschickten Verlauf viel größer sind.
  Der Hinweis richtet sich jetzt nach dem Restbudget.

## Ergebnisse

Vergleich mit einer Ground Truth auf `dbader/schedule` (Juli 2026,
`deepseek-chat`, ohne vorgegebene Zielgröße, 3 Wiederholungen mit den Seeds 7,
42 und 123, `runs/experiment_20260707T033256/`). `schedule` ist ein kleines
Python-Programm, mit dem man Aufgaben zu festen Zeiten ausführen lässt. Die
Ground Truth besteht aus 2 Klassen und 2 Linien: `Scheduler` (der Zeitplan)
besitzt seine `Job`s (die geplanten Aufgaben, Komposition), und jeder `Job`
kennt seinen `Scheduler` (Assoziation).

Die Tabelle zeigt den Mittelwert über die drei Wiederholungen. "Kanten strikt"
zählt eine Linie nur als richtig, wenn Anfang, Ende und Art stimmen. "Kanten als
Paar" verlangt nur, dass die richtigen zwei Klassen verbunden sind, egal in
welcher Richtung und mit welcher Art von Linie. Was F1 bedeutet, erklärt das
[Haupt-README](../README.md#wie-man-prüft-ob-ein-diagramm-gut-ist).

| Variante | Knoten-F1 | Kanten strikt | Kanten als Paar |
| :--- | ---: | ---: | ---: |
| prune | 1,00 | 0,78 | 1,00 |
| prune-peek | 1,00 | 0,72 | 1,00 |
| catalog | 1,00 | 0,67 | 1,00 |
| catalog-peek | 0,76 | 0,73 | 0,72 |
| cluster-peek | 0,72 | 0,39 | 0,61 |
| cluster | 0,67 | 0,47 | 0,61 |
| overview | 0,61 | 0,60 | 0,67 |
| overview-peek | 0,61 | 0,60 | 0,52 |

Die Werte lassen sich mit `python -m src.tools.gt_compare
runs/experiment_20260707T033256/ground_truth.json
runs/experiment_20260707T033256/seed_<N>/schedule` für jeden Seed neu
berechnen.

Die Varianten `prune`, `prune-peek` und `catalog` haben die beiden Klassen in
jeder Wiederholung gefunden und keine weitere dazugenommen. Die übrigen
Varianten finden sie ebenfalls, nehmen aber zusätzliche Klassen mit auf. Bei
den besten Varianten hat das Lesen im Code (Peek) keinen messbaren Vorteil
gebracht. Die 24 Läufe haben zusammen etwa 0,15 US-Dollar gekostet.

Stabilität auf `schedule` und `loguru` (Juli 2026, 8 Varianten mit je 5 Seeds,
`runs/experiment_20260713T214319/experiment_summary.md`): Auf `loguru`, einem
Programm zum Schreiben von Protokolldateien, liegt die mittlere Zahl der Klassen
im Diagramm je nach Variante zwischen etwa 9 und 19. Die Standardabweichung, ein
Maß dafür, wie stark die Zahl von Lauf zu Lauf schwankt, liegt zwischen 1,5
und 4,7 Klassen. Eine Ground Truth gibt es für `loguru` nicht.

`schedule` ist sehr klein, und Ergebnisse auf zwei Klassen lassen sich kaum auf
größere Systeme übertragen. Das war der Anlass, nach einem größeren Datensatz mit
echten Diagrammen zu suchen, was dann zum Wechsel auf Java geführt hat.

## Installation und Aufruf

Die folgenden Befehle tippt man in ein Terminal, im Ordner
`1-llm-pipeline-abstrakte-klassendiagramme`. Sie richten eine eigene
Python-Umgebung (`.venv`) ein, installieren das Paket und lassen die Tests
laufen. Eine ausführlichere Anleitung, auch für Windows und Docker, steht in
[`INSTALLATION.md`](../INSTALLATION.md).

```bash
python -m venv .venv
.venv/bin/pip install -e '.[java,dev]'
.venv/bin/python -m pytest -q -m 'not network'
```

API-Schlüssel (das Passwort für den Zugang zum Modellanbieter) werden aus
Umgebungsvariablen gelesen (`GEMINI_API_KEY`, `DEEPSEEK_API_KEY`, je nach
Konfiguration).

```bash
# einfacher Lauf (Standard: Variante catalog)
python -m src /pfad/zum/repo

# bestimmte Variante und Zielgröße
python -m src https://github.com/user/repo --method cluster-peek --target-nodes 15

# alle acht Varianten über eine Liste von Repos
python -m src repos.txt --method all --out runs/

# Java-Repo
python -m src /pfad/zum/java/repo --language java

# Trockenlauf ohne LLM
python -m src /pfad/zum/repo --method all --dry-run --no-cleanup
```

Die Konfigurationen liegen in `configs/`. `default.yaml` enthält die
Standardwerte, die anderen Dateien überschreiben einzelne Werte davon:

| Datei | Zweck |
| :--- | :--- |
| `default.yaml` | Standardwerte, Gemini als Modell |
| `deepseek.yaml`, `deepseek_exp.yaml` | DeepSeek, die zweite mit den Budgets der Juli-Experimente |
| `ollama.yaml` | lokales Modell über Ollama (`qwen2.5:14b`) |
| `ollama_docker.yaml` | dasselbe, wenn die Pipeline im Docker-Container läuft und Ollama auf dem Rechner selbst |
| `gemini.yaml` | Gemini mit etwas höherer Temperatur (mehr Zufall in den Antworten) |
| `smoke_*.yaml` | kurze Funktionstests (Gemini bzw. `qwen2:0.5b`) |

## Ordner

| Ordner | Inhalt |
| :--- | :--- |
| `src/parsing/` | statische Analyse: `python/` (ast-Modul und pyreverse) und `java/` (eigener Parser auf tree-sitter), daneben was beide teilen (`code_graph.py` setzt die Schritte zusammen, `models.py`, `languages.py`, `cache.py`) |
| `src/methods/` | Driver, Varianten, Tools, Clustering |
| `src/llm/` | Anbindung an das LLM über litellm, Wiederholversuche, Protokoll, Platzhalter für Trockenläufe |
| `src/schema/` | Graph-Modell, Validator, PlantUML-Ausgabe |
| `src/cleanup/`, `src/targeting/` | Aufräumen durch das LLM, automatische Zielgröße |
| `src/tools/` | Hilfsskripte: Vergleich mit Ground Truth, Lauf wiederholen, PlantUML neu erzeugen |
| `prompts/` | Prompts für das LLM (englisch, weil sie Teil des Versuchs sind) |
| `configs/` | Konfigurationen |
| `tests/` | Tests, laufen ohne Netz und ohne LLM |
| `doku/` | [Beschreibung des Java-Parsers](doku/java-parser.md) |
| `runs/` | Ausgaben der Läufe, `runs/old/` enthält die Läufe von Mai bis Juli 2026 (nur im vollständigen Projektordner, nicht auf GitHub) |

Jeder Lauf schreibt `diagram.puml`, `graph.json`, `trace.jsonl` (alle Anfragen
an das LLM mit Token und Dauer), `config.yaml` (die benutzten Einstellungen),
`errors.log` und `summary.md`.
