[Deutsch](README.md) · **English**

# LLM pipeline for abstract class diagrams

This folder holds the project's main program. It reads in a software project,
has a language model (LLM) pick out the important classes and draws a clear
class diagram from them. If you are not sure yet what classes, class diagrams
or LLMs are, start with the [main README](../README.en.md); its
[glossary](../README.en.md#glossary) explains all the technical terms.

Step by step, the pipeline reads a repository (Python or Java) and has a
language model turn it into an abstract class diagram in the PlantUML text
format. The diagram should show only the central classes, meaning the domain
classes (the things the software is about, such as a customer or an order),
classes that steer the program, and important interfaces. Helper classes,
plain data containers, framework code (the ready-made scaffolding a piece of
software is built on) and tests are left out.

The Python package is called `abstract-uml`. The history of the project is in
the [main README](../README.en.md#how-the-project-developed).

## Status

- The pipeline runs end to end for Python and Java.
- All ways of working go through one shared control program (the driver),
  with eight variants.
- The most recent runs with a real LLM were in July 2026, using
  `deepseek-chat` on the Python repos `schedule` and `loguru`.
- The Java side is tested and has been measured on research data, but so far
  it has only been run as a dry run without an LLM.
- The Java parser can also produce class diagrams the way IntelliJ does
  (IntelliJ mode, see below).
- All tests pass with `pytest -m 'not network'`. Tests are small checking
  programs that automatically confirm the code still does what it should.
  `not network` skips the tests that need an internet connection.

## How it works

```
repo (path, GitHub URL or list)
  -> collect files, size check up front (preflight)
  -> static analysis: classes, members, import graph, full class graph
  -> driver: the LLM builds a working graph using tools
  -> check and repair (validator), optionally a cleanup pass by the LLM
  -> graph.json, diagram.puml, trace and metrics for every run
```

"Members" are a class's attributes and methods. The working graph is the
diagram the LLM is currently working on. Internally everything is a graph in
JSON format (`src/schema/`); the PlantUML is only generated from it at the
very end.

### Static analysis

Static analysis reads the code without running it. Each language has its own
tools for this:

| | Python | Java |
| :--- | :--- | :--- |
| files | `*.py` | `*.java` |
| classes and members | `ast` (Python's built-in parser) | `tree-sitter-java` |
| dependencies | import lines | resolved type references |
| full class graph | `pyreverse` (from pylint) | our own parser |
| file per repo | `pyreverse.json/.puml` | `javagraph.json/.puml` |

From here on the process is the same for both languages; only the input from
the static analysis differs.

### The Java parser

The parser lives in `src/parsing/java/`:

| File | Job |
| :--- | :--- |
| `ts_pass.py` | reads the syntax tree (the broken-down structure of each file) and collects types, fields, methods and supertypes |
| `resolution.py` | works out which class a name refers to, through packages, imports and nested types |
| `graph_builder.py` | builds the full class graph from that |
| `import_graph.py` | dependencies between packages, used to form clusters |
| `javac_solver.py` | optional extra resolution through the Java compiler |
| `intellij.py` | class diagram following IntelliJ's rules (see below) |

How the individual steps fit together is described at length, with a worked
example, in [`doku/java-parser.en.md`](doku/java-parser.en.md).

Some of the decisions behind the parser:

- The parser reads source code only, never bytecode, so projects do not have to
  compile. That is exactly where the bytecode tools fell down in the comparison
  (see [folder
  2](../2-java-extraktoren-benchmark-forschungsdaten/README.en.md)).
- The encoding is detected per file (UTF-8, then CP1252, then Latin-1). Older
  Java projects are often not saved as UTF-8.
- Package names are given relative to the repo, with the shared prefix removed
  (`de.firma.app.model` becomes `model`).
- External superclasses and interfaces, that is, ones from third-party
  libraries, are kept in the package `external`, because inheriting from
  `JFrame` (the class for program windows), for example, says something about
  what a class does. Fields with external types such as `String` (text) or
  `Timer`, on the other hand, do not create an edge.
- If a type name is ambiguous because several classes could be meant, it is
  reported and left out.
- Every relationship records where it was found (field or method, type, file,
  line). Ambiguities, duplicate declarations and files that could not be read
  cleanly go into `javagraph.diagnostics.json`.
- You can set how much of each class is shown (`--java-member-profile
  structure|summary|public-api|full`), whether dependencies from method
  signatures are added (`--java-method-dependencies`) and whether javac helps
  with resolution (`--java-symbol-solver javac` with `--java-classpath`).

Why we wrote a parser of our own is explained in the [main
README](../README.en.md#phase-3-switching-to-java-and-choosing-a-parser-august-2026)
and in folder 2.

### IntelliJ mode

In short, in this mode the parser also reads the code inside the methods, and
every class used there becomes a dependency, even by way of a detour. The
details:

With `--java-relations intellij` (in the configuration, `java.relation_style:
intellij`) the parser produces the class diagram according to the rules of the
IntelliJ IDEA programming environment (`src/parsing/java/intellij.py`). To do
that it also reads what is inside the methods. Every reference in the code
becomes a dependency. A method call counts for the class in which the method
is written, even through chains of calls such as
`RaiseMeUp.getCurrentJob().getImpactenergy()`. `new` (creating an object)
gives a dependency labelled `«create»`, fields become compositions marked "1"
or "*", and inner classes get an edge of their own (`nesting`). Inheritance and
realization skip over types that are not in the diagram.

| Option | Meaning |
| :--- | :--- |
| `--java-diagram-classes FILE` | the classes to put in the diagram, one fully qualified name (including the package, e.g. `de.firma.Kunde`) per line. Without a file, all of them |
| `--java-ide-no-jdk` | behave as if IntelliJ had no JDK configured |
| `--java-ide-no-same-package` | behave as if IntelliJ had not found classes from the same package |

The rules and the comparison with the nine IntelliJ diagrams from Zhang/Hebig
are in folder 2, in
[`doku/intellij-nachbildung.en.md`](../2-java-extraktoren-benchmark-forschungsdaten/doku/intellij-nachbildung.en.md).

### Variants

All variants share the same loop in the driver, with the same tools, prompts,
budgets and stopping rules. They differ in three settings:

- seed: the working graph either starts empty (additive, the model adds
  things) or as the full class graph, from which the model removes things
  (subtractive). This "seed" (the starting material) has nothing to do with
  the random seed used for repetitions.
- context: what goes into the first message to the model, namely an overview
  of the packages, the clusters of the import graph, or the full class graph.
- peek: whether the model may read the source code itself (tools `read_file`,
  `search_code`).

| Variant | seed | context | peek | old name |
| :--- | :--- | :--- | :--- | :--- |
| `overview` | empty | overview | no | |
| `overview-peek` | empty | overview | yes | `m2` |
| `cluster` | empty | clusters | no | |
| `cluster-peek` | empty | clusters | yes | `m3` |
| `catalog` | empty | class graph | no | `m1a` |
| `catalog-peek` | empty | class graph | yes | `m1b` |
| `prune` | full graph | class graph | no | `m4a` |
| `prune-peek` | full graph | class graph | yes | `m4b` |

The `cluster` variants also split the run by cluster and then merge the
partial diagrams in a step of their own (synthesis). The old names `m1a` to
`m4b` come from the first version, in which every method was a separate
program. They still work as alternative names (aliases).

The model has three tools: `inspect_class` (look at a class), `apply_edits`
(remove classes and add classes and lines, all in one call) and
`emit_diagram` (hand in the finished diagram). The peek variants add
`read_file` and `search_code`, but those are only unlocked once a first draft
exists. Shortly before the budget runs out, the model is told to wrap up.

Several of these rules came out of problems in earlier runs (`runs/old/`):

- Back when classes and lines were added through separate tools, the budget
  often ran out between the two steps, and the diagrams ended up with no lines
  at all.
- Models that could read the code often did nothing but read and never added
  anything. An instruction in the prompt did not stop that, so the reading
  tools are now locked while the diagram is empty.
- Without feedback on the current size, the models often ended up well above
  or below the target size. Every response to a change now includes the
  current state.
- A reminder that came after a fixed share of the budget had been used arrived
  too late, because later steps are much bigger once the whole conversation is
  sent along. The reminder now depends on the budget that is left.

## Results

Comparison with a ground truth on `dbader/schedule` (July 2026,
`deepseek-chat`, no target size, 3 repetitions with seeds 7, 42 and 123,
`runs/experiment_20260707T033256/`). `schedule` is a small Python program for
running tasks at set times. The ground truth has 2 classes and 2 lines:
`Scheduler` (the schedule) owns its `Job`s (the scheduled tasks; composition),
and every `Job` knows its `Scheduler` (association).

The table shows the mean over the three repetitions. "Edges, strict" only
counts a line as correct if its start, end and kind all match. "Edges as
pairs" only asks for the right two classes to be connected, in either
direction and with any kind of line. What F1 means is explained in the
[main README](../README.en.md#how-to-tell-whether-a-diagram-is-good).

| Variant | Node F1 | Edges, strict | Edges as pairs |
| :--- | ---: | ---: | ---: |
| prune | 1.00 | 0.78 | 1.00 |
| prune-peek | 1.00 | 0.72 | 1.00 |
| catalog | 1.00 | 0.67 | 1.00 |
| catalog-peek | 0.76 | 0.73 | 0.72 |
| cluster-peek | 0.72 | 0.39 | 0.61 |
| cluster | 0.67 | 0.47 | 0.61 |
| overview | 0.61 | 0.60 | 0.67 |
| overview-peek | 0.61 | 0.60 | 0.52 |

You can recompute the scores for each seed with `python -m src.tools.gt_compare
runs/experiment_20260707T033256/ground_truth.json
runs/experiment_20260707T033256/seed_<N>/schedule`.

`prune`, `prune-peek` and `catalog` found both classes in every repetition and
added nothing else. The other variants find them too but also take in extra
classes. For the best variants, reading the code (peek) made no measurable
difference. The 24 runs together cost about 0.15 US dollars.

Stability on `schedule` and `loguru` (July 2026, 8 variants with 5 seeds each,
`runs/experiment_20260713T214319/experiment_summary.md`): on `loguru`, a
library for writing log files, the average number of classes in the diagram
lies between about 9 and 19 depending on the variant. The standard deviation,
a measure of how much that number varies from run to run, lies between 1.5
and 4.7 classes. There is no ground truth for `loguru`.

`schedule` is very small, and results on two classes hardly carry over to
larger systems. That is what prompted the search for a bigger dataset with
real diagrams, which in turn led to the switch to Java.

## Installing and running

Type the following commands into a terminal, inside the folder
`1-llm-pipeline-abstrakte-klassendiagramme`. They set up a Python environment
of its own (`.venv`), install the package and run the tests. A fuller guide,
including Windows and Docker, is in [`INSTALLATION.en.md`](../INSTALLATION.en.md).

```bash
python -m venv .venv
.venv/bin/pip install -e '.[java,dev]'
.venv/bin/python -m pytest -q -m 'not network'
```

API keys (the password for accessing the model provider) are read from
environment variables (`GEMINI_API_KEY`, `DEEPSEEK_API_KEY`, depending on the
configuration).

```bash
# simple run (default: the catalog variant)
python -m src /path/to/repo

# a particular variant and target size
python -m src https://github.com/user/repo --method cluster-peek --target-nodes 15

# all eight variants over a list of repos
python -m src repos.txt --method all --out runs/

# a Java repo
python -m src /path/to/java/repo --language java

# dry run without an LLM
python -m src /path/to/repo --method all --dry-run --no-cleanup
```

The configurations are in `configs/`. `default.yaml` holds the defaults, and
the other files override individual values:

| File | Purpose |
| :--- | :--- |
| `default.yaml` | defaults, with Gemini as the model |
| `deepseek.yaml`, `deepseek_exp.yaml` | DeepSeek; the second one uses the budgets of the July experiments |
| `ollama.yaml` | a local model through Ollama (`qwen2.5:14b`) |
| `ollama_docker.yaml` | the same, for when the pipeline runs in the Docker container and Ollama on the machine itself |
| `gemini.yaml` | Gemini with a slightly higher temperature (more randomness in the answers) |
| `smoke_*.yaml` | quick functional checks (Gemini or `qwen2:0.5b`) |

## Folders

| Folder | Contents |
| :--- | :--- |
| `src/parsing/` | static analysis: `python/` (the ast module and pyreverse) and `java/` (our own parser on tree-sitter), plus what both share (`code_graph.py` puts the steps together, `models.py`, `languages.py`, `cache.py`) |
| `src/methods/` | driver, variants, tools, clustering |
| `src/llm/` | the LLM connection through litellm, retries, trace, the stand-in for dry runs |
| `src/schema/` | graph model, validator, PlantUML output |
| `src/cleanup/`, `src/targeting/` | cleanup by the LLM, automatic target size |
| `src/tools/` | helper scripts: comparing with the ground truth, replaying a run, regenerating PlantUML |
| `prompts/` | the prompts for the LLM (in English, since they are part of the experiment) |
| `configs/` | configurations |
| `tests/` | tests; they run without a network or an LLM |
| `doku/` | [description of the Java parser](doku/java-parser.en.md) |
| `runs/` | output of the runs; `runs/old/` holds the runs from May to July 2026 (only in the full project folder, not on GitHub) |

Every run writes `diagram.puml`, `graph.json`, `trace.jsonl` (every request to
the LLM with its tokens and duration), `config.yaml` (the settings used),
`errors.log` and `summary.md`.
