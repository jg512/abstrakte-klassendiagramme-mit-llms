[Deutsch](reproduzieren.md) · **English**

# Repeating the measurements

This file lists the commands for repeating the measurements from folder 2 on
your own computer. You type the commands into a terminal. How to prepare the
computer for this, including for Windows and Docker, is described in more
detail in [`INSTALLATION.en.md`](../../INSTALLATION.en.md). The
[main README](../../README.en.md#glossary) explains the technical terms.

The basis is the fixed list of projects in `daten/lindholmen/manifest.json`.
Do not rerun the selection of projects for a repetition, because the repos'
branches and contents may have changed since then.

All commands are run in this folder
(`2-java-extraktoren-benchmark-forschungsdaten/`). The pipeline with our
extractor is in `../1-llm-pipeline-abstrakte-klassendiagramme`.

## Environment

You need Python 3.13, a JDK, `git` (downloads repos), `curl` (downloads files)
and `uv` (sets up Python environments). The versions of the measurement
environment and the checksums of the tools are in `werkzeuge/TOOLS.json`. A
checksum (here SHA-256) is a kind of fingerprint of a file. If it matches, the
file is unchanged.

```bash
uv venv .venv --python 3.13
uv pip install --python .venv/bin/python -r werkzeuge/requirements.lock.txt
uv pip install --python .venv/bin/python --no-deps -e ../1-llm-pipeline-abstrakte-klassendiagramme
```

In the full project folder, java2plantuml (mirajp1) is already compiled under
`werkzeuge/`; the GitHub repository does not have it. This is how to
build it again:

```bash
git clone https://github.com/mirajp1/java2plantuml.git werkzeuge/java2plantuml
git -C werkzeuge/java2plantuml checkout cadd0f0a06e87825472227381a37210763ae137c
curl -fL https://repo.maven.apache.org/maven2/com/github/javaparser/javaparser-core/3.4.0/javaparser-core-3.4.0.jar -o werkzeuge/javaparser-core-3.4.0.jar
mkdir -p werkzeuge/java2plantuml/classes
javac -cp werkzeuge/javaparser-core-3.4.0.jar -d werkzeuge/java2plantuml/classes \
  werkzeuge/java2plantuml/src/main/java/*.java werkzeuge/java2plantuml/src/main/java/source/*.java \
  werkzeuge/java2plantuml/src/main/java/translate/*.java werkzeuge/java2plantuml/src/main/java/visitors/*.java
```

The tool is compiled unchanged against JavaParser 3.4.0; the outdated Gradle
wrapper is not needed. Do not run the build scripts of the projects under
study.

The four remaining tools for the measurement with seven tools are described in
[`werkzeuge.en.md`](werkzeuge.en.md).

## Lindholmen (30 projects)

```bash
.venv/bin/python skripte/restore.py                     # checks the inputs, downloads anything missing
.venv/bin/python -m pytest -q skripte/test_benchmark.py
.venv/bin/python skripte/benchmark.py --label rerun --limit 30
```

Before extraction, every Java file is checked against its SHA-256 checksum.
`restore.py` also checks the models and, when downloading again, the checksum
of the archive. The results (raw outputs, JSON per project, CSV and overall
result) are stored in `ergebnisse/messungen/rerun/`. Each adapter has a time
limit of 120 seconds, the Java process one of 90 seconds. The script sets these
time limits through POSIX signals, a feature of Unix systems, so it only runs
on Linux, macOS or WSL (Linux under Windows).

## Zhang/Hebig (9 projects)

The replication package is under `daten/zhang-hebig/`. The checksum of the
source archive is
`11db4e9a45affaf80df627fa6604119e0c56b47aef66e0e1ceae58086a13f85e`. The
transcription of the diagrams and the checksums of the source files are in
`daten/zhang-hebig/reference.json` and `daten/zhang-hebig/manifest.json`.

```bash
.venv/bin/python -m pytest -q skripte/test_benchmark.py skripte/test_curated_hebig.py
PYTHONPATH=../1-llm-pipeline-abstrakte-klassendiagramme \
  .venv/bin/python skripte/curated_hebig_benchmark.py --label curated-rerun
```

All three extractors get the same 72 Java files. The number of relationships
according to the authors (82, directed) is included in the output; what is
scored are the 79 relationships after normalisation.

Measurement with all seven tools (the tools from `werkzeuge.en.md` must be
present):

```bash
PYTHONPATH=../1-llm-pipeline-abstrakte-klassendiagramme \
  .venv/bin/python skripte/curated_tools_benchmark.py \
    --label curated-alltools \
    --workdir /tmp/java-uml-bytecode \
    --genuml /pfad/zum/genuml-venv/bin/genuml
```

Here `/pfad/zum/` means "/path/to/". The command compiles each project once
with `javac` and measures all seven tools. The results are written to
`ergebnisse/messungen/curated-alltools/`, and every output is written to
`ergebnisse/diagramme/` as PlantUML and PNG.

## Selecting the projects

`daten/lindholmen/Project_FileTypes_V2.0.csv` and
`daten/lindholmen/UMLFiles_List_V2.0.csv` are the Lindholmen indexes from the
mirror server at the University of Rostock (link in
[`recherche-datensätze.en.md`](recherche-datensätze.en.md)).

```bash
.venv/bin/python skripte/discover.py --limit 1200
.venv/bin/python skripte/acquire.py --limit 220
.venv/bin/python skripte/benchmark.py --prepare
```

These commands repeat the selection with the repos as they are today.
`daten/lindholmen/eligible-manifest.json` contains all suitable pairs; the
first 30 of them were copied into `daten/lindholmen/manifest.json` before any
extractor was measured. The original selection is documented in
`daten/lindholmen/discovery.json`, `daten/lindholmen/acquisition.json`,
`daten/lindholmen/preparation-exclusions.json` and the logs in
`ergebnisse/protokolle/`.

## Before and after

`ergebnisse/messungen/before/` was recorded before the fixes to the extractor,
`ergebnisse/messungen/final/` after them. The other tools stayed unchanged.
`report.py` summarises the stored results
(`.venv/bin/python skripte/report.py`) and in doing so writes a short
`REPORT.md` in English to `ergebnisse/messungen/`. The detailed evaluation is
in [`ergebnisse-lindholmen.en.md`](ergebnisse-lindholmen.en.md).
`ergebnisse/messungen/verification/` holds a later full repeat run with all
three tools.

## Checking the pipeline

The `.venv` from this folder contains folder 1 as an editable install along
with all dependencies, so it is also enough for the pipeline:

```bash
cd ../1-llm-pipeline-abstrakte-klassendiagramme
../2-java-extraktoren-benchmark-forschungsdaten/.venv/bin/python -m pytest -q -m 'not network'
../2-java-extraktoren-benchmark-forschungsdaten/.venv/bin/python -m src ../2-java-extraktoren-benchmark-forschungsdaten/daten/lindholmen/corpus/jainebri__Super-Simple-Stocks/source \
  --language java --method all --dry-run --no-cleanup \
  --out ../2-java-extraktoren-benchmark-forschungsdaten/ergebnisse/pipeline-trockenlauf
```

The benchmark with 20 small Java cases is in folder 3
([`benchmarks/java_literal/`](../../3-java-parser-klassendiagramme/benchmarks/java_literal/README.en.md),
with the command in the README there).

Instead of an LLM, the dry run uses a stand-in with fixed answers. It shows
that parser, driver and output work together for all eight variants, but it
says nothing about the quality of real diagrams. For the prune variants the
stand-in makes up extra classes, so the pipeline reports that the diagram has
too many classes. That is expected.

To measure only the current version of our extractor on the same inputs:

```bash
PYTHONPATH=../1-llm-pipeline-abstrakte-klassendiagramme .venv/bin/python skripte/benchmark.py --label enhanced-rerun --limit 30 --tools ours
PYTHONPATH=../1-llm-pipeline-abstrakte-klassendiagramme .venv/bin/python skripte/curated_hebig_benchmark.py --label curated-enhanced-rerun --tools ours
```
