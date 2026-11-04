# LLM-Pipeline für abstrakte Klassendiagramme

Die Pipeline liest ein Repository (Python oder Java) ein und lässt ein
Sprachmodell daraus ein abstraktes PlantUML-Klassendiagramm erstellen. Das
Diagramm soll nur die zentralen Klassen zeigen, also Fachklassen, Klassen mit
steuernder Rolle und wichtige Schnittstellen. Hilfsklassen, reine Datenklassen,
Framework-Code und Tests werden weggelassen.

Das Python-Paket heißt `abstract-uml`. Die Vorgeschichte des Projekts steht im
README eine Ebene höher.

## Stand

- Die Pipeline läuft für Python und Java vollständig durch.
- Alle Strategien laufen über einen gemeinsamen Driver mit acht Varianten.
- Die letzten Läufe mit echtem LLM waren im Juli 2026 mit `deepseek-chat` auf den
  Python-Repos `schedule` und `loguru`.
- Der Java-Zweig ist getestet und auf Forschungsdaten gemessen, lief aber bisher
  nur als Trockenlauf ohne LLM.
- Der Java-Parser kann zusätzlich Klassendiagramme wie IntelliJ erzeugen
  (IntelliJ-Modus, siehe unten).
- Alle Tests mit `pytest -m 'not network'` bestehen.

## Ablauf

```
Repo (Pfad, GitHub-URL oder Liste)
  -> Dateien sammeln, Preflight (Größengrenzen)
  -> statische Analyse: Klassen, Member, Importgraph, voller Klassengraph
  -> Driver: das LLM baut mit Tools einen Arbeitsgraphen
  -> Prüfung und Reparatur (Validator), optional Cleanup durch das LLM
  -> graph.json, diagram.puml, Trace und Kennzahlen pro Lauf
```

Intern wird mit einem Graph-JSON gearbeitet (`src/schema/`), das PlantUML wird
erst am Schluss daraus erzeugt.

### Statische Analyse

| | Python | Java |
| :--- | :--- | :--- |
| Dateien | `*.py` | `*.java` |
| Klassen und Member | `ast` | `tree-sitter-java` |
| Abhängigkeiten | Importzeilen | aufgelöste Typreferenzen |
| voller Klassengraph | `pyreverse` (aus pylint) | eigener Extraktor |
| Datei pro Repo | `pyreverse.json/.puml` | `javagraph.json/.puml` |

Ab hier ist der Ablauf für beide Sprachen gleich, nur die Eingabedaten der
statischen Analyse unterscheiden sich.

### Java-Parser

Der Parser liegt in `src/parsing/java/`:

| Datei | Aufgabe |
| :--- | :--- |
| `ts_pass.py` | liest den Syntaxbaum und sammelt Typen, Felder, Methoden und Obertypen |
| `resolution.py` | löst Typnamen über Pakete, Imports und verschachtelte Typen auf |
| `graph_builder.py` | baut daraus den vollständigen Klassengraphen |
| `import_graph.py` | Abhängigkeiten zwischen Paketen für das Clustering |
| `javac_solver.py` | optionale Ergänzung über den JDK-Compiler |
| `intellij.py` | Klassendiagramm nach den Regeln von IntelliJ (siehe unten) |

Wie die einzelnen Schritte zusammenspielen, steht ausführlich in
`doku/java-parser.md`.

Einige Designentscheidungen:

- Der Parser liest nur Quelltext und keinen Bytecode. Projekte müssen also nicht
  kompilierbar sein. An diesem Punkt sind die Bytecode-Werkzeuge im Vergleich
  gescheitert (siehe Ordner 2).
- Das Encoding wird pro Datei bestimmt (UTF-8, dann CP1252, dann Latin-1). Ältere
  Java-Projekte sind oft nicht in UTF-8 gespeichert.
- Paketnamen werden relativ zum Repo angegeben, das gemeinsame Präfix wird
  entfernt (`de.firma.app.model` wird zu `model`).
- Externe Oberklassen und Interfaces bleiben im Paket `external` erhalten, weil
  z. B. die Vererbung von `JFrame` etwas über die Rolle einer Klasse aussagt.
  Felder mit externen Typen wie `String` oder `Timer` erzeugen dagegen keine
  Kante.
- Mehrdeutige Typreferenzen werden gemeldet und weggelassen.
- Zu jeder Beziehung wird die Fundstelle gespeichert (Feld oder Methode, Typ,
  Datei, Zeile). Mehrdeutigkeiten, doppelte Deklarationen und Parse-Fehler stehen
  in `javagraph.diagnostics.json`.
- Einstellbar sind der Detailgrad der Member
  (`--java-member-profile structure|summary|public-api|full`),
  Methodenabhängigkeiten (`--java-method-dependencies`) und die Auflösung über
  javac (`--java-symbol-solver javac` mit `--java-classpath`).

Warum ein eigener Parser geschrieben wurde, steht im README eine Ebene höher und
in Ordner 2.

### IntelliJ-Modus

Mit `--java-relations intellij` (in der Konfiguration `java.relation_style:
intellij`) erzeugt der Parser das Klassendiagramm nach den Regeln von IntelliJ
IDEA (`src/parsing/java/intellij.py`). Dabei werden auch die Methodenrümpfe
gelesen. Jeder Verweis im Code wird zur Abhängigkeit, Methodenaufrufe zählen für
die Klasse, die die Methode deklariert, auch über Aufrufketten wie
`RaiseMeUp.getCurrentJob().getImpactenergy()`. `new` ergibt eine Abhängigkeit mit
`«create»`, Felder werden zu Kompositionen mit "1" oder "*", innere Klassen
bekommen eine eigene Kante (`nesting`). Vererbung und Realisierung laufen über
Typen hinweg, die nicht im Diagramm stehen.

| Option | Bedeutung |
| :--- | :--- |
| `--java-diagram-classes DATEI` | Klassen im Diagramm, ein voll qualifizierter Name pro Zeile. Ohne Datei alle |
| `--java-ide-no-jdk` | so tun, als sei in IntelliJ kein JDK eingerichtet gewesen |
| `--java-ide-no-same-package` | so tun, als habe IntelliJ Klassen aus demselben Paket nicht gefunden |

Die Regeln und der Abgleich mit den neun IntelliJ-Diagrammen von Zhang/Hebig
stehen in Ordner 2 unter `doku/intellij-nachbildung.md`.

### Varianten

Alle Varianten nutzen dieselbe Driver-Schleife mit denselben Tools, Prompts,
Budgets und Abbruchregeln. Sie unterscheiden sich in drei Einstellungen:

- seed: Der Arbeitsgraph startet leer (additiv) oder mit dem vollständigen
  Klassengraphen, aus dem das Modell streicht (subtraktiv).
- context: Was in der ersten Nachricht steht, also Paketübersicht, Cluster des
  Importgraphen oder der vollständige Klassengraph.
- peek: Ob das Modell den Quelltext selbst lesen darf (`read_file`,
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
Teilgraphen werden danach in einem Syntheseschritt zusammengeführt. Die alten
Namen `m1a` bis `m4b` stammen aus der ersten Version, in der jede Methode ein
eigenes Programm war. Sie funktionieren weiterhin als Alias.

Das Modell hat drei Tools: `inspect_class`, `apply_edits` (Knoten entfernen,
Knoten und Kanten hinzufügen in einem Aufruf) und `emit_diagram`. Bei den
Peek-Varianten kommen `read_file` und `search_code` dazu, die aber erst
freigeschaltet werden, wenn ein erster Entwurf existiert. Kurz vor Ende des
Budgets bekommt das Modell den Hinweis, den Lauf abzuschließen.

Mehrere dieser Regeln kamen durch Probleme in früheren Läufen (`runs/old/`)
dazu:

- Als Knoten und Kanten noch über getrennte Tools angelegt wurden, war das
  Budget oft zwischen beiden Schritten aufgebraucht und die Diagramme hatten
  keine Kanten.
- Modelle mit Lesezugriff haben häufig nur gelesen und nie etwas angelegt. Eine
  Anweisung im Prompt hat das nicht verhindert, deshalb sind die Lesetools jetzt
  bei leerem Graphen gesperrt.
- Ohne Rückmeldung zur aktuellen Größe lagen die Modelle oft deutlich über oder
  unter der Zielgröße. Jede Antwort auf eine Änderung enthält jetzt den Stand.
- Ein Hinweis, der nach einem festen Anteil des verbrauchten Budgets kam, war zu
  spät, weil spätere Züge durch den mitgeschickten Verlauf viel größer sind. Der
  Hinweis richtet sich jetzt nach dem Restbudget.

## Ergebnisse

Vergleich mit einer Ground Truth auf `dbader/schedule` (Juli 2026,
`deepseek-chat`, offene Größe, 3 Wiederholungen,
`runs/experiment_20260707T033256/`). Die Ground Truth besteht aus 2 Knoten und
2 Kanten: Scheduler besitzt seine Jobs (Komposition), Job kennt seinen Scheduler
(Assoziation).

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

Die Varianten mit dem vollständigen Klassengraphen haben die beiden Klassen in
jeder Wiederholung gefunden. `overview` und `cluster` finden sie ebenfalls,
nehmen aber zusätzliche Klassen mit auf. Bei den besten Varianten hat Peek keinen
messbaren Unterschied gemacht. Die 24 Läufe haben zusammen etwa 0,15 $ gekostet.

Stabilität auf `schedule` und `loguru` (Juli 2026, 8 Varianten mit je 5 Seeds,
`runs/experiment_20260713T214319/experiment_summary.md`): Auf `loguru` liegt die
mittlere Knotenzahl je nach Variante zwischen etwa 9 und 19, die
Standardabweichung bei 3 bis 5. Eine Ground Truth gibt es für `loguru` nicht.

`schedule` ist sehr klein, und Ergebnisse auf zwei Klassen lassen sich kaum auf
größere Systeme übertragen. Das war der Anlass, nach einem größeren Datensatz mit
echten Diagrammen zu suchen, was dann zum Wechsel auf Java geführt hat.

## Installation und Aufruf

```bash
python -m venv .venv
.venv/bin/pip install -e '.[java,dev]'
.venv/bin/python -m pytest -q -m 'not network'
```

API-Schlüssel werden aus Umgebungsvariablen gelesen (`GEMINI_API_KEY`,
`DEEPSEEK_API_KEY`, je nach Konfiguration).

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
| `default.yaml` | Standardwerte, Gemini als Backend |
| `deepseek.yaml`, `deepseek_exp.yaml` | DeepSeek, die zweite mit den Budgets der Juli-Experimente |
| `ollama.yaml` | lokales Modell über Ollama (`qwen2.5:14b`) |
| `gemini.yaml` | Gemini mit etwas höherer Temperatur |
| `smoke_*.yaml` | kurze Funktionstests (Gemini bzw. `qwen2:0.5b`) |

## Ordner

| Ordner | Inhalt |
| :--- | :--- |
| `src/parsing/` | statische Analyse: `python/` (ast-Modul und pyreverse) und `java/` (eigener Parser auf tree-sitter), daneben was beide teilen (`code_graph.py` setzt die Schritte zusammen, `models.py`, `languages.py`, `cache.py`) |
| `src/methods/` | Driver, Varianten, Tools, Clustering |
| `src/llm/` | LLM-Client über litellm, Wiederholversuche, Trace, Platzhalter für Trockenläufe |
| `src/schema/` | Graph-Modell, Validator, PlantUML-Ausgabe |
| `src/cleanup/`, `src/targeting/` | Cleanup durch das LLM, automatische Zielgröße |
| `src/tools/` | Hilfsskripte: Vergleich mit Ground Truth, Lauf wiederholen, PlantUML neu erzeugen |
| `prompts/` | Prompts für das LLM (englisch) |
| `configs/` | Konfigurationen |
| `tests/` | Tests, laufen ohne Netz und ohne LLM |
| `doku/` | Beschreibung des Java-Parsers |
| `runs/` | Ausgaben der Läufe, `runs/old/` enthält die Läufe von Mai bis Juli 2026 |

Jeder Lauf schreibt `diagram.puml`, `graph.json`, `trace.jsonl` (alle LLM-Aufrufe
mit Token und Dauer), `config.yaml`, `errors.log` und `summary.md`.

