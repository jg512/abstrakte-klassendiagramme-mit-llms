**Deutsch** · [English](README.en.md)

# Kuratierte Suite nach Zhang/Hebig

Die Autoren dieser Studie haben für neun Java-Projekte untersucht, was Menschen
weglassen, wenn sie ein Klassendiagramm zu vorhandenem Code zeichnen. Ihr
veröffentlichtes Material (das Replikationspaket) dient in diesem Projekt als
sorgfältig aufbereitete ("kuratierte") Testsammlung. Fachbegriffe erklärt das
[Haupt-README](../../../README.md#begriffe).

Hier liegt das öffentliche Replikationspaket zu Wenli Zhang, Weixing Zhang,
Daniel Strüber und Regina Hebig, *An empirical study of manual abstraction
between class diagrams and code of open-source systems* (Software and Systems
Modeling, 2025).

- Paper: https://doi.org/10.1007/s10270-025-01289-y
- Paket: https://osf.io/p4jdr/?view_only=34b153d3b7704f4a84befd661dc9c6a1
- SHA-256 des Quellarchivs: `11db4e9a45affaf80df627fa6604119e0c56b47aef66e0e1ceae58086a13f85e`
- Größe des Quellarchivs: 331.030.607 Bytes, 6.268 Java-Dateien in neun Projekten

| Pfad | Inhalt |
| :--- | :--- |
| `Version(s) of Source Code Used/` | die neun Projekte in der untersuchten Version |
| `models/original/` | die ursprünglichen Klassendiagramme der Projekte |
| `models/annotated/` | dieselben Diagramme mit den Annotationen der Autoren (PDF) |
| `models/reverse/` | mit IntelliJ per Reverse Engineering erzeugte Diagramme (ausgepackt aus `downloads/reverse-models.zip`) |
| `comparisons/` | pro Projekt eine Vergleichstabelle der Autoren (xlsx) |
| `reference.json` | von Hand abgeschriebene Referenz: 79 Klassen und ihre Beziehungen |
| `manifest.json` | die 72 Quelldateien, die die Extraktoren als Eingabe bekommen, mit SHA-256 |

Die Autoren zählen 82 Beziehungen in den Diagrammen. Im Benchmark werden
Assoziation, Aggregation und Komposition zu einer ungerichteten Assoziation
zusammengefasst. Dadurch fallen drei doppelte bzw. gegenläufige Assoziationen
weg, und es bleiben 79 Beziehungen. Vererbung und Realisierung behalten Richtung
und Typ.

Das Paket selbst ist zu groß für das Repository und liegt nur im vollständigen
Projektordner. Wie man es herunterlädt, steht in
[`INSTALLATION.md`](../../../INSTALLATION.md). Im Repository liegen
`reference.json` und `manifest.json`.

Aufruf aus dem übergeordneten Ordner:

```bash
.venv/bin/python -m pytest -q skripte/test_benchmark.py skripte/test_curated_hebig.py
PYTHONPATH=../1-llm-pipeline-abstrakte-klassendiagramme \
  .venv/bin/python skripte/curated_hebig_benchmark.py --label curated-rerun
```

Alle Extraktoren bekommen dieselben Dateien, und zwar die, in denen eine Klasse
aus dem Modell (oder ein dokumentierter Alias) deklariert ist. Die Ausgaben
werden auf die 79 Klassen aus dem Modell beschränkt. Gemessen wird also die
Extraktion innerhalb des Umfangs, den die Autoren untersucht haben. Ob ein
Werkzeug diesen Umfang selbst aus allen Klassen eines Projekts auswählen könnte,
wird nicht gemessen. Das wäre die Aufgabe der LLM-Pipeline.

Sechs Klassen aus den Modellen findet keiner der Extraktoren: `Dog`, `Cat`,
`Fish`, `Penguin` und `ItemDecorator` in RaiseMeUp sowie `Link` in myblog. Laut
den Autoren gibt es diese Klassen so nicht im Code. In der Auswertung zählen sie
als nicht gefunden, sind aber keine Fehler der Parser.
