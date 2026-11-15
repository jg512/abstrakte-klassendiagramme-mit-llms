**Deutsch** · [English](README.en.md)

# Abstrakte Klassendiagramme mit LLMs

Dieses Projekt untersucht, ob ein Sprachmodell (ein LLM, wie es auch hinter
ChatGPT steckt) aus dem Programmcode einer Software selbstständig eine
übersichtliche Zeichnung ihres Aufbaus erstellen kann. Die Zeichnung soll nur
das Wichtige zeigen, so wie es ein erfahrener Mensch tun würde, der das System
kennt.

Diese Seite ist der Einstieg. Sie erklärt das Projekt so, dass man es ohne
Programmierkenntnisse verstehen kann, und führt zu allen anderen Dokumenten.
Fachbegriffe werden beim ersten Auftreten erklärt und stehen zum Nachschlagen
noch einmal unter [Begriffe](#begriffe) am Ende.

## Inhalt

- [Worum es geht](#worum-es-geht)
- [Warum man das braucht](#warum-man-das-braucht)
- [Warum ein Sprachmodell](#warum-ein-sprachmodell)
- [Wie es gemacht wird](#wie-es-gemacht-wird)
- [Wie man prüft, ob ein Diagramm gut ist](#wie-man-prüft-ob-ein-diagramm-gut-ist)
- [Was bisher herausgekommen ist](#was-bisher-herausgekommen-ist)
- [Wegweiser durch die Dokumente](#wegweiser-durch-die-dokumente)
- [Verlauf des Projekts](#verlauf-des-projekts)
- [Aktueller Stand](#aktueller-stand)
- [Probleme und Lösungen](#probleme-und-lösungen)
- [Offene Punkte](#offene-punkte)
- [Begriffe](#begriffe)

## Worum es geht

Software besteht aus **Quellcode**, also Text in einer Programmiersprache, der
dem Computer sagt, was er tun soll. Größere Programme werden in **Klassen**
aufgeteilt. Eine Klasse beschreibt eine Art von Ding, mit dem das Programm
arbeitet. In einer Software für eine Bücherei gäbe es zum Beispiel eine Klasse
`Buch` und eine Klasse `Bibliothek`. Eine Klasse hat **Attribute** (die Daten,
die sie sich merkt, etwa den Titel eines Buches) und **Methoden** (das, was sie
tun kann, etwa ein Buch hinzufügen).

So sieht das in der Programmiersprache Java aus:

```java
public class Buch {
    private String titel;           // jedes Buch hat einen Titel
}

public class Bibliothek {
    private List<Buch> buecher;     // eine Bibliothek hat eine Liste von Büchern
    public void hinzufuegen(Buch b) { ... }
}
```

Klassen hängen voneinander ab. Die Bibliothek enthält Bücher, ein Roman ist eine
besondere Art von Buch, ein Ausleihvorgang verweist auf ein Buch und eine
Person. Ein **Klassendiagramm** zeichnet diese Zusammenhänge auf: Jede Klasse
ist ein Kasten, jede Beziehung eine Linie. Wie die Kästen und Linien aussehen,
legt die **UML** fest (Unified Modeling Language), eine weltweit übliche
Zeichensprache für Software. Eine Raute am Linienende heißt zum Beispiel "hat
als Teil", ein Dreieck heißt "ist eine besondere Art von".

```
┌────────────┐               ┌──────────┐
│ Bibliothek │◇──────────────│   Buch   │
│            │ buecher  0..* │ titel    │
└────────────┘               └──────────┘
                                   △
                                   │  "ist ein"
                             ┌──────────┐
                             │  Roman   │
                             └──────────┘
```

Gelesen: Eine Bibliothek hat beliebig viele (`0..*`) Bücher, und ein Roman ist
ein Buch. In diesem Projekt werden Diagramme als **PlantUML** geschrieben, einem
Textformat, aus dem ein Programm das Bild zeichnet. Die Zeile
`Bibliothek o-- "0..*" Buch : buecher` ergibt die obere Linie.

Für zwei Klassen ist so ein Diagramm schnell gezeichnet. Echte Programme haben
aber Hunderte oder Tausende Klassen. Ein Diagramm mit allen Klassen ist dann so
voll, dass niemand mehr etwas erkennt. Wer ein System erklären will, zeichnet
deshalb ein **abstraktes** Klassendiagramm: Es lässt Hilfsklassen, technische
Details und Testcode weg und zeigt nur die zentralen Klassen und wie sie
zusammenhängen. Ein guter Vergleich ist der Netzplan einer U-Bahn. Er lässt
Straßen, Häuser und genaue Entfernungen weg und ist gerade deshalb nützlicher
als ein Stadtplan, wenn man wissen will, wie man von A nach B kommt.

Das Ziel des Projekts ist, solche abstrakten Diagramme automatisch zu erzeugen.

## Warum man das braucht

- Wer neu in ein Softwareprojekt kommt, muss erst einmal verstehen, wie es
  aufgebaut ist. Ein gutes Übersichtsdiagramm spart Tage an Lesen.
- Von Hand gezeichnete Diagramme veralten, weil der Code sich weiterentwickelt
  und niemand das Bild nachzieht. Ein Diagramm, das sich jederzeit neu erzeugen
  lässt, bleibt aktuell. Wie häufig gezeichnete Diagramme vom Code abweichen,
  hat sich auch in diesem Projekt gezeigt (siehe
  [Fallstudien](2-java-extraktoren-benchmark-forschungsdaten/doku/fallstudien.md)).
- Viele Firmen betreiben Software, die vor Jahren geschrieben wurde und deren
  Autoren längst weg sind. Bevor man so ein System ändern oder ersetzen kann,
  muss man es verstehen.
- Für Forschung und Lehre ist interessant, wie Menschen beim Zeichnen
  abstrahieren, also was sie weglassen und was sie behalten, ist bisher wenig
  verstanden. Ein Werkzeug, das diese Auswahl nachahmt, macht sie messbar.

## Warum ein Sprachmodell

Ein Programm, das Quellcode liest und seinen Aufbau erkennt, heißt **Parser**.
Man kann es sich vorstellen wie jemanden, der einen Satz grammatisch zerlegt:
Er erkennt Subjekt, Verb und Objekt, ohne zu verstehen, worum es inhaltlich
geht. Ein Parser findet zuverlässig jede Klasse und jede Beziehung im Code. Er
kann aber nicht beurteilen, welche davon für das Verständnis wichtig sind.
Dass `Bibliothek` zentral ist und `DatumsFormatierer` eine Nebensache, steht
nirgends im Code.

Diese Einschätzung soll ein **LLM** übernehmen (Large Language Model, großes
Sprachmodell). Ein LLM ist ein Programm, das mit riesigen Mengen Text trainiert
wurde, darunter viel Quellcode, und das deshalb Code lesen und Fragen dazu
beantworten kann. Bekannte Beispiele sind GPT, Gemini oder DeepSeek. In diesem
Projekt bekommt das Modell nicht den rohen Code, sondern das, was der Parser
gefunden hat, und wählt daraus aus. Die Arbeitsteilung ist also: Der Parser
liefert genau das, was im Code steht, das LLM trifft die Auswahl.

## Wie es gemacht wird

Die Verarbeitung läuft in mehreren Schritten hintereinander ab. So eine Kette
nennt man **Pipeline**.

1. **Code einlesen.** Man gibt ein **Repository** an (kurz Repo, der Ordner
   eines Softwareprojekts, oft auf GitHub). Die Pipeline sammelt alle
   Quelldateien und lässt Tests und erzeugte Dateien weg.
2. **Statische Analyse.** Der Parser liest den Code, ohne ihn auszuführen
   (darum "statisch"). Er erstellt eine Liste aller Klassen mit ihren
   Attributen und Methoden und den vollständigen **Klassengraphen**: alle
   Klassen als Punkte (**Knoten**) und alle Beziehungen als Verbindungen
   (**Kanten**).
3. **Auswahl durch das LLM.** Das Modell arbeitet mit **Tools**, also Befehlen,
   die es aufrufen darf, etwa "zeige mir Klasse X", "lies diese Datei" oder
   "füge diese Klasse und diese Linie zum Diagramm hinzu". Es baut das Diagramm
   in mehreren Schritten auf und entscheidet selbst, was es als Nächstes tut.
   Ein Modell, das so selbstständig mit Werkzeugen arbeitet, nennt man
   **Agent**. Damit es nicht endlos weiterarbeitet, hat es ein **Budget**, eine
   Obergrenze für die verbrauchte Textmenge.
4. **Prüfen und reparieren.** Ein Prüfprogramm (der **Validator**) entfernt
   Linien zu Klassen, die es nicht gibt, doppelte Einträge und Ähnliches.
5. **Ausgabe.** Am Ende stehen das Diagramm als PlantUML und als **JSON** (ein
   Textformat für strukturierte Daten, das Programme leicht lesen können) sowie
   ein Protokoll aller Anfragen an das Modell mit Kosten und Dauer.

Wie das Modell arbeitet, lässt sich auf acht Arten einstellen (die
**Varianten**). Es kann mit einem leeren Blatt anfangen und wichtige Klassen
eintragen, oder es bekommt das vollständige Diagramm und streicht das
Unwichtige (das heißt im Projekt `prune`, englisch für "zurückschneiden"). Es
bekommt zu Beginn eine Übersicht der **Pakete** (Ordner, in denen
zusammengehörige Klassen liegen), Gruppen eng verbundener Klassen oder die
vollständige Liste aller Klassen zu sehen. Und es darf den Quellcode selbst
nachlesen oder nicht (`peek`, "hineinschauen"). Nicht jede Kombination ist
sinnvoll: Wer das vollständige Diagramm zum Streichen bekommt, sieht ohnehin
schon alle Klassen. So ergeben sich sechs Varianten, die leer beginnen, und
zwei, die streichen, zusammen acht. Alle Varianten
benutzen dieselben Anweisungen und dasselbe Budget, damit man sie fair
vergleichen kann. Die genaue Beschreibung steht im
[README von Ordner 1](1-llm-pipeline-abstrakte-klassendiagramme/README.md).

Die Pipeline funktioniert für zwei Programmiersprachen, **Python** und
**Java**. Für Java wurde ein eigener Parser geschrieben, weil die vorhandenen
Werkzeuge nicht taugten (dazu unten mehr). Diesen Parser gibt es auch als
eigenständiges Programm `javauml`, das für ein Java-Projekt ohne LLM ein
vollständiges Klassendiagramm zeichnet.

## Wie man prüft, ob ein Diagramm gut ist

Um zu messen, wie gut ein erzeugtes Diagramm ist, braucht man eine richtige
Lösung zum Vergleichen. So eine Referenz heißt **Ground Truth**. Hier sind das
Diagramme, die Menschen zu echten Projekten gezeichnet haben, oder für den
Parser die Beziehungen, die nachweislich im Code stehen.

Ein **Benchmark** ist ein festgelegter Vergleichstest: Alle Werkzeuge bekommen
dieselben Eingaben, und ihre Ergebnisse werden auf dieselbe Weise mit der
Referenz verglichen. Gezählt wird, wie viele Klassen und Linien übereinstimmen.
Daraus ergeben sich drei übliche Kennzahlen, jeweils zwischen 0 und 1:

- **Precision** (Genauigkeit): Welcher Anteil der ausgegebenen Linien ist
  richtig?
- **Recall** (Trefferquote): Welcher Anteil der richtigen Linien wurde gefunden?
- **F1**: ein gemeinsamer Wert aus beiden. Er ist nur hoch, wenn beide hoch
  sind.

Ein Beispiel: Die Referenz hat 4 Linien. Ein Werkzeug zeichnet 5 Linien, davon
sind 3 richtig. Die Precision ist dann 3 von 5 = 0,60, der Recall 3 von 4 =
0,75 und der F1-Wert 2 · 0,60 · 0,75 / (0,60 + 0,75) = 0,67. Ein Werkzeug, das
einfach alle denkbaren Linien zeichnet, hätte einen Recall von 1, aber eine
sehr schlechte Precision. Der F1-Wert bestraft das.

Über viele Projekte hinweg gibt es zwei Arten, den Durchschnitt zu bilden.
**Micro-F1** zählt alle Treffer aller Projekte zusammen und rechnet dann einmal.
**Macro-F1** rechnet für jedes Projekt einzeln und nimmt dann den Mittelwert, so
zählt ein kleines Projekt genauso viel wie ein großes.

Für den Parser ist so ein Vergleich eindeutig, denn er soll genau das liefern,
was im Code steht. Bei den Diagrammen des LLM ist es schwieriger. Ein
abstraktes Diagramm lässt mit Absicht vieles weg, und zwei Fachleute würden
nicht genau dieselben Klassen behalten. Wie man die Qualität eines solchen
Diagramms am besten misst, ist deshalb noch offen (siehe
[Offene Punkte](#offene-punkte)).

Wichtig für das Lesen der Ergebnisse: Ein Wert unter 1 heißt nicht unbedingt,
dass das Werkzeug falsch liegt. Gezeichnete Diagramme sind oft veraltet oder
beschreiben einen Plan, der im Code anders umgesetzt wurde. Die Fallstudien in
Ordner 2 zeigen das an konkreten Projekten.

## Was bisher herausgekommen ist

- Auf dem kleinen Python-Projekt `schedule` haben die besten Varianten mit dem
  Modell DeepSeek die beiden zentralen Klassen in jeder Wiederholung gefunden.
  Alle 24 Läufe zusammen haben etwa 0,15 US-Dollar gekostet. Das Projekt ist
  aber zu klein, um daraus allgemeine Schlüsse zu ziehen.
- Für Java gibt es einen eigenen Parser. Geprüft wurde er auf 39 öffentlichen
  Java-Projekten mit gezeichneten Diagrammen aus zwei Forschungsdatensätzen: 30
  Projekte aus dem Lindholmen-Datensatz und 9 aus einer Studie von Zhang, Zhang,
  Strüber und Hebig (kurz Zhang/Hebig). Dort erreicht er genau dieselben Werte
  wie javalang, das beste andere getestete Werkzeug. Das ist zu erwarten, weil
  beide dieselben Angaben im Code lesen und nach denselben Regeln bewertet
  werden. Seine Vorteile liegen woanders: Er versteht auch neuere
  Java-Versionen, kommt mit alten Dateiformaten zurecht, läuft auch, wenn sich
  ein Projekt nicht übersetzen lässt, und vermerkt zu jeder Linie die Stelle im
  Code, aus der sie stammt.
- IntelliJ IDEA ist eine weit verbreitete Programmierumgebung, die selbst
  Klassendiagramme zeichnen kann. Der Parser hat einen zweiten Modus bekommen,
  der genau diese Diagramme nachbildet. Bei sieben von neun Projekten stimmt das
  Ergebnis vollständig mit dem Bild von IntelliJ überein.
- Noch offen ist der wichtigste Schritt: Die LLM-Varianten wurden noch nicht mit
  einem echten Modell auf Java-Projekten ausgeführt und mit den von Menschen
  gezeichneten Diagrammen verglichen.

Die Einzelheiten und Zahlen stehen in den Dokumenten, die der Wegweiser unten
aufführt.

## Wegweiser durch die Dokumente

Das Projekt hat drei nummerierte Ordner. Sie sind in dieser Reihenfolge
entstanden, und jeder baut auf dem vorigen auf.

| Ordner | Inhalt | Zeitraum |
| :--- | :--- | :--- |
| [`1-llm-pipeline-abstrakte-klassendiagramme/`](1-llm-pipeline-abstrakte-klassendiagramme/) | die Pipeline aus Parser und LLM mit den acht Varianten, für Python und Java, und die Läufe mit echten Modellen | Mai bis September 2026 |
| [`2-java-extraktoren-benchmark-forschungsdaten/`](2-java-extraktoren-benchmark-forschungsdaten/) | der Vergleich von Java-Werkzeugen auf öffentlichen Forschungsdaten: 30 Projekte aus dem Lindholmen-Datensatz und 9 Projekte von Zhang/Hebig mit von Hand abstrahierten Diagrammen, dazu Fallstudien und die Nachbildung von IntelliJ | September und Oktober 2026 |
| [`3-java-parser-klassendiagramme/`](3-java-parser-klassendiagramme/) | der Java-Parser als eigenständiges Werkzeug `javauml`: Java-Projekt rein, Klassendiagramm raus, ohne LLM | November 2026 |

Alle Dokumente gibt es auf Deutsch und auf Englisch. Die englische Fassung hat
denselben Namen mit `.en` davor, also `README.en.md` neben `README.md`.

Es gibt das Projekt in zwei Formen. Das **Repository auf GitHub**
(`jg512/abstrakte-klassendiagramme-mit-llms`) enthält den Code, die Dokumente
und die eigenen Metadaten, aber keine großen Daten. Der **vollständige
Projektordner**, so wie er an die Universität übergeben wird, enthält dazu die
heruntergeladenen Datensätze, die gebauten Fremdwerkzeuge und alle
gespeicherten Läufe und Messergebnisse (zusammen knapp 1 GB). Wo unten steht
"nur im vollständigen Projektordner", fehlt die Datei auf GitHub. Wie man die
Daten selbst neu lädt, steht in [`INSTALLATION.md`](INSTALLATION.md).

### Allgemein

| Dokument | Was drinsteht | Wann lesen |
| :--- | :--- | :--- |
| [`INSTALLATION.md`](INSTALLATION.md) | wie man alles auf einem neuen Rechner einrichtet, direkt oder mit Docker, und die Messungen wiederholt | wenn man selbst etwas ausprobieren oder nachmessen will |

### Ordner 1: die LLM-Pipeline

| Dokument | Was drinsteht | Wann lesen |
| :--- | :--- | :--- |
| [`1-…/README.md`](1-llm-pipeline-abstrakte-klassendiagramme/README.md) | Ablauf der Pipeline, die acht Varianten und warum sie so gebaut sind, Ergebnisse auf `schedule` und `loguru`, Aufruf | wenn man verstehen will, wie das LLM arbeitet und was es bisher geleistet hat |
| [`1-…/doku/java-parser.md`](1-llm-pipeline-abstrakte-klassendiagramme/doku/java-parser.md) | wie der Java-Parser Schritt für Schritt aus Code einen Klassengraphen macht, mit einem durchgerechneten Beispiel aus zwei Klassen | wenn man den Parser verstehen, ändern oder prüfen will |

Die gespeicherten Läufe liegen in `1-…/runs/`. Jeder Lauf hat dort eine kurze
`summary.md`, die das Programm selbst geschrieben hat (englisch). Dieser Ordner
ist zu groß für GitHub und liegt nur im vollständigen Projektordner.

### Ordner 2: Benchmark auf Forschungsdaten

| Dokument | Was drinsteht | Wann lesen |
| :--- | :--- | :--- |
| [`2-…/README.md`](2-java-extraktoren-benchmark-forschungsdaten/README.md) | Fragestellung, wichtigste Ergebnisse und Aufbau des Ordners | als Einstieg in Ordner 2 |
| [`2-…/doku/recherche-datensätze.md`](2-java-extraktoren-benchmark-forschungsdaten/doku/recherche-datensätze.md) | welche Datensätze mit Java-Code und Diagrammen es gibt, welche gewählt wurden und warum, nach welchen Regeln verglichen wird | wenn man wissen will, woher die Vergleichsdaten kommen |
| [`2-…/doku/ergebnisse-lindholmen.md`](2-java-extraktoren-benchmark-forschungsdaten/doku/ergebnisse-lindholmen.md) | drei Werkzeuge auf 30 Lindholmen-Projekten und den Zhang/Hebig-Projekten, die gefundenen und behobenen Fehler im Parser, Tabelle pro Projekt | für die ausführlichen Zahlen des ersten Vergleichs |
| [`2-…/doku/ergebnisse-zhang-hebig.md`](2-java-extraktoren-benchmark-forschungsdaten/doku/ergebnisse-zhang-hebig.md) | alle sieben Werkzeuge auf den Zhang/Hebig-Projekten und warum die meisten an der Übersetzung der Projekte scheitern | für den großen Werkzeugvergleich |
| [`2-…/doku/fallstudien.md`](2-java-extraktoren-benchmark-forschungsdaten/doku/fallstudien.md) | drei Projekte im Detail: Liegt eine Abweichung am Werkzeug oder am Diagramm? | wenn man verstehen will, warum Diagramm und Code auseinanderlaufen |
| [`2-…/doku/intellij-nachbildung.md`](2-java-extraktoren-benchmark-forschungsdaten/doku/intellij-nachbildung.md) | nach welchen Regeln IntelliJ Diagramme zeichnet und wie genau der Parser das nachbildet | für den IntelliJ-Modus |
| [`2-…/doku/werkzeuge.md`](2-java-extraktoren-benchmark-forschungsdaten/doku/werkzeuge.md) | Herkunft, Versionen und Bau der sieben verglichenen Werkzeuge | wenn man die Werkzeuge selbst bauen will |
| [`2-…/doku/reproduzieren.md`](2-java-extraktoren-benchmark-forschungsdaten/doku/reproduzieren.md) | alle Befehle, um die Messungen zu wiederholen | wenn man nachmessen will |
| [`2-…/daten/zhang-hebig/README.md`](2-java-extraktoren-benchmark-forschungsdaten/daten/zhang-hebig/README.md) | was im Datenpaket der Studie von Zhang/Hebig steckt und wie die Referenz daraus entstand | wenn man mit diesen Daten arbeitet |
| [`2-…/ergebnisse/diagramme/README.md`](2-java-extraktoren-benchmark-forschungsdaten/ergebnisse/diagramme/README.md) | Erklärung der gezeichneten Vergleichsbilder, Referenz neben allen Werkzeugen | wenn man sich die Bilder ansieht (liegt nur im vollständigen Projektordner, nicht auf GitHub) |

In `2-…/ergebnisse/pipeline-trockenlauf/` liegen außerdem automatisch erzeugte
Zusammenfassungen eines Probelaufs der Pipeline ohne LLM, ebenfalls nur im
vollständigen Projektordner. Die READMEs unter `2-…/werkzeuge/` und
`2-…/daten/lindholmen/corpus/` gehören zu fremden Projekten, die hier nur als
Untersuchungsgegenstand liegen.

### Ordner 3: javauml

| Dokument | Was drinsteht | Wann lesen |
| :--- | :--- | :--- |
| [`3-…/README.md`](3-java-parser-klassendiagramme/README.md) | Installation, Benutzung, die zwei Modi, Optionen, Ausgabe und Grenzen des Werkzeugs | wenn man für ein Java-Projekt ein Klassendiagramm haben will |
| [`3-…/benchmarks/java_literal/README.md`](3-java-parser-klassendiagramme/benchmarks/java_literal/README.md) | 20 kleine Testprojekte, an denen geprüft wird, ob der Parser genau das liest, was im Code steht | wenn man wissen will, wie der Parser selbst getestet wird |

## Verlauf des Projekts

Das Projekt lief von Januar bis November 2026 in sieben Abschnitten. Sie
werden hier etwas genauer beschrieben, weil die Entscheidungen jeweils aus den
Problemen des vorigen Abschnitts folgen.

### Phase 0: Lokale Open-Source-Modelle und Feintuning (Januar bis April 2026)

Zuerst sollte ein frei verfügbares Modell (**Open Source**) auf einem eigenen
Rechner laufen und eventuell durch **Feintuning** (zusätzliches Training mit
Beispielen) auf die Aufgabe spezialisiert werden. Das hat aus mehreren Gründen
nicht funktioniert:

- Die vorhandene Hardware reichte nur für Modelle bis etwa 24 Milliarden
  **Parameter** (die Größe eines Modells, grob die Zahl seiner einstellbaren
  Werte), für Feintuning noch weniger.
- Modelle dieser Größe konnten nicht zuverlässig einschätzen, welche Klassen
  wichtig sind.
- Ein ganzes Repository passte nicht in das **Kontextfenster**, also die
  Textmenge, die ein Modell auf einmal lesen kann.
- Die Modelle hielten sich oft nicht an das vorgegebene JSON-Format, sodass ihre
  Antworten nicht weiterverarbeitet werden konnten.

Deshalb wurde der Ansatz geändert. Statt eines eigenen Modells sollte ein
allgemeines Programm um das Modell herum entstehen (ein **Harness**), in dem das
Modell austauschbar ist und das über gut gestaltete Anweisungen gesteuert wird
(**Prompt Engineering**, ein **Prompt** ist die Anweisung an das Modell). Der
Schwerpunkt lag damit auf der Pipeline: statische Analyse, Tools für das Modell
und Prüfung und Reparatur der Antworten.

### Phase 1: Python-Pipeline mit fünf Methoden (bis Ende Mai 2026)

In dieser Phase entstand die Pipeline in Ordner 1, zunächst nur für Python. Das
LLM bekommt statt des rohen Codes die Ergebnisse eines Parsers (Klassen,
Attribute und Methoden, den **Importgraphen**, also welche Datei welche andere
benutzt, und den vollständigen Klassengraphen aus dem Werkzeug `pyreverse`) und
wählt daraus aus. Es wurden fünf Methoden ausprobiert:

- additiv, also mit einem leeren Diagramm beginnen und es aufbauen: Paket für
  Paket (M1), als Agent mit Lesezugriff auf den Code (M2) oder getrennt nach
  Gruppen eng verbundener Dateien (**Cluster**) mit anschließender
  Zusammenführung (M3)
- subtraktiv, also mit dem vollständigen Klassengraphen beginnen und Klassen
  streichen: ohne (M4a) und mit Lesezugriff auf den Code (M4b)

Die Modelle wurden über die Bibliothek `litellm` angebunden (eine **Bibliothek**
ist fertiger Code, den man in eigene Programme einbindet), die viele Anbieter
unter einer Oberfläche zusammenfasst. Getestet wurde auf drei Python-Repos:
`schedule` (etwa 1.000 Zeilen Code), `loguru` und `transitions` (je etwa 5.000
Zeilen).

Lokal lief über das Programm Ollama zunächst wieder ein Open-Source-Modell
(`qwen2.5:14b`). Die Probleme aus Phase 0 tauchten wieder auf, ließen sich aber
besser handhaben. Das Kontextfenster von Ollama ist standardmäßig auf 2.048
**Token** gesetzt (ein Token ist ein Wortstück, im Englischen etwa vier
Buchstaben lang, in Token werden Textmengen, Grenzen und Kosten gemessen) und
wurde auf 32.768 erhöht. Bei ungültigem JSON wird die Anfrage einmal mit einem
Korrekturhinweis wiederholt. Sehr kleine Modelle wie `qwen2:0.5b` waren nur noch
für Funktionstests brauchbar.

Danach wurden Gemini (`gemini-2.5-pro`, Läufe am 22. und 29.05.) und später
DeepSeek (`deepseek-chat`) über ihre **API** getestet, also über das Internet
beim Anbieter. Mit beiden entstanden brauchbare Diagramme. Mit schwächeren
Modellen wie `flash-lite`, einer kleinen und günstigen Ausgabe von Gemini,
lieferten die Methoden M2 und M3, bei denen das Modell als Agent arbeitet,
dagegen leere oder fast leere Diagramme.

Das größte Problem war der wachsende Kontext. Ein Agent schickt in jedem
Schritt den gesamten bisherigen Gesprächsverlauf erneut mit. Mit jedem
Tool-Aufruf werden die Anfragen größer, bis das Budget oder das Kontextfenster
erschöpft ist. DeepSeek hat zum Beispiel zuerst die gesamte Codebasis gelesen
und erst danach Klassen angelegt, das waren etwa 1.500 Token pro Klasse. Ab
etwa 20 Klassen war bei den Varianten, die mit einem leeren Diagramm beginnen,
das Budget aufgebraucht, bevor ein Diagramm ausgegeben wurde.

### Phase 2: Ein gemeinsamer Ablauf statt fünf Programmen (Juni und Juli 2026)

Die fünf Methoden waren getrennte Programme mit eigenen Prompts und Budgets und
ließen sich deshalb schlecht vergleichen. Anfang Juli wurden sie zu einem
gemeinsamen Steuerprogramm (dem **Driver**) zusammengeführt. Die Methoden
unterscheiden sich seitdem nur in drei Einstellungen: womit das Diagramm
startet, was im ersten Prompt steht und ob das Modell den Code lesen darf.
Daraus ergeben sich die acht Varianten mit denselben Tools, Prompts und
Budgets.

Gegen den wachsenden Kontext und typische Fehler der Modelle kamen dabei
mehrere Änderungen dazu: ein Tool, das Klassen und Linien in einem einzigen
Aufruf anlegt, eine Rückmeldung zur aktuellen Größe des Diagramms nach jeder
Änderung, ein Hinweis zum Abschließen abhängig vom Restbudget, Lesezugriff erst
nach einem ersten Entwurf und eine optionale Zusammenfassung des bisherigen
Verlaufs. Die Gründe dafür stehen im
[README von Ordner 1](1-llm-pipeline-abstrakte-klassendiagramme/README.md).

Am 07.07. wurde zum ersten Mal mit einer Ground Truth verglichen, auf `schedule`
mit `deepseek-chat`. Die Ground Truth hat dort nur zwei Klassen: `Scheduler`
(der Zeitplan) und `Job` (eine geplante Aufgabe). Die Varianten, die mit dem
vollständigen Klassengraphen arbeiten (`prune`, `prune-peek`, `catalog`), haben
beide in jeder Wiederholung gefunden und keine weitere Klasse dazugenommen. Die
24 Läufe haben zusammen etwa 0,15 $ gekostet. Am 13.07. folgte ein Lauf mit
fünf Wiederholungen je Variante auf `schedule` und `loguru`, um zu prüfen, wie
stark die Ergebnisse von Lauf zu Lauf schwanken. Für jede Wiederholung wird
dabei ein anderer **Seed** gesetzt, ein Startwert für den Zufall, den das
Modell beim Formulieren seiner Antworten benutzt.

### Phase 3: Wechsel zu Java und Auswahl des Parsers (August 2026)

Für eine aussagekräftige Auswertung fehlten Referenzdiagramme. `schedule` hat
nur zwei relevante Klassen, und für Python gibt es kaum Sammlungen von Projekten
mit Code und zugehörigem UML-Diagramm. Für Java gibt es deutlich mehr, allein
der Lindholmen-Datensatz verzeichnet über 93.000 UML-Dateien in Projekten auf
GitHub.

Die Pipeline wurde deshalb um Java erweitert. Der Ablauf nach der statischen
Analyse bleibt gleich, nur der Parser ist ein anderer.

Zuerst wurden vorhandene Open-Source-Werkzeuge getestet. Zum Vergleich diente
eine Ground Truth aus dem **Bytecode** (die Unterlagen zu diesem ersten
Vergleich liegen nicht in diesem Projekt, nur sein Ergebnis): Java-Code wird vor
dem Ausführen von einem **Compiler** in eine maschinennahe Form übersetzt
(kompiliert), und aus diesem Bytecode lassen sich die Beziehungen exakt ablesen.
Keines der Werkzeuge war geeignet:

- Die Werkzeuge, die Bytecode lesen (plantuml-generator, Java2PlantUML von
  juanmf, genuml), brauchen ein Projekt, das sich vollständig übersetzen lässt.
  Dafür müssen alle **Bibliotheken** vorhanden sein, also fremder Code, den das
  Projekt benutzt. Fehlt eine, scheitern sie. genuml gibt außerdem keine
  Beziehungen aus.
- java2plantuml von mirajp1, ein anderes Werkzeug mit fast gleichem Namen, das
  den Quelltext liest, bricht bei Dateien ab, deren Umlaute und Sonderzeichen in
  einer älteren Form gespeichert sind (im **Encoding** ISO-8859-1 statt des
  heute üblichen UTF-8). Es meldet trotzdem Erfolg und gibt ein leeres Diagramm
  aus.
- javalang liest älteren Code sehr genau, versteht aber nur Java bis Version 8
  und scheitert an neueren Sprachmitteln wie Records (Kurzschreibweise für reine
  Datenklassen) und Sealed-Typen (Klassen, die festlegen, wer von ihnen erben
  darf).
- jdeps (Teil von Java selbst) liefert nur, welche Klasse welche benutzt, ohne
  die Art der Beziehung, und keine Vererbung.

Deshalb wurde ein eigener Parser geschrieben, auf Grundlage der Bibliothek
`tree-sitter-java`. Er liest nur den Quelltext und muss das Projekt nicht
übersetzen, erkennt das Encoding jeder Datei einzeln und behält auch Oberklassen
aus fremden Bibliotheken bei (etwa `JFrame` für Programmfenster, was viel über
die Rolle einer Klasse sagt). Beim Vergleich fielen drei Fehler im Parser auf
(Vererbung zwischen Interfaces, Auflösung verschachtelter Typen, gekürzte
Namen), die direkt behoben wurden. Danach fand er auf den damals geprüften
Projekten alle Beziehungen, die im Quelltext vorhanden sind.

Dabei fiel noch etwas auf. Vergleicht man nur über den Kurznamen einer Klasse
(`Kunde` statt `de.firma.model.Kunde`), bleiben Fehler unentdeckt, wenn es zwei
Klassen mit demselben Kurznamen in verschiedenen Paketen gibt. Der Parser prüft
deshalb bei jedem Namen, welche Klasse genau gemeint ist (die **Auflösung**
eines Namens). Ist das nicht eindeutig, meldet er den Fall, statt zu raten.

### Phase 4: Benchmark auf Forschungsdaten (September und Oktober 2026)

Mit der Ground Truth aus dem Bytecode lässt sich prüfen, ob der Parser richtig
liest. Für das Projekt werden aber Diagramme gebraucht, die Menschen gezeichnet
haben. Ordner 2 enthält die Suche nach solchen Daten und die Messungen:

- 30 Projekte aus dem Lindholmen-Datensatz, Code und Diagramm jeweils aus
  demselben Stand des Projekts (demselben **Commit**, so heißt ein gespeicherter
  Zwischenstand in der Versionsverwaltung Git). Der eigene Parser liegt
  gleichauf mit javalang und vor java2plantuml. Dabei wurden mehrere Fehler im
  Parser gefunden und behoben. Danach kamen weitere Funktionen dazu, etwa die
  Erkennung der üblichen Ordnerstruktur von Java-Projekten und zu jeder Linie
  die Stelle im Code, aus der sie stammt.
- 9 Projekte aus der Studie von Zhang, Zhang, Strüber und Hebig (2025, kurz
  Zhang/Hebig), deren Diagramme von Menschen gezielt abstrahiert wurden.
  Verglichen wurden sieben Werkzeuge. Nur drei der neun Projekte lassen sich
  übersetzen, deshalb liefen die Bytecode-Werkzeuge kaum. Die Werkzeuge, die
  Quelltext lesen, liefen auf allen Projekten.
- In den Fallstudien (05. und 06.10.) zeigte sich, dass im Projekt RaiseMeUp die
  meisten Abweichungen am Diagramm liegen. Es beschreibt einen Entwurf, der im
  Code anders umgesetzt wurde. Im Diagramm gibt es zum Beispiel die Klassen
  `Dog`, `Cat`, `Fish` und `Penguin`, im Code ist die Tierart nur ein Eintrag in
  einem Feld.

### Phase 5: Indirekte Verbindungen wie in IntelliJ (Oktober 2026)

Kommerzielle UML-Werkzeuge zeigen Verbindungen, die der Parser bisher nicht sah,
weil er nur die **Deklarationen** las, also die Stellen, an denen Klassen,
Felder und Methoden angekündigt werden: Felder, `extends` ("erbt von") und
`implements` ("erfüllt die Schnittstelle"). Den Code innerhalb der Methoden las
er nicht. IntelliJ liest auch den Inhalt der
Methoden. Im Projekt RaiseMeUp hängt deshalb `PetObserver` von `Job` ab, obwohl
das Wort `Job` dort nirgends vorkommt. Die Verbindung läuft über eine dritte
Klasse, über den Aufruf `RaiseMeUp.getCurrentJob().getImpactenergy()`: Die
Klasse `RaiseMeUp` liefert einen `Job`, und von diesem wird ein Wert abgefragt.
Solche Verbindungen über Umwege heißen **transitiv**.

Der Parser hat dafür einen zweiten Modus bekommen, der die Klassendiagramme von
IntelliJ nachbildet. Die Regeln wurden aus den neun IntelliJ-Diagrammen im
Datenpaket von Zhang/Hebig abgeleitet: Abhängigkeiten aus allen Verweisen im
Code, auch über Aufrufketten, die Markierung `«create»`, wenn eine Klasse ein
Objekt einer anderen erzeugt, Felder mit "1" oder "*" (eins oder viele), innere
Klassen (Klassen, die innerhalb einer anderen geschrieben stehen) und Vererbung
über Klassen hinweg, die nicht im Diagramm stehen. Dabei zeigte sich auch, dass
IntelliJ die Projekte unterschiedlich gut eingelesen hatte, teils ohne die
Standardbibliothek von Java (das **JDK**), teils mit falsch eingestelltem
Quellordner. Beides lässt sich im Parser nachstellen.

Auf sieben der neun Projekte erzeugt der Parser dasselbe Diagramm wie IntelliJ.
Bei den beiden übrigen, Orekit und Neuroph, sind die IntelliJ-Bilder so voll,
dass sich nicht jede Linie verfolgen lässt. Dort stimmen alle Linien, die sich
im Bild prüfen ließen. Die Einzelheiten stehen in
[`intellij-nachbildung.md`](2-java-extraktoren-benchmark-forschungsdaten/doku/intellij-nachbildung.md).

### Phase 6: Der Parser als eigenes Werkzeug (November 2026)

Der Java-Parser ist auch ohne die LLM-Pipeline nützlich, etwa um für ein
beliebiges Java-Projekt schnell ein vollständiges Klassendiagramm zu bekommen.
Ordner 3 enthält ihn deshalb als eigenes Programm, das man über die
**Kommandozeile** (Eingabe von Befehlen im Terminal) aufruft. Es braucht nur
`tree-sitter`, keine LLM-Bibliotheken und keine Einstellungen der Pipeline.
Anders als IntelliJ braucht es weder eine Lizenz noch ein übersetzbares
Projekt, und man kann es für viele Projekte auf einmal aufrufen.

Der Code des Parsers ist eine Kopie aus Ordner 1. Auf allen 59 Projekten, die in
Ordner 2 liegen (alle 50 heruntergeladenen Lindholmen-Projekte, von denen 30 in
die Messung eingingen, und die 9 von Zhang/Hebig), liefern beide in vier
Einstellungen Zeichen für Zeichen dieselbe Ausgabe, und der IntelliJ-Abgleich
ergibt über das neue Werkzeug dieselben Linien.

## Aktueller Stand

- Die Pipeline unterstützt Python und Java. Für Java gibt es einen eigenen
  Parser, der ohne Übersetzen des Projekts auskommt und auf den Forschungsdaten
  so gut abschneidet wie das beste getestete Werkzeug.
- Mit den Daten von Zhang/Hebig gibt es einen Datensatz mit Java-Diagrammen, die
  von Menschen abstrahiert wurden.
- Die acht Varianten wurden noch nicht mit einem echten LLM auf Java-Projekten
  ausgeführt und mit den Diagrammen von Zhang/Hebig verglichen. Auf Java gab es
  bisher nur **Trockenläufe**, bei denen statt des Modells ein Platzhalter mit
  festen Antworten läuft. Sie zeigen, dass alle Teile zusammenarbeiten, sagen
  aber nichts über die Qualität. Der echte Lauf ist der nächste Schritt.
- Der Java-Parser kann die Klassendiagramme von IntelliJ nachbilden. Auf sieben
  der neun Projekte ist das vollständig gegen die IntelliJ-Bilder geprüft, bei
  Orekit und Neuroph nur teilweise.
- Den Parser gibt es zusätzlich als eigenes Werkzeug in Ordner 3. Er liegt dort
  als Kopie vor. Änderungen am Parser müssen deshalb in Ordner 1 und in Ordner 3
  gemacht werden.
- Zum Projekt gibt es vier Präsentationen: zur Python-Pipeline mit fünf
  Methoden (29.05.2026), zum gemeinsamen Driver mit acht Varianten
  (07.07.2026), zum Vergleich der sieben Java-Werkzeuge (21.09.2026) und zu
  `javauml` im Vergleich mit IntelliJ (03.11.2026). Sie liegen noch nicht in
  diesem Projekt und werden noch hinzugefügt.

## Probleme und Lösungen

| Problem | Phase | Lösung |
| :--- | :--- | :--- |
| Lokale Hardware reicht nur für Modelle bis etwa 24 Milliarden Parameter | 0 | Wechsel zu Modellen über die API, lokale Modelle nur noch optional über Ollama |
| Modelle halten das JSON-Format nicht ein | 0 und 1 | Validator, der fehlerhafte Diagramme repariert, ein Wiederholversuch mit Korrekturhinweis und Tools statt freier Textantworten |
| Wachsender Kontext durch wiederholte Tool-Aufrufe | 1 und 2 | gemeinsames Budget, Hinweis abhängig vom Restbudget, ein Tool für Klassen und Linien, Lesezugriff erst nach einem Entwurf, optionale Zusammenfassung des Verlaufs |
| Fünf Methoden schlecht vergleichbar | 1 | ein Driver, acht Varianten mit gleichen Prompts und Budgets |
| Testprojekte zu klein für belastbare Aussagen | 2 | Suche nach größeren Datensätzen mit Diagrammen |
| Kaum UML-Datensätze für Python | 3 | Wechsel zu Java |
| Vorhandene Java-Werkzeuge scheitern an fehlenden Bibliotheken, Encoding oder neuer Syntax | 3 | eigener Parser auf Grundlage von tree-sitter |
| Vergleich über Kurznamen verdeckt Fehler bei gleichnamigen Klassen | 3 | eigene Prüfung der Namensauflösung, mehrdeutige Fälle werden gemeldet statt geraten |
| Referenzdiagramme weichen teilweise vom Code ab | 4 | Fallstudien am Code. Die Werte zeigen die Übereinstimmung mit dem Diagramm und sagen nichts über die Korrektheit |
| Parser sieht keine Verbindungen über Methodenaufrufe | 5 | IntelliJ-Modus: Methodeninhalte lesen und den Typ jedes Zwischenergebnisses in Aufrufketten bestimmen |

## Offene Punkte

- Läufe mit einem echten LLM auf Java-Projekten und Vergleich mit den
  Diagrammen von Zhang/Hebig.
- Festlegen, wie die Qualität eines Diagramms gemessen wird: Vergleich mit einer
  Referenz, Bewertung durch Menschen oder Bewertung durch ein LLM. Diese Frage
  ist seit der ersten Präsentation im Mai 2026 offen.

## Begriffe

Zum Nachschlagen, alphabetisch. Die anderen Dokumente verweisen hierher.

| Begriff | Bedeutung |
| :--- | :--- |
| Abhängigkeit | Eine Klasse benutzt eine andere irgendwo im Code, etwa als Rückgabewert oder in einem Aufruf. Im UML-Diagramm eine gestrichelte Linie mit offenem Pfeil. |
| Abstraktion, abstraktes Diagramm | Weglassen des Unwichtigen. Ein abstraktes Klassendiagramm zeigt nur die zentralen Klassen und Beziehungen. |
| Agent | Ein LLM, das in mehreren Schritten selbstständig Tools aufruft, die Ergebnisse liest und danach entscheidet, was es als Nächstes tut. |
| API | Schnittstelle, über die ein Programm ein anderes benutzt. Hier: der Zugang zu einem Sprachmodell beim Anbieter über das Internet, bezahlt nach Token. |
| Assoziation, Aggregation, Komposition | Drei Arten von "hat"-Beziehungen in UML. Assoziation: kennt ein anderes Objekt (Linie). Aggregation: hat andere Objekte als Teil, die auch allein existieren könnten (leere Raute). Komposition: Teile gehören fest zum Ganzen (gefüllte Raute). |
| Auflösung (eines Namens) | Herausfinden, welche Klasse mit einem Namen im Code gemeint ist. Steht dort `Kunde`, prüft der Parser über Paket und Imports, ob `de.firma.model.Kunde` oder eine andere Klasse dieses Namens gemeint ist. |
| Attribut, Feld | Datum, das sich ein Objekt einer Klasse merkt, etwa der Titel eines Buches. In Java heißt es Feld. |
| Benchmark | Festgelegter Vergleichstest. Alle Werkzeuge bekommen dieselben Eingaben und werden gleich bewertet. |
| Bibliothek (im Programmiersinn) | Fertiger, fremder Code, den ein Projekt benutzt, etwa für Fenster oder Datenbanken. |
| Budget | Obergrenze für die Textmenge (in Token), die ein Lauf verbrauchen darf. |
| Build, kompilieren, Bytecode, Compiler | Java-Code wird vor dem Ausführen vom Compiler in Bytecode übersetzt. Diesen Vorgang nennt man kompilieren oder bauen (Build). Er klappt nur, wenn alle benutzten Bibliotheken vorhanden sind. |
| Cluster | Gruppe eng miteinander verbundener Dateien oder Klassen. |
| Commit | Ein gespeicherter Zwischenstand eines Projekts in der Versionsverwaltung Git. |
| Branch, Tag | Ein Branch ist ein Entwicklungszweig in Git, ein Tag ein benannter fester Stand, etwa eine Versionsnummer. |
| Deklaration | Die Stelle im Code, an der eine Klasse, ein Feld oder eine Methode angekündigt wird, mit Name und Typ. Der Code, der in einer Methode ausgeführt wird, gehört nicht dazu. |
| Docker, Image, Container, Compose | Docker liefert eine fertig eingerichtete Umgebung als Paket (Image). Ein laufendes Image heißt Container. Compose ist der Teil von Docker, der beschreibt, wie der Container gestartet wird. Man muss dann nichts einzeln installieren. | Programm, das eine fertig eingerichtete Umgebung in einem Paket (Image) liefert. Man muss dann nichts einzeln installieren. |
| Driver | Das Steuerprogramm in Ordner 1, das das LLM Schritt für Schritt durch einen Lauf führt. |
| Encoding | Die Art, wie Buchstaben als Bytes gespeichert werden. Ältere Dateien speichern Umlaute oft anders (ISO-8859-1, CP1252) als heute üblich (UTF-8). |
| Extraktor | In Ordner 2 der Oberbegriff für Werkzeuge, die aus Code ein Klassendiagramm erzeugen. Der eigene Parser ist einer davon. |
| F1, Micro-F1, Macro-F1 | Gemeinsamer Wert aus Precision und Recall zwischen 0 und 1. Micro-F1 zählt alle Treffer aller Projekte zusammen, Macro-F1 mittelt die Werte der einzelnen Projekte. Siehe [Wie man prüft](#wie-man-prüft-ob-ein-diagramm-gut-ist). |
| Feintuning | Zusätzliches Training eines fertigen Modells mit Beispielen für eine bestimmte Aufgabe. |
| Graph, Knoten, Kante | Ein Graph besteht aus Punkten (Knoten) und Verbindungen (Kanten). Im Klassengraphen sind die Klassen die Knoten und die Beziehungen die Kanten. |
| Ground Truth, Referenz | Die als richtig angenommene Lösung, mit der verglichen wird. |
| Harness | Das Programm um ein Sprachmodell herum, das ihm Aufgaben stellt, Werkzeuge gibt und seine Antworten prüft. |
| Importgraph | Wer benutzt wen auf der Ebene von Dateien oder Paketen. |
| IntelliJ IDEA | Weit verbreitete kommerzielle Programmierumgebung, die Klassendiagramme aus Code zeichnen kann. |
| Interface, Schnittstelle, Realisierung | Ein Interface legt fest, was eine Klasse können muss, ohne zu sagen, wie. Eine Klasse, die das erfüllt, "realisiert" das Interface (Java: `implements`). In UML eine gestrichelte Linie mit Dreieck. |
| Java, Python | Zwei verbreitete Programmiersprachen. |
| JDK | Java Development Kit, die Grundausstattung zum Übersetzen und Ausführen von Java, mit der Standardbibliothek (`List`, `String` und so weiter). |
| JSON | Textformat für strukturierte Daten, das Programme leicht lesen und schreiben können. |
| Klasse, Methode | Eine Klasse beschreibt eine Art von Ding im Programm. Methoden sind die Handlungen, die sie ausführen kann. |
| Klassendiagramm | Zeichnung der Klassen eines Programms als Kästen und ihrer Beziehungen als Linien, nach den Regeln der UML. |
| JVM | Java Virtual Machine, das Programm, das Java-Bytecode ausführt. Ihr Start kostet jedes Mal etwas Zeit. |
| Kommandozeile, Terminal | Ein Fenster, in das man Befehle als Text eintippt, statt zu klicken. |
| Konstantenpool | Ein Verzeichnis im Bytecode jeder Java-Klasse, das unter anderem alle Klassen nennt, auf die sie verweist. |
| Kontextfenster | Die größte Textmenge, die ein Sprachmodell auf einmal verarbeiten kann. |
| Korpus | Die Sammlung von Projekten, auf der gemessen wird. |
| Lambda | Eine kurze, namenlose Funktion, die direkt an der Stelle steht, wo sie gebraucht wird. |
| LLM | Large Language Model, großes Sprachmodell. Ein mit sehr viel Text trainiertes Programm, das Text versteht und erzeugt. |
| Modul (Build-Modul) | Ein Teilprojekt in einem größeren Java-Projekt, das für sich gebaut wird. Zwei Module können Klassen mit gleichem Namen haben. |
| Normalisierung | Das Angleichen von Daten vor dem Vergleich. Hier vor allem: Assoziation, Aggregation und Komposition werden zu einer Beziehungsart zusammengefasst, weil Menschen und Werkzeuge sie sehr unterschiedlich verwenden. |
| Open Source | Software, deren Code frei verfügbar ist. |
| Paket | Ordner, in dem zusammengehörige Klassen liegen. |
| Parameter (eines Modells) | Die einstellbaren Zahlen in einem Sprachmodell. Ihre Anzahl ist ein grobes Maß für die Größe des Modells. |
| Parser | Programm, das Text in einer festen Sprache (hier Programmcode) einliest und seinen Aufbau erkennt. |
| Pipeline | Kette von Verarbeitungsschritten, bei der jeder Schritt das Ergebnis des vorigen weiterverarbeitet. |
| PlantUML | Textformat für Diagramme und das Programm, das daraus Bilder (PNG, SVG) zeichnet. |
| Precision, Recall | Precision: Anteil der ausgegebenen Elemente, die richtig sind. Recall: Anteil der richtigen Elemente, die gefunden wurden. |
| Prompt | Die Anweisung oder Frage, die man einem Sprachmodell schickt. |
| Quellcode, Quelltext | Der von Menschen geschriebene Programmtext. |
| Replikationspaket | Daten und Material, das die Autoren einer Studie veröffentlichen, damit andere die Ergebnisse nachprüfen können. |
| Rendern | Aus einem Diagramm in Textform (PlantUML) ein Bild erzeugen. |
| Repository, Repo | Ordner eines Softwareprojekts mit allen Dateien und seiner Versionsgeschichte, oft auf GitHub. |
| Seed | Startwert für den Zufall. Gleicher Seed ergibt bei vielen Programmen dieselbe Folge von Zufallszahlen. |
| Statische Analyse | Untersuchung von Code, ohne ihn auszuführen. |
| Stereotyp | Eine Zusatzangabe an einem Klassenkasten in UML, etwa `«interface»` oder `«enum»`, die sagt, was für eine Art Klasse das ist. |
| Test, Testcode | Kleine Prüfprogramme, die automatisch kontrollieren, ob der eigentliche Code das Erwartete tut. Sie gehören zum Projekt, aber nicht zu dem, was es fachlich macht, und werden deshalb im Diagramm weggelassen. |
| Token | Wortstück, in dem Sprachmodelle Text zählen, im Englischen etwa vier Buchstaben. Grenzen und Kosten werden in Token gemessen. |
| Tool | Befehl, den ein LLM während eines Laufs aufrufen darf, etwa um eine Datei zu lesen oder das Diagramm zu ändern. |
| Transitive Verbindung | Verbindung über einen Umweg: A benutzt B, und über B erreicht A die Klasse C. |
| Trockenlauf | Probelauf, bei dem statt des Sprachmodells ein Platzhalter mit festen Antworten läuft. Prüft das Zusammenspiel, nicht die Qualität. |
| Umgebungsvariable | Ein benannter Wert, den man im Terminal setzt und den Programme lesen können, etwa der API-Schlüssel. |
| UML | Unified Modeling Language, eine genormte Zeichensprache für Software. |
| Validator | Prüfprogramm, das fehlerhafte Diagramme erkennt und repariert. |
| Variante | Eine der acht Arten, wie das LLM in der Pipeline arbeitet (leer anfangen oder streichen, was es zu Beginn sieht, ob es Code lesen darf). |
| Vererbung | Eine Klasse ist eine besondere Art einer anderen (Java: `extends`). Ein Roman ist ein Buch. In UML eine durchgezogene Linie mit Dreieck. |
