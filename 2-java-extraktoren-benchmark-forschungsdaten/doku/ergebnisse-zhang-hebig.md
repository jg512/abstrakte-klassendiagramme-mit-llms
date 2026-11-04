# Ergebnisse: sieben Extraktoren auf der Zhang/Hebig-Suite

Verglichen wurden sieben Werkzeuge, die aus Java-Code ein UML-Klassendiagramm
erzeugen, auf den neun Projekten aus dem Replikationspaket von Zhang, Zhang,
Strüber und Hebig (SoSyM 2025). Als Referenz dienen die von den Autoren von Hand
abstrahierten Diagramme mit 79 Klassen und 79 Beziehungen (nach Normalisierung).

Gemessen wird die Übereinstimmung mit den gezeichneten Diagrammen. Ein niedriger
Wert bedeutet nicht unbedingt, dass der Parser einen Fehler hat.

javalang unterstützt nur Java 8. Die 72 ausgewerteten Dateien enthalten aber
keine Records, kein `sealed`, kein `var`, keine `switch`-Ausdrücke mit Pfeil und
keine Textblöcke, auch nicht in Orekit und Artemis. Dass javalang auf allen neun
Projekten lief, sagt also nichts darüber aus, ob es mit neuerem Java zurechtkommt.

## Gesamtergebnis

| Werkzeug | liest | lief auf | Knoten | Kanten | Precision | Recall | F1 | Zeit |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| eigener Extraktor (tree-sitter) | Quelltext | 9/9 | 73/79 | 53/79 | 0,757 | 0,671 | 0,711 | 0,4 s |
| javalang 0.13.0 + Adapter | Quelltext | 9/9 | 73/79 | 53/79 | 0,757 | 0,671 | 0,711 | 0,8 s |
| java2plantuml (mirajp1) | Quelltext | 9/9 | 73/79 | 43/79 | 0,827 | 0,544 | 0,656 | 7,4 s |
| jdeps (JDK) | Bytecode | 3/9 | 29/79 | 24/79 | 0,471 | 0,304 | 0,369 | 3,1 s |
| plantuml-generator 2.3.0 | Bytecode | 2/9 | 19/79 | 16/79 | 0,762 | 0,203 | 0,320 | 3,9 s |
| Java2PlantUML (juanmf) | Bytecode | 2/9 | 19/79 | 10/79 | 1,000 | 0,127 | 0,225 | 29,8 s |
| genuml 0.6.1 | Bytecode | 3/9 | 15/79 | 0/79 | – | 0,000 | 0,000 | 158,0 s |

"lief auf" zählt die Projekte mit verwertbarer Ausgabe. "Knoten" und "Kanten"
sind die Treffer innerhalb des Modellumfangs, summiert über alle neun Projekte.

## Nur die drei kompilierbaren Projekte

RaiseMeUp, NeurophChanges und PatrickFromTheMOOC enthalten zusammen 34 Klassen
und 39 Beziehungen. Auf diesen drei Projekten laufen auch die
Bytecode-Werkzeuge, deshalb lässt sich hier vergleichen, wie gut sie
analysieren, wenn sie überhaupt laufen.

| Werkzeug | liest | lief auf | Knoten | Kanten | Precision | Recall | F1 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| eigener Extraktor | Quelltext | 3/3 | 29/34 | 25/39 | 0,806 | 0,641 | 0,714 |
| javalang + Adapter | Quelltext | 3/3 | 29/34 | 25/39 | 0,806 | 0,641 | 0,714 |
| java2plantuml (mirajp1) | Quelltext | 3/3 | 29/34 | 18/39 | 1,000 | 0,462 | 0,632 |
| jdeps | Bytecode | 3/3 | 29/34 | 24/39 | 0,471 | 0,615 | 0,533 |
| plantuml-generator | Bytecode | 2/3 | 19/34 | 16/39 | 0,762 | 0,410 | 0,533 |
| Java2PlantUML (juanmf) | Bytecode | 2/3 | 19/34 | 10/39 | 1,000 | 0,256 | 0,408 |
| genuml | Bytecode | 3/3 | 15/34 | 0/39 | – | 0,000 | 0,000 |

Im Vergleich zu allen neun Projekten:

- jdeps steigt von F1 0,369 auf 0,533 und hat mit 0,615 einen höheren Recall als
  java2plantuml (0,462). Die Precision ist mit 0,471 niedrig, weil jdeps Kanten
  ohne Typ aus dem Konstantenpool liefert.
- plantuml-generator steigt von 0,320 auf 0,533, Java2PlantUML (juanmf) von 0,225
  auf 0,408.
- java2plantuml hat hier eine Precision von 1,000 bei einem Recall von 0,462: Alle
  18 gefundenen Kanten sind richtig, 21 fehlen.
- Der eigene Extraktor und javalang verändern sich kaum (0,711 auf 0,714). Die
  drei kompilierbaren Projekte sind für sie also nicht einfacher als die anderen.
- genuml bleibt bei 0,000, weil es grundsätzlich keine Beziehungen ausgibt.

## Warum die Bytecode-Werkzeuge kaum laufen

Diese Werkzeuge brauchen kompilierten Code, das Replikationspaket enthält aber
nur Quelltext. Jedes Projekt wurde deshalb einmal mit `javac` kompiliert, mit
allen JARs aus dem Projekt und 41 zusätzlichen Bibliotheken aus
`werkzeuge/extra/jars/` (siehe `werkzeuge.md`).

| Projekt | javac | Quelldateien | class-Dateien | Grund für den Fehler |
| --- | --- | ---: | ---: | --- |
| ZooTypers | Fehler | 14 | 0 | generierte Android-Klasse `R` fehlt |
| RaiseMeUp | OK | 40 | 158 |  |
| EAPLI_PL_2NB | Fehler | 51 | 0 | `sun.security.jca` ist im Modulsystem nicht zugänglich |
| FreeDaysIntern | Fehler | 78 | 0 | Spring-Roo-Annotationen, `javax.validation` |
| NeurophChanges | OK | 173 | 158 |  |
| PatrickFromTheMOOC | OK | 18 | 32 |  |
| myblog | Fehler | 7 | 0 | Symbole lassen sich nicht auflösen |
| Orekit | Fehler | 1711 | 18 | braucht Hipparchus 3.1-SNAPSHOT, veröffentlicht ist nur 3.0 |
| Artemis | Fehler | 1582 | 0 | Spring Boot, jHipster |

Die Spalte "Quelldateien" zählt nur die Verzeichnisse, in denen Klassen aus dem
Modell liegen, nicht das ganze Projekt. Bei Orekit entstehen 18 class-Dateien,
bevor `javac` abbricht. Diese wurden nicht verwendet, weil unvollständiger
Bytecode nicht vergleichbar wäre.

Nur 3 von 9 Projekten lassen sich kompilieren. Auch dann laufen nicht alle
Werkzeuge: Bei NeurophChanges scheitern beide PlantUML-Generatoren beim Laden der
Klassen (`NoClassDefFoundError` bei `AbstractMapEntry` bzw. bei einer
Hibernate-Klasse, die im Projekt fehlt).

## Gefundene Beziehungen pro Projekt

| Projekt | Referenz | eigener Extraktor | javalang 0.13.0 | java2plantuml | jdeps | plantuml-generator 2.3.0 | Java2PlantUML | genuml 0.6.1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ZooTypers | 5 | 2 | 2 | 2 | – | – | – | – |
| RaiseMeUp | 22 | 8 | 8 | 6 | 9 | 8 | 6 | 0 |
| EAPLI_PL_2NB | 7 | 5 | 5 | 4 | – | – | – | – |
| FreeDaysIntern | 7 | 7 | 7 | 6 | – | – | – | – |
| NeurophChanges | 9 | 9 | 9 | 8 | 9 | – | – | 0 |
| PatrickFromTheMOOC | 8 | 8 | 8 | 4 | 6 | 8 | 4 | 0 |
| myblog | 10 | 6 | 6 | 5 | – | – | – | – |
| Orekit | 5 | 2 | 2 | 2 | – | – | – | – |
| Artemis | 6 | 6 | 6 | 6 | – | – | – | – |

`–` heißt, dass das Werkzeug für dieses Projekt keine verwertbare Ausgabe hatte.
