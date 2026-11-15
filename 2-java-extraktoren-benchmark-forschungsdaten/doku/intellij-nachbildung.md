**Deutsch** · [English](intellij-nachbildung.en.md)

# Nachbildung der IntelliJ-Klassendiagramme

Stand 23.10.2026.

IntelliJ IDEA ist eine weit verbreitete Programmierumgebung, die aus Java-Code
automatisch Klassendiagramme zeichnen kann. Diese Datei beschreibt, nach welchen
Regeln IntelliJ dabei vorgeht, wie der eigene Parser das nachbildet und wie gut
das gelingt: Bei sieben von neun Projekten ist das Ergebnis Linie für Linie
gleich. Fachbegriffe erklärt das [Haupt-README](../../README.md#begriffe).

Kommerzielle UML-Werkzeuge zeigen Verbindungen, die der eigene Extraktor bisher
nicht gesehen hat. Der Extraktor las nur Felder, `extends` und `implements`.
IntelliJ liest außerdem die Methodenrümpfe und zeigt dadurch auch Verbindungen,
die über eine dritte Klasse laufen. Ziel war, dass der Extraktor für dieselben
Klassen dasselbe Diagramm erzeugt wie IntelliJ.

Als Vorlage dienen die neun Diagramme, die Zhang/Hebig mit IntelliJ per Reverse
Engineering erzeugt haben (`daten/zhang-hebig/models/reverse/`).

## Beispiel für eine transitive Verbindung

Transitiv heißt: Die Verbindung läuft über einen Umweg, über eine dritte Klasse.

In RaiseMeUp zeichnet IntelliJ eine Abhängigkeit von `PetObserver` zu `Job`.
`PetObserver` hat kein Feld vom Typ `Job` und importiert `Job` nicht einmal. Es
ruft aber `RaiseMeUp.getCurrentJob().getImpactenergy()` auf. `getCurrentJob()`
gibt ein `Job` zurück, und `getImpactenergy()` ist in `Job` deklariert. Damit
hängt `PetObserver` über `RaiseMeUp` von `Job` ab.

Eine zweite Form steckt in der Vererbung. In Orekit implementiert
`AdaptedStepInterpolator` das Interface `OrekitStepInterpolator`, das nicht im
Diagramm steht. Dessen Obertyp `PVCoordinatesProvider` steht drin, und IntelliJ
zeichnet die Realisierung direkt dorthin.

## Regeln

Die Regeln wurden aus den neun Bildern abgeleitet und am Quelltext geprüft. Die
Spalte "Darstellung" beschreibt, wie die Linie im IntelliJ-Bild aussieht. Ein
Cast ist eine Umwandlung in einen anderen Typ, `instanceof` die Frage "ist
dieses Objekt vom Typ X?". Eine Schleife ist eine Linie, die von einer Klasse
zu ihr selbst zurückführt.

| Kante | Wann IntelliJ sie zeichnet | Darstellung |
| --- | --- | --- |
| Vererbung | `extends`. Steht der Obertyp nicht im Diagramm, geht die Linie zum nächsten Obertyp, der drinsteht | durchgezogen, Dreieck |
| Realisierung | `implements`, ebenfalls über nicht gezeigte Typen hinweg | gestrichelt, Dreieck |
| Feld | Feld (auch `static`), dessen Typ eine Klasse im Diagramm ist | durchgezogen, Raute beim Besitzer, "1" an beiden Enden, Feldname am Ziel |
| Feld mit vielen Elementen | Array oder Collection aus dem JDK (`List`, `Set`, ...) bzw. eigene Klasse, die von einer solchen erbt. `Map` zählt nicht | wie oben, "*" am Ziel |
| Innere Klasse | Klasse, die in einer anderen Klasse im Diagramm deklariert ist | rote Linie mit Kreis und Plus |
| Abhängigkeit | jeder Verweis im Code: Typen in Signaturen, Feldern, lokalen Variablen, Casts, `instanceof`, Klassenliterale (`X.class`), statische Zugriffe über den Klassennamen und Methodenaufrufe, auch über Aufrufketten. Ein Methodenaufruf zählt für die Klasse, die die Methode deklariert | gestrichelt, offener Pfeil |
| `«create»` | `new X(...)` irgendwo in der Klasse | gestrichelt mit `«create»` |
| Schleife | die Klasse ruft eigene Methoden auf oder benutzt ihren eigenen Typ (Cast, `instanceof`, Rückgabetyp) | gestrichelte Schleife |

Dazu kommen drei Ausnahmen:

- Lesen und Schreiben von Feldern erzeugt keine Abhängigkeit. `EvaluationReview`
  in PatrickFromTheMOOC benutzt nur eigene Felder und hat keine Schleife.
- Eine einfache Abhängigkeit wird weggelassen, wenn zwischen denselben Klassen in
  derselben Richtung schon eine Vererbung, Realisierung oder Feldbeziehung
  besteht, oder wenn eine innere Klasse ihre äußere benutzt.
- `«create»` wird immer gezeichnet, auch wenn es schon eine Feldbeziehung gibt.
  In ZooTypers hat `SinglePlayer` das Feld `model` und erzeugt es auch, im Bild
  stehen beide Linien.

Welche Klassen im Diagramm stehen, haben die Autoren in IntelliJ ausgewählt.
Diese Auswahl ist eine Eingabe und steht pro Projekt in `daten/intellij/projekte.json`.

## Umgebung pro Projekt

IntelliJ zeichnet nur, was es auflösen kann, und das hing davon ab, wie das
jeweilige Projekt geöffnet war. Das JDK ist die Grundausstattung von Java mit
Standardklassen wie `List`. Das Source-Root ist der Ordner, den IntelliJ als
Anfang des Quellcodes ansieht. Zwei Fälle kommen vor:

- Kein JDK eingerichtet: IntelliJ kennt dann `List`, `LinkedList` usw. nicht und
  zeichnet für Collection-Felder nur eine Abhängigkeit. Zu erkennen ist das an
  PatrickFromTheMOOC (fünf `LinkedList`-Felder ohne Linie) und EAPLI
  (`List<Income>` ohne Linie), während myblog und Neuroph für `Set` und `List`
  ein "*" zeigen.
- Falsch gesetztes Source-Root: IntelliJ findet dann Klassen aus demselben Paket
  nicht mehr, ausdrücklich importierte Klassen aber schon. In Artemis fehlen die
  drei Feldbeziehungen innerhalb eines Pakets, während alle Beziehungen über
  Paketgrenzen mit `import` gezeichnet sind. In FreeDaysIntern
  liegen alle Klassen in einem Paket, das Bild zeigt außer einer Schleife nichts.

| Projekt | JDK | Klassen aus demselben Paket |
| --- | --- | --- |
| ZooTypers | ja | ja |
| RaiseMeUp | ja | ja |
| EAPLI_PL_2NB | nein | ja |
| FreeDaysIntern | ja | nein |
| NeurophChanges | ja | ja |
| PatrickFromTheMOOC | nein | ja |
| myblog | ja | ja |
| Orekit | ja | ja |
| Artemis | ja | nein |

Bei FreeDaysIntern lässt sich nicht sagen, ob ein JDK eingerichtet war, weil
ohnehin nichts aufgelöst wurde.

## Abgleich

Das Skript `intellij_abgleich.py` baut für jedes Projekt das Diagramm und vergleicht es mit
den Kanten, die aus dem IntelliJ-Bild abgelesen wurden (`daten/intellij/referenz/`).
Die Ergebnisse stehen in `ergebnisse/messungen/intellij/`, die Diagramme als PlantUML und PNG
neben dem IntelliJ-Bild in `ergebnisse/diagramme-intellij/<Projekt>/`.

| Projekt | Kanten | Abschrift aus dem Bild | Übereinstimmung |
| --- | ---: | --- | --- |
| ZooTypers | 16 | vollständig | 16 von 16, keine zusätzlich |
| RaiseMeUp | 36 | vollständig | 36 von 36, keine zusätzlich |
| EAPLI_PL_2NB | 22 | vollständig | 22 von 22, keine zusätzlich |
| FreeDaysIntern | 1 | vollständig | 1 von 1, keine zusätzlich |
| PatrickFromTheMOOC | 18 | vollständig | 18 von 18, keine zusätzlich |
| myblog | 12 | vollständig | 12 von 12, keine zusätzlich |
| Artemis | 19 | vollständig | 19 von 19, keine zusätzlich |
| Orekit | 35 | teilweise (28 Kanten) | 28 von 28 |
| NeurophChanges | 103 | teilweise (16 Kanten) | 16 von 16 |

Wie die Abschriften entstanden sind:

- Bei sechs Projekten wurde jede Linie im Bild von Ende zu Ende nachverfolgt und
  mit der Ausgabe des Extraktors verglichen.
- Bei RaiseMeUp überlagern sich viele gestrichelte Linien. Dort wurden an jedem
  Kasten Anzahl und Art der ein- und ausgehenden Linien gezählt und mit den
  Beschriftungen abgeglichen. Alle 16 Kästen stimmen, die einzelnen gestrichelten
  Linien sind aber nicht alle von Ende zu Ende verfolgt.
- Bei Orekit sind alle Vererbungen, Realisierungen, inneren Klassen,
  Feldbeziehungen, die gezeigten `«create»` und die sichtbaren Schleifen geprüft.
- Bei Neuroph sind die Feldbeziehungen mit lesbarem Rollennamen und zwei
  `«create»` geprüft. Das Bild hat rund 100 Linien, die sich stark überlagern.

Die Abschriften wurden nach der Prüfung im Bild aus der Ausgabe des Extraktors
übernommen. Sie halten den geprüften Stand fest und zeigen bei späteren
Änderungen am Extraktor, ob sich etwas verschiebt.

## Offene Punkte

- Neuroph ist nur zu einem kleinen Teil gegen das Bild geprüft.
- In Orekit laufen im Bild mehrere gestrichelte Linien übereinander zu
  `AbstractPropagator`. Der Extraktor sagt vier Abhängigkeiten von inneren Klassen
  dorthin voraus, die sich im Bild nicht einzeln trennen lassen. Außerdem sagt er eine
  Schleife an `AbstractPropagator` voraus, die im Bild nicht zu sehen ist. Sie
  kann in den überlagerten Linien verborgen sein.
- Die beiden Umgebungsschalter sind aus den Bildern erschlossen. Dass IntelliJ
  bei Artemis ein falsches Source-Root hatte, ist eine Erklärung, die zu allen
  fehlenden Linien passt, aber nicht direkt belegt.
- Überladene Methoden werden nur über die Zahl der Argumente unterschieden.
  Lambdas ohne Typangabe, `var` mit schwer bestimmbarem Typ und Methoden aus
  Bibliotheken außer den gängigen JDK-Collections beenden eine Aufrufkette.

## Benutzung

In der Pipeline (Ordner 1):

```bash
python -m src /pfad/zum/repo --language java --java-relations intellij \
  --java-diagram-classes klassen.txt --java-member-profile full
```

`klassen.txt` enthält einen voll qualifizierten Klassennamen pro Zeile. Ohne diese
Datei kommen alle Klassen des Projekts ins Diagramm. `--java-ide-no-jdk` und
`--java-ide-no-same-package` bilden die beiden Umgebungsfälle nach. Das Ergebnis
steht wie gewohnt in `javagraph.json` und `javagraph.puml`.

Den Abgleich wiederholen (aus Ordner 2):

```bash
PYTHONPATH=../1-llm-pipeline-abstrakte-klassendiagramme \
  .venv/bin/python skripte/intellij_abgleich.py --render
```
