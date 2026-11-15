[Deutsch](ergebnisse-zhang-hebig.md) · **English**

# Results: seven extractors on the Zhang/Hebig suite

In short: tools that read the source code run on all nine projects and reach
the best scores. Tools that read bytecode need a project that can be
translated (compiled) completely. That worked for only three of the nine
projects, so they fall far behind. The
[main README](../../README.en.md#glossary) explains the technical terms.

We compared seven tools that produce a UML class diagram from Java code, on the
nine projects from the replication package of Zhang, Zhang, Strüber and Hebig
(Software and Systems Modeling, 2025). The reference is the set of diagrams the
authors abstracted by hand, with 79 classes and 79 relationships (after
normalisation, that is, after the three kinds of "has a" relationship were
merged into one).

What is measured is agreement with the drawn diagrams. A low score does not
necessarily mean the parser has a bug. The normalisation that turns the 82
relationships counted by the authors into 79 is described in
[`daten/zhang-hebig/README.en.md`](../daten/zhang-hebig/README.en.md).

javalang only supports Java up to version 8. The 72 files that were scored,
however, contain no newer language features (records, `sealed`, `var`,
`switch` expressions with arrows, text blocks), not even in Orekit and Artemis.
So the fact that javalang ran on all nine projects says nothing about whether
it copes with newer Java.

## Overall result

| Tool | reads | ran on | nodes | edges | precision | recall | F1 | time |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| our extractor (tree-sitter) | source code | 9/9 | 73/79 | 53/79 | 0.757 | 0.671 | 0.711 | 0.4 s |
| javalang 0.13.0 + adapter | source code | 9/9 | 73/79 | 53/79 | 0.757 | 0.671 | 0.711 | 0.8 s |
| java2plantuml (mirajp1) | source code | 9/9 | 73/79 | 43/79 | 0.827 | 0.544 | 0.656 | 7.4 s |
| jdeps (JDK) | bytecode | 3/9 | 29/79 | 24/79 | 0.471 | 0.304 | 0.369 | 3.1 s |
| plantuml-generator 2.3.0 | bytecode | 2/9 | 19/79 | 16/79 | 0.762 | 0.203 | 0.320 | 3.9 s |
| Java2PlantUML (juanmf) | bytecode | 2/9 | 19/79 | 10/79 | 1.000 | 0.127 | 0.225 | 29.8 s |
| genuml 0.6.1 | bytecode | 3/9 | 15/79 | 0/79 | – | 0.000 | 0.000 | 158.0 s |

"ran on" counts the projects with usable output. "nodes" and "edges" are the
hits within the model scope, summed over all nine projects.

## Only the three projects that compile

RaiseMeUp, NeurophChanges and PatrickFromTheMOOC together contain 34 classes
and 39 relationships. The bytecode tools also run on these three projects, so
here you can compare how well they analyse when they run at all.

| Tool | reads | ran on | nodes | edges | precision | recall | F1 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| our extractor | source code | 3/3 | 29/34 | 25/39 | 0.806 | 0.641 | 0.714 |
| javalang + adapter | source code | 3/3 | 29/34 | 25/39 | 0.806 | 0.641 | 0.714 |
| java2plantuml (mirajp1) | source code | 3/3 | 29/34 | 18/39 | 1.000 | 0.462 | 0.632 |
| jdeps | bytecode | 3/3 | 29/34 | 24/39 | 0.471 | 0.615 | 0.533 |
| plantuml-generator | bytecode | 2/3 | 19/34 | 16/39 | 0.762 | 0.410 | 0.533 |
| Java2PlantUML (juanmf) | bytecode | 2/3 | 19/34 | 10/39 | 1.000 | 0.256 | 0.408 |
| genuml | bytecode | 3/3 | 15/34 | 0/39 | – | 0.000 | 0.000 |

Compared with all nine projects:

- jdeps rises from F1 0.369 to 0.533, and at 0.615 it has a higher recall than
  java2plantuml (0.462). Its precision is low at 0.471, because jdeps outputs
  edges without a type, taken from the constant pool.
- plantuml-generator rises from 0.320 to 0.533, Java2PlantUML (juanmf) from
  0.225 to 0.408.
- Here java2plantuml has a precision of 1.000 with a recall of 0.462: all 18
  edges it finds are correct, and 21 are missing.
- Our extractor and javalang hardly change (0.711 to 0.714). So the three
  projects that compile are not easier for them than the others.
- genuml stays at 0.000, because it never outputs any relationships.

## Why the bytecode tools mostly fail to run

These tools need compiled code, but the replication package only contains
source code. So each project was compiled once with `javac`, using all JARs
from the project and 41 extra libraries from `werkzeuge/extra/jars/` (see
[`werkzeuge.en.md`](werkzeuge.en.md)).

| Project | javac | source files | class files | reason for the failure |
| --- | --- | ---: | ---: | --- |
| ZooTypers | failed | 14 | 0 | the generated Android class `R` is missing |
| RaiseMeUp | OK | 40 | 158 |  |
| EAPLI_PL_2NB | failed | 51 | 0 | `sun.security.jca` is not accessible in the module system |
| FreeDaysIntern | failed | 78 | 0 | Spring Roo annotations, `javax.validation` |
| NeurophChanges | OK | 173 | 158 |  |
| PatrickFromTheMOOC | OK | 18 | 32 |  |
| myblog | failed | 7 | 0 | symbols cannot be resolved |
| Orekit | failed | 1711 | 18 | needs Hipparchus 3.1-SNAPSHOT, only 3.0 has been released |
| Artemis | failed | 1582 | 0 | Spring Boot, jHipster |

The "source files" column only counts the folders that hold classes from the
model, not the whole project. For Orekit, 18 class files are produced before
`javac` stops. They were not used, because incomplete bytecode would not be
comparable.

Only 3 of 9 projects can be compiled. Even then, not every tool runs: for
NeurophChanges both PlantUML generators fail while loading the classes
(`NoClassDefFoundError`, meaning "class not found": plantuml-generator for
`AbstractMapEntry`, Java2PlantUML for a class from the database library
Hibernate that is missing from the project).

## Relationships found per project

| Project | reference | our extractor | javalang 0.13.0 | java2plantuml | jdeps | plantuml-generator 2.3.0 | Java2PlantUML | genuml 0.6.1 |
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

`–` means that the tool had no usable output for this project.
