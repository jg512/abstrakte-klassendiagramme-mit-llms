[Deutsch](recherche-datensätze.md) · **English**

# Research: datasets with Java code and matching class diagrams

To check how well a tool or an LLM produces class diagrams, you need something
to compare against: real software projects for which people have drawn a
class diagram. This file describes which such collections (datasets) exist,
which ones were chosen and why, and by which rules the comparison is made. The
[main README](../../README.en.md#glossary) explains the technical terms.

The research was done on 20 September 2026. We were looking for Java projects
for which a class diagram or class graph exists. The aim was 20 to 50
projects, and at least 20 usable pairs of code and diagram.

## Lindholmen dataset

Robles, Ho-Quang, Hebig, Chaudron and Fernandez, *An extensive dataset of UML
models in GitHub*, MSR 2017. It was preceded by Hebig et al., *The Quest for
Open Source Projects that Use UML: Mining GitHub*, MODELS 2016.

- Paper: https://research.chalmers.se/en/publication/251818
- Mirror at the University of Rostock, with downloads:
  https://se.informatik.uni-rostock.de/forschung/datensaetze-und-tools/mirror-lindholmen-datensatz/
- The index lists more than 93,000 UML files in more than 24,000 repos. Not all
  of them are Java projects or class diagrams, and some repos can no longer be
  reached.
- We used only machine-readable `.uml` and `.xmi` files (diagrams stored as
  text, not as pictures). Source code and diagram always come from the same
  commit.
- The 30 projects are our own selection from this dataset, not a published gold
  standard. The models may have been designed by hand, produced by reverse
  engineering or created together with the code, and they may be incomplete or
  out of date.

The selection can be reproduced. The index entries were grouped by repo. Only
repos with at most ten XML models were considered, and from each one the model
with the shortest path was taken. The list was shuffled at random with the seed
20260920 (the fixed starting value means you get the same shuffle again), and
1,200 repos were checked. The first 220 models with 3 to 200 types and at
least one relationship were kept. Downloads were limited to 15 MB per archive,
40 MB unpacked, and 3 to 1,500 Java files. Because of these limits, smaller
projects are overrepresented in the selection. All failures and exclusions are
stored.

For each pair, at least three classes must be matched unambiguously between
model and source code, and there must be at least one relationship between
them. The names must be unique both in the model and in the Java code. The
classes in the source code were collected with javalang, which only supports
Java 8, so the selection leans towards older projects. All extractors get the
same list of files, and the downloaded code was never run.

## Zhang et al. 2025

Wenli Zhang, Weixing Zhang, Daniel Strüber and Regina Hebig, *An empirical study
of manual abstraction between class diagrams and code of open-source systems*,
Software and Systems Modeling 24 (2025),
https://doi.org/10.1007/s10270-025-01289-y

- Replication package:
  https://osf.io/p4jdr/?view_only=34b153d3b7704f4a84befd661dc9c6a1
- Nine Java projects: ZooTypers, RaiseMeUp, EAPLI PL 2NB, FreeDaysIntern,
  Neuroph, PatrickFromTheMOOC, myblog, Orekit and Artemis.
- The package contains the versions of the projects that were studied (an
  archive of 331,030,607 bytes), the original and the annotated models,
  diagrams produced by reverse engineering with IntelliJ, and nine comparison
  tables.
- The authors matched the model elements to the code by hand and recorded what
  was left out, replaced, moved or shown inaccurately. That makes the package
  well suited to studying how people abstract when they draw class diagrams.
- Nine projects on their own are not enough for the 20 we aimed for. So both
  datasets are used: the 30 Lindholmen projects for breadth, and the nine
  Zhang/Hebig projects as a carefully prepared addition.
- Seven of the nine projects originally come from Lindholmen; two were found
  through a search for PlantUML repos. So the two datasets partly overlap.

This dataset is of particular interest for the pipeline. An extractor can read
the code correctly and still differ from the diagram, because classes, members
or relationships were left out of the diagram on purpose. The benchmark only
scores the extraction within the scope the authors modelled. The authors'
annotations can later be used to assess the abstraction done by the LLM.

## Other sources we checked

| Paper / source | Contents | Decision |
| --- | --- | --- |
| Campanello et al., *On the Use of GPT-4 in the Reverse Engineering of Class Diagrams*, JOT 2025, https://www.jot.fm/issues/issue_2025_02/a14.pdf | Five larger Java projects with corrected diagrams abstracted by people. Material: https://github.com/sh4r10/thesis-autogen-classdiagrams/tree/revision | Overlaps with the study by Zhang et al. |
| Siala and Lano, *Using LLMs to extract UML class diagrams from Java and Python programs: an empirical study*, STAF 2025, https://ceur-ws.org/Vol-4122/paper12.pdf | 14 Java examples with generated reference models. Download list at https://zenodo.org/api/records/15108621 | Too few examples, and too small. |
| Siala and Lano, *Leveraging LLMs for abstracting UML and OCL representations from Java and Python programs*, JSS 2026, https://doi.org/10.1016/j.jss.2026.112874 | 2,560 Java/UML pairs, mostly constructed or generated examples, 66 of them from the internet. References produced with Java2JSON. | More useful for parser tests; no real projects. The full archive was not checked. |
| Naboichenko and Peinl, *Unlocking UML Class Diagram Understanding in Vision Language Models*, 2026, https://arxiv.org/abs/2605.11634 | Diagrams generated from Java repos, with questions and answers: https://huggingface.co/datasets/iisys-hof/uml-class-diagrams | The matching Java projects are not included. |
| Palladio Retriever benchmark, https://github.com/PalladioSimulator/Palladio-ReverseEngineering-Benchmark | Many repos with generated architecture models, some references made by hand. | Contains component, system and deployment views, but no class diagrams. |
| Golden UML ModelSet, https://golden-uml-modelset.vercel.app/ | 45 domain descriptions with class diagrams. | No Java implementation. |

## Scoring rules

- What is measured is agreement with the diagram, not whether the extractor is
  correct.
- Only the classes in the model that can be matched unambiguously to a class in
  the source code are scored. Classes and edges that could not be matched are
  still stored.
- Inheritance and realization are compared separately and with their direction.
  Association, aggregation and composition are merged into a single undirected
  association, because people and tools use these three in very different ways.
  Multiplicity (the "1" or "0..*" at the end of a line), role names and
  ownership are not scored.
- Attributes whose type is a class from the model count as an association.
  Duplicate relationships are counted only once. Unsupported relationships are
  logged.
- The tools' graphs are cut down to the same scope as the reference. Node recall
  shows extraction errors; node precision says little within this restricted
  scope, because the output is first limited to the classes in the reference, so
  wrong classes cannot appear at all. (Nodes are the classes, edges the lines
  between them.)
- Failed runs are reported, including when the tool reported success but
  produced no usable output. They enter the totals as an empty output.
- A low score does not automatically mean that an extractor reads the code
  wrongly. Differences were checked against the source code before the extractor
  was changed.
- The tools compared are the pipeline's tree-sitter extractor, javalang 0.13.0
  with an adapter of our own, and mirajp1/java2plantuml (JavaParser 3.4.0).
  javalang is only a parser and needs the adapter to produce a class graph.
