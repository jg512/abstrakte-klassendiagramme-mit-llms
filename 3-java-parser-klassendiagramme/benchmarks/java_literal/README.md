**Deutsch** · [English](README.en.md)

# Benchmark: Klassengraphen aus modernem Java

Ein Benchmark ist ein festgelegter Test, der bei jedem Lauf dieselben Eingaben
bekommt. Diese Suite (Sammlung von Testfällen) prüft, ob der Java-Parser die
Klassen und Beziehungen innerhalb eines Projekts genau so ausliest, wie sie im
Code stehen. Im Unterschied zum Benchmark in [Ordner
2](../../../2-java-extraktoren-benchmark-forschungsdaten/README.md) ist die
Referenz hier also kein abstrahiertes, von Menschen gezeichnetes Diagramm.
Verglichen wird mit dem, was nachweislich im Code steht.

Die Suite besteht aus 20 kleinen, voneinander unabhängigen Projekten mit
jeweils wenigen Zeilen Code. Jedes prüft einen bestimmten Fall. Abgedeckt
sind direkte Felder, Arrays, Standard- und eigene Generics, `Optional`, Maps,
Records, Sealed-Typen, verschachtelte Typen, Imports, Vererbung zwischen
Interfaces, Realisierung, Selbstbeziehungen, Komposition, Kardinalitäten aus
JPA-Annotationen und die optionalen Methodenabhängigkeiten.

Die erwarteten Graphen in `manifest.json` wurden von Hand anhand der
Codebeispiele geprüft. Die Begriffe erklärt das
[Haupt-README](../../../README.md#begriffe), die Java-Begriffe die [Beschreibung
des
Parsers](../../../1-llm-pipeline-abstrakte-klassendiagramme/doku/java-parser.md#begriffe-aus-java-die-hier-vorkommen).
Die Suite läuft als Teil der normalen Tests mit und lässt sich auch einzeln
starten (im Ordner `3-java-parser-klassendiagramme`):

```bash
.venv/bin/python -m benchmarks.java_literal.run --output benchmarks/java_literal/results.json
```

Aktuell bestehen alle 20 Fälle (`results.json`). Die Suite braucht keinen
Build und liefert bei jedem Lauf dasselbe Ergebnis.
