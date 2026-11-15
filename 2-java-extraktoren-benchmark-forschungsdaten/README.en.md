[Deutsch](README.md) · **English**

# Benchmarking Java extractors on research data (September/October 2026)

An extractor, in this folder, is a tool that automatically turns Java code into
a class diagram. Here seven such tools, our own parser among them, are compared
on real projects for which people have drawn class diagrams. If the basic terms
(class diagram, parser, benchmark, ground truth, precision, recall, F1) are new
to you, the [main README](../README.en.md#glossary) explains them.

Why this comparison is needed: a ground truth taken from bytecode tells you
whether a parser reads the code correctly. For this project, though, what
matters more is how well a class graph matches a diagram a person drew. That
calls for public Java projects that come with matching UML diagrams. This
folder contains the search for such data, the data itself and the
measurements. Later on, the same data is meant to show how well the LLM from
folder 1 abstracts.

## Research questions

1. Is there a research dataset of Java projects with matching class diagrams
   that contains at least 20 usable pairs?
2. How does our own extractor (folder 1, `src/parsing/java/`) do on this data
   compared with other tools?
3. Which bugs in our extractor come to light along the way, and can they be
   fixed and covered by tests?

## Results

- Data: we use 30 projects from the Lindholmen dataset, a collection of GitHub
  projects that contain UML files (4,040 Java files in total, with source code
  and model always taken from the same commit). On top of that come the nine
  projects from the Zhang/Hebig study (2025), whose diagrams were abstracted by
  hand. "Model" here means the drawn diagram in machine-readable form. More on
  this in [`doku/recherche-datensätze.en.md`](doku/recherche-datensätze.en.md).
- On the 30 Lindholmen projects, our extractor and javalang tie (micro F1
  0.646), and java2plantuml (mirajp1) reaches 0.577. All three ran on all 30
  projects. Micro F1 is the F1 score over all lines of all projects together.
  That our extractor and javalang score exactly the same is to be expected:
  javalang is only a parser, and the adapter that turns its output into a class
  graph was written in this project and looks at the same declarations. Our
  extractor differs where these projects do not test it: newer Java, old
  encodings, evidence for each edge and the IntelliJ mode. "Java2PlantUML"
  (capitalised) means a different tool in this folder, the one by juanmf that
  reads bytecode.
- On the Zhang/Hebig projects seven extractors were compared. The three tools
  that read source code run on all nine projects (our extractor and javalang
  F1 0.711, java2plantuml 0.656). The bytecode tools run on three projects at
  most, because only three can be compiled at all. Even on those three they
  stay well below the source-code tools, with F1 between 0.41 and 0.53 against
  0.63 to 0.71. genuml outputs no relationships whatsoever.
- Several bugs were found and fixed in our extractor (imports, wildcard
  imports, inherited nested types, enum bodies, generic wrapper classes,
  self-associations). After that more features were added: recognising the
  Maven/Gradle folder layout, recording where each edge was found,
  multiplicities, and an optional javac mode.
- In October a second mode was added that reproduces IntelliJ's class
  diagrams, including dependencies that come from method bodies and chains of
  calls. On seven of the nine projects it matches the IntelliJ diagram
  completely, and on the other two it matches every edge that could be checked
  in the picture. More on this in
  [`doku/intellij-nachbildung.en.md`](doku/intellij-nachbildung.en.md).
- The scores only measure how well the output fits the diagrams. They do not
  show whether the code was read correctly. The case studies revealed that some
  reference diagrams describe a design that ended up being built differently.

## Layout

```
README.md
doku/                     reports on the research, the results and the case studies
skripte/                  all Python scripts and their tests
daten/
  lindholmen/             the 30 Lindholmen projects and everything about how they were chosen
  zhang-hebig/            the Zhang/Hebig replication package with a transcription of the diagrams
  intellij/               class selection and the edges read off the IntelliJ pictures
  recherche/              material on other datasets and tools
ergebnisse/
  messungen/              every measurement run as JSON and CSV
  diagramme/              rendered diagrams per Zhang/Hebig project, the reference and every tool
  diagramme-intellij/     the IntelliJ picture next to the output of the IntelliJ mode
  pipeline-trockenlauf/   a run of the pipeline with all eight variants, without an LLM
  protokolle/             logs of the runs and tests
werkzeuge/                built third-party tools, measurement environment, Python dependencies
```

(The folder names are German: `doku` is documentation, `skripte` scripts,
`daten` data, `ergebnisse` results, `messungen` measurements, `diagramme`
diagrams, `protokolle` logs, `werkzeuge` tools.)

The scripts are run from this folder, for example
`.venv/bin/python skripte/intellij_abgleich.py`. The exact commands are in
[`doku/reproduzieren.en.md`](doku/reproduzieren.en.md). Most of `daten/` and
`ergebnisse/` is too big for GitHub. The repository only holds our own
metadata (selection, checksums, transcriptions, references); everything else
is in the full project folder or can be downloaded again by following
[`INSTALLATION.en.md`](../INSTALLATION.en.md).

## Documents

A sensible reading order is: the dataset research, then the two results
reports, then the case studies and the IntelliJ reproduction. You only need the
tools and reproduction documents if you want to rerun the measurements.

| File | Contents |
| :--- | :--- |
| [`doku/recherche-datensätze.en.md`](doku/recherche-datensätze.en.md) | available datasets, which ones were chosen and why, the scoring rules |
| [`doku/ergebnisse-lindholmen.en.md`](doku/ergebnisse-lindholmen.en.md) | 30 projects and the Zhang/Hebig suite with three extractors, bugs fixed, a table per project |
| [`doku/ergebnisse-zhang-hebig.en.md`](doku/ergebnisse-zhang-hebig.en.md) | all seven extractors on the Zhang/Hebig suite, and why the bytecode tools dropped out |
| [`doku/fallstudien.en.md`](doku/fallstudien.en.md) | RaiseMeUp, NeurophChanges and PatrickFromTheMOOC in detail |
| [`doku/intellij-nachbildung.en.md`](doku/intellij-nachbildung.en.md) | IntelliJ's rules, the environment per project, the comparison with the IntelliJ diagrams |
| [`doku/werkzeuge.en.md`](doku/werkzeuge.en.md) | origin, versions, checksums and building of the tools |
| [`doku/reproduzieren.en.md`](doku/reproduzieren.en.md) | commands for repeating the measurements |
| [`daten/zhang-hebig/README.en.md`](daten/zhang-hebig/README.en.md) | the Zhang/Hebig replication package |
| [`ergebnisse/diagramme/README.en.md`](ergebnisse/diagramme/README.en.md) | what the drawn diagrams show (only in the full project folder) |

## Scripts

| File | Job |
| :--- | :--- |
| `skripte/discover.py`, `skripte/acquire.py` | selecting and downloading the Lindholmen subset |
| `skripte/restore.py` | checks the inputs against their checksums and downloads anything missing |
| `skripte/benchmark.py` | measurement on the 30 Lindholmen projects (three extractors) |
| `skripte/curated_hebig_benchmark.py` | the same for the Zhang/Hebig projects |
| `skripte/curated_tools_benchmark.py` | all seven extractors on the Zhang/Hebig projects, including compiling and rendering |
| `skripte/intellij_abgleich.py` | the IntelliJ mode of our extractor against the IntelliJ diagrams |
| `skripte/report.py` | regenerates tables and reference graphs from the stored runs |
| `skripte/test_benchmark.py`, `skripte/test_curated_hebig.py` | tests for the normalisation and the reference data |

## The data in detail

| Path | Contents |
| :--- | :--- |
| `daten/lindholmen/manifest.json` | the 30 fixed pairs of project, commit, model and source files |
| `daten/lindholmen/corpus/` | downloaded projects, source code and model |
| `daten/lindholmen/reference-graphs/` | normalised reference graphs per project (JSON and PlantUML) |
| `daten/lindholmen/model-probes/` | 850 UML models that were examined during selection |
| `daten/lindholmen/discovery.json`, `acquisition.json`, `eligible-manifest.json`, `preparation-exclusions.json` | intermediate states and exclusions of the selection |
| `daten/lindholmen/UMLFiles_List_V2.0.csv`, `Project_FileTypes_V2.0.csv`, `lindholmen.html` | indexes of the Lindholmen dataset and the mirror server's page |
| `daten/lindholmen/syntax-audit.json` | syntax check of the inputs |
| `daten/intellij/projekte.json` | per project, the classes in the IntelliJ diagram and how the project was opened in IntelliJ |
| `daten/intellij/referenz/` | the edges read off the IntelliJ pictures |
| `daten/recherche/` | `siala-*.json`, `palladio-tree.json`, `java2plantuml-repo.json` from the search for datasets and tools |
| `ergebnisse/messungen/reproduction-verification.json` | comparison of the repeat runs |
| `werkzeuge/TOOLS.json`, `werkzeuge/requirements.lock.txt` | measurement environment and Python dependencies |

Paths in the JSON files under `daten/lindholmen/` are relative to that
subfolder; those in `daten/intellij/projekte.json` are relative to `daten/`.

Downloaded project code was never run.
