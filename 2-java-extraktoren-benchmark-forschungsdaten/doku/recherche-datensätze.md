# Recherche: Datensätze mit Java-Code und passenden Klassendiagrammen

Die Recherche fand am 20.09.2026 statt. Gesucht waren Java-Projekte, zu denen
ein Klassendiagramm oder Klassengraph existiert. Ziel waren 20 bis 50 Projekte,
mindestens aber 20 brauchbare Paare aus Code und Diagramm.

## Lindholmen-Datensatz

Robles, Ho-Quang, Hebig, Chaudron und Fernandez, *An extensive dataset of UML
models in GitHub*, MSR 2017. Davor erschien Hebig et al., *The Quest for Open
Source Projects that Use UML: Mining GitHub*, MODELS 2016.

- Paper: https://research.chalmers.se/en/publication/251818
- Spiegel an der Uni Rostock mit Downloads:
  https://se.informatik.uni-rostock.de/forschung/datensaetze-und-tools/mirror-lindholmen-datensatz/
- Der Index umfasst über 93.000 UML-Dateien in über 24.000 Repos. Davon sind
  nicht alle Java-Projekte oder Klassendiagramme, und manche Repos sind nicht
  mehr erreichbar.
- Verwendet wurden nur maschinenlesbare `.uml`- und `.xmi`-Dateien. Quelltext und
  Diagramm stammen jeweils aus demselben Commit.
- Die 30 Projekte sind eine eigene Auswahl aus diesem Datensatz und kein
  veröffentlichter Goldstandard. Die Modelle können von Hand entworfen, per
  Reverse Engineering oder zusammen mit dem Code erzeugt worden sein, und sie
  können unvollständig oder veraltet sein.

Die Auswahl lässt sich reproduzieren. Die Indexeinträge wurden nach Repo
gruppiert, dabei wurden nur Repos mit höchstens zehn XML-Modellen berücksichtigt
und jeweils das Modell mit dem kürzesten Pfad genommen. Die Liste wurde mit dem
Seed 20260920 gemischt und 1.200 Repos wurden geprüft. Übernommen wurden die
ersten 220 Modelle mit 3 bis 200 Typen und mindestens einer Beziehung. Die
Downloads waren auf 15 MB pro Archiv, 40 MB entpackt und 3 bis 1.500
Java-Dateien begrenzt. Durch diese Grenzen sind kleinere Projekte in der
Auswahl überrepräsentiert. Alle Fehlschläge und Ausschlüsse sind gespeichert.

Für jedes Paar müssen mindestens drei Klassen eindeutig zwischen Modell und
Quelltext zugeordnet werden können, und zwischen ihnen muss mindestens eine
Beziehung bestehen. Die Namen müssen sowohl im Modell als auch im Java-Code
eindeutig sein. Die Klassen im Quelltext wurden mit javalang erfasst, das nur
Java 8 unterstützt. Die Auswahl enthält deshalb eher ältere Projekte. Alle
Extraktoren bekommen dieselbe Dateiliste, und der heruntergeladene Code wurde
nie ausgeführt.

## Zhang et al. 2025

Wenli Zhang, Weixing Zhang, Daniel Strüber und Regina Hebig, *An empirical study
of manual abstraction between class diagrams and code of open-source systems*,
Software and Systems Modeling 24 (2025), https://doi.org/10.1007/s10270-025-01289-y

- Replikationspaket:
  https://osf.io/p4jdr/?view_only=34b153d3b7704f4a84befd661dc9c6a1
- Neun Java-Projekte: ZooTypers, RaiseMeUp, EAPLI PL 2NB, FreeDaysIntern,
  Neuroph, PatrickFromTheMOOC, myblog, Orekit und Artemis.
- Das Paket enthält die untersuchten Versionen der Projekte (Archiv mit
  331.030.607 Bytes), die ursprünglichen und die annotierten Modelle, per Reverse
  Engineering mit IntelliJ erzeugte Diagramme und neun Vergleichstabellen.
- Die Autoren haben die Modellelemente von Hand dem Code zugeordnet und
  festgehalten, was ausgelassen, ersetzt, verschoben oder ungenau dargestellt
  wurde. Damit eignet sich das Paket gut, um zu untersuchen, wie Menschen beim
  Zeichnen von Klassendiagrammen abstrahieren.
- Neun Projekte reichen allein nicht für die angestrebten 20. Deshalb werden
  beide Datensätze verwendet: die 30 Lindholmen-Projekte für die Breite und die
  neun Projekte von Zhang/Hebig als sorgfältig aufbereitete Ergänzung.
- Sieben der neun Projekte stammen ursprünglich aus Lindholmen, zwei wurden über
  eine Suche nach PlantUML-Repos gefunden. Die beiden Datensätze überschneiden
  sich also teilweise.

Für die Pipeline ist dieser Datensatz besonders interessant. Ein Extraktor kann
den Code korrekt lesen und trotzdem vom Diagramm abweichen, weil im Diagramm
bewusst Klassen, Member oder Beziehungen weggelassen wurden. Im Benchmark wird
nur die Extraktion innerhalb des Umfangs bewertet, den die Autoren modelliert
haben. Die Annotationen der Autoren können später genutzt werden, um die
Abstraktion durch das LLM zu bewerten.

## Weitere geprüfte Quellen

| Paper / Quelle | Inhalt | Entscheidung |
| --- | --- | --- |
| Campanello et al., *On the Use of GPT-4 in the Reverse Engineering of Class Diagrams*, JOT 2025, https://www.jot.fm/issues/issue_2025_02/a14.pdf | Fünf größere Java-Projekte mit korrigierten, von Menschen abstrahierten Diagrammen. Material: https://github.com/sh4r10/thesis-autogen-classdiagrams/tree/revision | Überschneidet sich mit der Studie von Zhang et al. |
| Siala und Lano, *Using LLMs to extract UML class diagrams from Java and Python programs: an empirical study*, STAF 2025, https://ceur-ws.org/Vol-4122/paper12.pdf | 14 Java-Beispiele mit generierten Referenzmodellen. Download-Liste unter https://zenodo.org/api/records/15108621 | Zu wenige und zu kleine Beispiele. |
| Siala und Lano, *Leveraging LLMs for abstracting UML and OCL representations from Java and Python programs*, JSS 2026, https://doi.org/10.1016/j.jss.2026.112874 | 2.560 Java/UML-Paare, größtenteils konstruierte oder generierte Beispiele, davon 66 aus dem Internet. Referenzen mit Java2JSON erzeugt. | Eher für Parser-Tests interessant, keine echten Projekte. Das vollständige Archiv wurde nicht geprüft. |
| Naboichenko und Peinl, *Unlocking UML Class Diagram Understanding in Vision Language Models*, 2026, https://arxiv.org/abs/2605.11634 | Aus Java-Repos generierte Diagramme mit Fragen und Antworten: https://huggingface.co/datasets/iisys-hof/uml-class-diagrams | Die zugehörigen Java-Projekte sind nicht enthalten. |
| Palladio-Retriever-Benchmark, https://github.com/PalladioSimulator/Palladio-ReverseEngineering-Benchmark | Viele Repos mit generierten Architekturmodellen, teilweise manuell erstellte Referenzen. | Enthält Komponenten-, System- und Verteilungssichten, aber keine Klassendiagramme. |
| Golden UML ModelSet, https://golden-uml-modelset.vercel.app/ | 45 fachliche Beschreibungen mit Klassendiagrammen. | Keine Java-Implementierung vorhanden. |

## Regeln der Auswertung

- Gemessen wird die Übereinstimmung mit dem Diagramm, nicht die Korrektheit des
  Extraktors.
- Bewertet werden nur die Klassen aus dem Modell, die sich eindeutig einer Klasse
  im Quelltext zuordnen lassen. Nicht zugeordnete Klassen und Kanten werden
  trotzdem gespeichert.
- Vererbung und Realisierung werden getrennt und mit Richtung verglichen.
  Assoziation, Aggregation und Komposition werden zu einer ungerichteten
  Assoziation zusammengefasst. Multiplizität, Rollennamen und Besitz werden nicht
  bewertet.
- Attribute, deren Typ eine Klasse aus dem Modell ist, zählen als Assoziation.
  Doppelte Beziehungen werden nur einmal gezählt. Nicht unterstützte Beziehungen
  werden protokolliert.
- Die Graphen der Werkzeuge werden auf denselben Umfang wie die Referenz
  beschränkt. Der Knoten-Recall zeigt Fehler bei der Extraktion, die
  Knoten-Precision ist in diesem eingeschränkten Umfang wenig aussagekräftig.
- Fehlgeschlagene Läufe werden gemeldet, auch wenn das Werkzeug Erfolg gemeldet,
  aber keine brauchbare Ausgabe erzeugt hat. Sie gehen mit einer leeren Ausgabe
  in die Gesamtwerte ein.
- Ein niedriger Wert bedeutet nicht automatisch, dass ein Extraktor falsch
  liest. Abweichungen wurden am Quelltext geprüft, bevor der Extraktor geändert
  wurde.
- Verglichen werden der tree-sitter-Extraktor der Pipeline, javalang 0.13.0 mit
  einem eigenen Adapter und mirajp1/java2plantuml (JavaParser 3.4.0). javalang ist
  nur ein Parser und braucht den Adapter, um einen Klassengraphen zu erzeugen.
