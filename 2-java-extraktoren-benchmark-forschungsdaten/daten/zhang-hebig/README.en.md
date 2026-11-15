[Deutsch](README.md) · **English**

# The curated Zhang/Hebig suite

In 2025, Zhang, Zhang, Strüber and Hebig looked at nine Java projects to find
out what people leave out when they draw a class diagram of existing code. The
material they published (the replication package) serves this project as a
carefully prepared ("curated") test collection, or suite. Technical terms are
explained in the [main README](../../../README.en.md#glossary).

This folder holds the public replication package for Wenli Zhang, Weixing
Zhang, Daniel Strüber and Regina Hebig, *An empirical study of manual
abstraction between class diagrams and code of open-source systems* (Software
and Systems Modeling, 2025).

- Paper: https://doi.org/10.1007/s10270-025-01289-y
- Package: https://osf.io/p4jdr/?view_only=34b153d3b7704f4a84befd661dc9c6a1
- SHA-256 of the source archive:
  `11db4e9a45affaf80df627fa6604119e0c56b47aef66e0e1ceae58086a13f85e`
- Size of the source archive: 331,030,607 bytes, 6,268 Java files in nine
  projects

| Path | Contents |
| :--- | :--- |
| `Version(s) of Source Code Used/` | the nine projects in the version that was studied |
| `models/original/` | the projects' original class diagrams |
| `models/annotated/` | the same diagrams with the authors' notes on how each part is implemented in the code (PDF) |
| `models/reverse/` | diagrams that IntelliJ generated automatically from the code (reverse engineering), unpacked from `downloads/reverse-models.zip` |
| `comparisons/` | one comparison table per project, made by the authors (xlsx) |
| `reference.json` | the reference, transcribed by hand: 79 classes and their relationships |
| `manifest.json` | the 72 source files the extractors get as input, with SHA-256 checksums |

The authors count 82 relationships in the diagrams. The benchmark merges
association, aggregation and composition into a single undirected
association. That removes three associations that were duplicates or pointed
both ways, leaving 79 relationships. Inheritance and realization keep their
direction and kind.

The package itself is too big for the repository and only exists in the full
project folder. How to download it is described in
[`INSTALLATION.en.md`](../../../INSTALLATION.en.md). The repository contains
`reference.json` and `manifest.json`.

To run it from the parent folder:

```bash
.venv/bin/python -m pytest -q skripte/test_benchmark.py skripte/test_curated_hebig.py
PYTHONPATH=../1-llm-pipeline-abstrakte-klassendiagramme \
  .venv/bin/python skripte/curated_hebig_benchmark.py --label curated-rerun
```

Every extractor gets the same files, namely those in which a class from the
model (or a documented alias) is declared. The outputs are then restricted to
the 79 classes in the model. What gets measured, then, is extraction within the
scope the authors studied. Whether a tool could pick that scope out of all the
classes of a project by itself is not measured. That would be the job of the
LLM pipeline.

Six classes from the models are found by none of the extractors: `Dog`, `Cat`,
`Fish`, `Penguin` and `ItemDecorator` in RaiseMeUp, and `Link` in myblog.
According to the authors, these classes do not exist in that form in the code.
The evaluation counts them as not found, but they are not parser errors.
