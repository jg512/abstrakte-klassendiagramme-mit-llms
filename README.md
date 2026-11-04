# Abstrakte Klassendiagramme mit LLMs

Ziel des Projekts ist es, aus dem Quellcode eines Softwareprojekts mit Hilfe von
Sprachmodellen automatisch ein abstraktes Datenmodell bzw. Klassendiagramm zu
erzeugen. Das Diagramm soll nur die wichtigen Klassen enthalten: zentrale
Fachklassen, Klassen mit steuernder Rolle, wichtige Schnittstellen und die
Beziehungen zwischen ihnen.

Ein Parser kann alle Klassen und Beziehungen eines Projekts auflisten, aber
nicht entscheiden, welche davon wichtig sind. Diese Auswahl soll das LLM treffen.

## Ordner

| Ordner | Inhalt | Zeitraum |
| :--- | :--- | :--- |
| [`1-llm-pipeline-abstrakte-klassendiagramme/`](1-llm-pipeline-abstrakte-klassendiagramme/) | Die Pipeline aus statischer Analyse und LLM-Agent mit acht Varianten, für Python und Java. Enthält auch den eigenen Java-Parser (`src/parsing/java/`, beschrieben in `doku/java-parser.md`) und die Läufe mit echten Modellen (`runs/`). | Mai bis September 2026 |
| [`2-java-extraktoren-benchmark-forschungsdaten/`](2-java-extraktoren-benchmark-forschungsdaten/) | Vergleich von Java-Extraktoren auf öffentlichen Forschungsdaten: 30 Projekte aus Lindholmen und 9 Projekte von Zhang/Hebig mit von Hand abstrahierten Diagrammen, dazu Fallstudien. | September/Oktober 2026 |
| [`3-java-parser-klassendiagramme/`](3-java-parser-klassendiagramme/) | Der Java-Parser aus Ordner 1 als eigenes Werkzeug (`javauml`): Java-Repo als Pfad oder Git-URL rein, Klassendiagramm als PlantUML, JSON, PNG oder SVG raus. Ohne LLM und ohne Build. | November 2026 |

Jeder Ordner hat ein eigenes README. Wie man alles auf einem neuen Rechner
installiert und die Messungen wiederholt, direkt oder mit Docker, steht in
[`INSTALLATION.md`](INSTALLATION.md).

## Verlauf

### Phase 0: Lokale Open-Source-Modelle und Feintuning (Januar bis April 2026)

Zuerst sollte ein Open-Source-Modell lokal laufen und eventuell für die Aufgabe
feingetunt werden. Das hat aus mehreren Gründen nicht funktioniert:

- Die vorhandene Hardware reichte nur für Modelle bis etwa 24 Milliarden
  Parameter, für Feintuning noch weniger.
- Modelle dieser Größe konnten nicht zuverlässig einschätzen, welche Klassen
  wichtig sind.
- Ein ganzes Repository passte nicht in das Kontextfenster.
- Die Modelle hielten sich oft nicht an das vorgegebene JSON-Format, sodass die
  Ausgaben nicht weiterverarbeitet werden konnten.

Deshalb wurde der Ansatz geändert: Statt eines eigenen Modells sollte ein
allgemeines LLM-Harness mit Prompt Engineering entstehen, in dem das Modell
austauschbar ist. Der Schwerpunkt lag damit auf der Pipeline um das Modell
herum, also auf statischer Analyse, Tools für das Modell und der Prüfung und
Reparatur der Ausgaben.

### Phase 1: Python-Pipeline mit fünf Methoden (bis Ende Mai 2026)

In dieser Phase entstand die Pipeline in Ordner 1, zunächst nur für Python. Das
LLM bekommt dabei statt des rohen Codes die Ergebnisse eines Parsers (Klassen,
Member, Importgraph und den vollständigen Klassengraphen aus `pyreverse`) und
wählt daraus aus. Es wurden fünf Methoden ausprobiert:

- additiv, also mit einem leeren Diagramm beginnen und es aufbauen: Paket für
  Paket (M1), als Agent mit Lesezugriff auf den Code (M2) oder getrennt nach
  Clustern des Importgraphen mit anschließender Zusammenführung (M3)
- subtraktiv, also mit dem vollständigen Klassengraphen beginnen und Klassen
  streichen: ohne (M4a) und mit Lesezugriff auf den Code (M4b)

Die Modelle wurden über `litellm` angebunden. Getestet wurde auf drei
Python-Repos: `schedule` (etwa 1.000 Zeilen), `loguru` und `transitions` (je
etwa 5.000 Zeilen).

Lokal lief über Ollama zunächst wieder ein Open-Source-Modell (`qwen2.5:14b`).
Die Probleme aus Phase 0 tauchten wieder auf, ließen sich aber besser
handhaben: Das Kontextfenster von Ollama ist standardmäßig auf 2.048 Token
gesetzt und wurde auf 32.768 erhöht, und bei ungültigem JSON wird die Anfrage
einmal mit einem Korrekturhinweis wiederholt. Sehr kleine Modelle wie
`qwen2:0.5b` waren nur noch für Funktionstests brauchbar.

Danach wurden Gemini (`gemini-2.5-pro`, Läufe am 22. und 29.05.) und später
DeepSeek (`deepseek-chat`) über die API getestet. Mit beiden entstanden
brauchbare Diagramme. Mit schwächeren Modellen wie `flash-lite` lieferten die
agentischen Methoden M2 und M3 dagegen leere oder fast leere Diagramme.

Das größte Problem war der wachsende Kontext. Bei einem Agenten mit Tools wird
in jedem Schritt der gesamte bisherige Verlauf erneut mitgeschickt. Mit jedem
Tool-Aufruf werden die Anfragen größer, bis das Budget oder das Kontextfenster
erschöpft ist. DeepSeek hat zum Beispiel zuerst die gesamte Codebasis gelesen
und erst danach Klassen angelegt, das waren etwa 1.500 Token pro Klasse. Ab
etwa 20 Klassen war bei den Varianten, die mit einem leeren Diagramm beginnen,
das Budget aufgebraucht, bevor ein Diagramm ausgegeben wurde.

### Phase 2: Ein gemeinsamer Driver statt fünf Programmen (Juni und Juli 2026)

Die fünf Methoden waren getrennte Programme mit eigenen Prompts und Budgets und
ließen sich deshalb schlecht vergleichen. Anfang Juli wurden sie zu einem
gemeinsamen Driver zusammengeführt. Die Methoden unterscheiden sich seitdem nur
in drei Einstellungen: womit der Graph startet, welcher Kontext im ersten Prompt
steht und ob das Modell den Code lesen darf. Daraus ergeben sich acht Varianten
mit denselben Tools, Prompts und Budgets.

Gegen den wachsenden Kontext und typische Fehler der Modelle kamen dabei
mehrere Änderungen dazu: ein Tool, das Knoten und Kanten in einem Aufruf
anlegt, eine Rückmeldung zur aktuellen Größe in jeder Antwort, ein Hinweis zum
Abschließen abhängig vom Restbudget, Lesezugriff erst nach einem ersten Entwurf
und eine optionale Zusammenfassung des Verlaufs. Die Gründe dafür stehen im
README von Ordner 1.

Am 07.07. wurde zum ersten Mal mit einer Ground Truth verglichen, auf `schedule`
mit `deepseek-chat`. Die Varianten, die mit dem vollständigen Klassengraphen
arbeiten (`prune`, `prune-peek`, `catalog`), haben die beiden zentralen Klassen
in jeder Wiederholung gefunden. Die 24 Läufe haben zusammen etwa 0,15 $
gekostet. Am 13.07. folgte ein Lauf mit fünf Seeds auf `schedule` und `loguru`,
um die Stabilität der Ergebnisse zu prüfen.

### Phase 3: Wechsel zu Java und Auswahl des Parsers (August 2026)

Für eine aussagekräftige Auswertung fehlten Referenzdiagramme. `schedule` hat
nur zwei relevante Klassen, und für Python gibt es kaum Datensätze mit Code und
zugehörigem UML-Diagramm. Für Java gibt es deutlich mehr, allein der
Lindholmen-Datensatz verzeichnet über 93.000 UML-Dateien in GitHub-Repos.

Die Pipeline wurde deshalb um Java erweitert. Der Ablauf nach der statischen
Analyse bleibt gleich, nur der Parser ist ein anderer.

Zuerst wurden vorhandene Open-Source-Werkzeuge getestet und mit einer Ground
Truth aus dem Bytecode verglichen. Keines davon war geeignet:

- Die Werkzeuge, die Bytecode lesen (plantuml-generator, Java2PlantUML, genuml),
  müssen die Klassen laden und scheitern an fehlenden Abhängigkeiten. genuml gibt
  außerdem keine Beziehungen aus.
- java2plantuml bricht bei Dateien in ISO-8859-1 ab, meldet aber trotzdem Erfolg
  und gibt ein leeres Diagramm aus.
- javalang liest älteren Code sehr genau, unterstützt aber nur Java 8 und
  scheitert an Records und Sealed-Typen.
- jdeps liefert nur Abhängigkeiten ohne Typ und keine Vererbung.

Deshalb wurde ein eigener Extraktor auf Basis von `tree-sitter-java`
geschrieben. Er liest nur den Quelltext, braucht keinen Build, bestimmt das
Encoding pro Datei und behält externe Oberklassen bei. Beim Vergleich fielen drei Fehler im Extraktor auf
(Vererbung zwischen Interfaces, Auflösung verschachtelter Typen, gekürzte
qualifizierte Namen), die direkt behoben wurden. Danach fand er alle Kanten,
die im Quelltext vorhanden sind.

### Phase 4: Benchmark auf Forschungsdaten (September und Oktober 2026)

Mit der Ground Truth aus dem Bytecode lässt sich prüfen, ob der Parser richtig
liest. Für das Projekt werden aber Diagramme gebraucht, die von Menschen
gezeichnet wurden. Ordner 2 enthält die Recherche nach solchen Daten und die
Messungen:

- 30 Projekte aus Lindholmen, Quelltext und Modell jeweils aus demselben Commit.
  Der eigene Extraktor liegt gleichauf mit javalang und vor java2plantuml. Dabei
  wurden mehrere Fehler im Extraktor gefunden und behoben, danach kamen weitere
  Funktionen dazu (Maven/Gradle-Struktur, Fundstelle pro Kante, Kardinalitäten,
  optionaler javac-Modus).
- 9 Projekte von Zhang/Hebig (2025) mit von Hand abstrahierten Diagrammen,
  verglichen mit sieben Werkzeugen. Nur drei der neun Projekte lassen sich
  kompilieren, deshalb liefen die Bytecode-Werkzeuge kaum. Die Werkzeuge, die
  Quelltext lesen, liefen auf allen Projekten.
- In den Fallstudien (05./06.10.) zeigte sich, dass bei RaiseMeUp die meisten
  Abweichungen am Diagramm liegen. Es beschreibt einen Entwurf, der im Code
  anders umgesetzt wurde.

### Phase 5: Transitive Verbindungen wie in IntelliJ (Oktober 2026)

Kommerzielle UML-Werkzeuge zeigen Verbindungen, die der Parser bisher nicht sah,
weil er nur Felder, `extends` und `implements` las. IntelliJ liest auch die
Methodenrümpfe. In RaiseMeUp hängt `PetObserver` deshalb von `Job` ab, obwohl
`Job` dort nirgends vorkommt: Die Verbindung läuft über den Aufruf
`RaiseMeUp.getCurrentJob().getImpactenergy()`.

Der Parser hat dafür einen zweiten Modus bekommen, der die Klassendiagramme von
IntelliJ nachbildet. Die Regeln wurden aus den neun IntelliJ-Diagrammen im Paket
von Zhang/Hebig abgeleitet: Abhängigkeiten aus allen Verweisen im Code, auch über
Aufrufketten, `«create»` bei `new`, Felder mit "1" oder "*", innere Klassen und
Vererbung über nicht gezeigte Zwischentypen hinweg. Dabei zeigte sich auch, dass
IntelliJ die Projekte unterschiedlich gut aufgelöst hatte (teils ohne JDK, teils
mit falschem Source-Root). Das lässt sich im Parser einstellen.

Auf sieben der neun Projekte erzeugt der Parser dasselbe Diagramm wie IntelliJ.
Bei Orekit und Neuroph stimmen alle Kanten, die sich im Bild prüfen ließen. Die
Einzelheiten stehen in Ordner 2 unter `doku/intellij-nachbildung.md`.

### Phase 6: Der Parser als eigenes Werkzeug (November 2026)

Der Java-Parser ist auch ohne die LLM-Pipeline nützlich, etwa um für ein
beliebiges Java-Repo schnell ein vollständiges Klassendiagramm zu bekommen.
Ordner 3 enthält ihn deshalb als eigenes Paket mit Kommandozeile. Es braucht nur
`tree-sitter`, keine LLM-Bibliotheken und keine Konfiguration der Pipeline.

Der Code des Parsers ist eine Kopie aus Ordner 1. Auf allen 59 Projekten aus
Ordner 2 liefern beide in vier Einstellungen Zeichen für Zeichen dieselbe
Ausgabe, und der IntelliJ-Abgleich ergibt über das neue Werkzeug dieselben
Kanten.

## Aktueller Stand

- Die Pipeline unterstützt Python und Java. Für Java gibt es einen eigenen
  Parser, der ohne Build auskommt und auf den Forschungsdaten so gut abschneidet
  wie die besten getesteten Werkzeuge.
- Mit den Daten von Zhang/Hebig gibt es einen Datensatz mit Java-Diagrammen, die
  von Menschen abstrahiert wurden.
- Die acht Varianten wurden noch nicht mit einem echten LLM auf Java-Projekten
  ausgeführt und mit den Diagrammen von Zhang/Hebig verglichen. Auf Java gab es
  bisher nur Trockenläufe ohne LLM. Das ist der nächste Schritt.
- Der Java-Parser kann die Klassendiagramme von IntelliJ nachbilden. Auf sieben
  der neun Projekte ist das vollständig gegen die IntelliJ-Bilder geprüft, bei
  Orekit und Neuroph nur teilweise.
- Den Parser gibt es zusätzlich als eigenes Werkzeug in Ordner 3. Er liegt dort
  als Kopie vor. Änderungen am Parser müssen deshalb in Ordner 1 und Ordner 3
  gemacht werden.
- Die Präsentationen werden noch hinzugefügt.

## Probleme und Lösungen

| Problem | Phase | Lösung |
| :--- | :--- | :--- |
| Lokale Hardware reicht nur für Modelle bis etwa 24B | 0 | Wechsel zu API-Modellen, lokale Modelle nur noch optional über Ollama |
| Modelle halten das JSON-Format nicht ein | 0 und 1 | Validator, der fehlerhafte Graphen repariert, ein Wiederholversuch mit Korrekturhinweis und Tools statt freier Textausgabe |
| Wachsender Kontext durch wiederholte Tool-Aufrufe | 1 und 2 | gemeinsames Budget, Hinweis abhängig vom Restbudget, ein Tool für Knoten und Kanten, Lesezugriff erst nach einem Entwurf, optionale Zusammenfassung des Verlaufs |
| Fünf Methoden schlecht vergleichbar | 1 | ein Driver, acht Varianten mit gleichen Prompts und Budgets |
| Testrepos zu klein für belastbare Aussagen | 2 | Suche nach größeren Datensätzen mit Diagrammen |
| Kaum UML-Datensätze für Python | 3 | Wechsel zu Java |
| Vorhandene Java-Werkzeuge scheitern an Abhängigkeiten, Encoding oder neuer Syntax | 3 | eigener Parser auf Basis von tree-sitter |
| Abgleich über Kurznamen verdeckt Fehler bei gleichnamigen Klassen | 3 | eigene Prüfung der Auflösung, mehrdeutige Fälle werden gemeldet statt geraten |
| Referenzdiagramme weichen teilweise vom Code ab | 4 | Fallstudien am Code. Die Werte zeigen die Übereinstimmung mit dem Diagramm und sagen nichts über die Korrektheit |
| Parser sieht keine Verbindungen über Methodenaufrufe | 5 | IntelliJ-Modus: Methodenrümpfe lesen, Typen von Aufrufketten bestimmen |

## Offene Punkte

- Läufe mit echtem LLM auf Java-Projekten und Vergleich mit den Diagrammen von
  Zhang/Hebig.
- Festlegen, wie die Qualität eines Diagramms gemessen wird: Vergleich mit einer
  Referenz, Bewertung durch Menschen oder Bewertung durch ein LLM. Diese Frage
  ist seit dem ersten Bericht offen.
