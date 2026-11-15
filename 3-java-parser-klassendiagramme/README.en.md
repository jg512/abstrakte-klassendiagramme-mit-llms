[Deutsch](README.md) · **English**

# The Java parser as a standalone tool (November 2026)

`javauml` is a small program that draws a complete class diagram of any Java
project, without an LLM. You give it a project's folder or its address on
GitHub, and you get the diagram back as text and, if you like, as a picture. It
is the parser from the LLM pipeline, lifted out into a standalone tool. The
[main README](../README.en.md#glossary) explains what a class diagram, a parser
and PlantUML are.

Specifically, `javauml` turns a Java repo into a class diagram as PlantUML
and JSON, and optionally straight into a PNG or SVG picture. It reads only the
source code, so the project never has to be built or compiled, and missing
libraries do not get in the way.

The parser is the same one used by the LLM pipeline in
[folder 1](../1-llm-pipeline-abstrakte-klassendiagramme/README.en.md)
(`src/parsing/java/`). There it is just one part of the pipeline and depends
on the pipeline's configuration, cache and LLM libraries. Here it stands on its
own and needs nothing but `tree-sitter` and `tree-sitter-java`.

## Installing

Type these commands into a terminal, inside the folder
`3-java-parser-klassendiagramme`. They create a separate Python environment
(`.venv`) for this folder and install the tool into it. A fuller guide,
including Windows and Docker, is in
[`INSTALLATION.en.md`](../INSTALLATION.en.md).

```bash
python3 -m venv .venv
.venv/bin/pip install -e .          # with tests: -e '.[dev]'
```

After that you have the command `.venv/bin/javauml`. PNG and SVG output needs
PlantUML, either as a JAR file (in which case Java has to be installed too) or
as a `plantuml` command that the terminal can find (on the `PATH`). In the full
project folder the JAR already sits in folder 2. If you only have the GitHub
repository, download it as described in
[`INSTALLATION.en.md`](../INSTALLATION.en.md) and adjust the path:

```bash
export PLANTUML_JAR=../2-java-extraktoren-benchmark-forschungsdaten/werkzeuge/plantuml-1.2025.4.jar
```

## Usage

```bash
# local repo; writes uml-ausgabe/<repo>/klassendiagramm.json and .puml
javauml path/to/repo

# straight from GitHub, with a picture
javauml https://github.com/user/project.git -f json,puml,svg

# several repos into one folder
javauml repo-a repo-b https://github.com/user/repo-c -o diagrams

# only PlantUML, printed to standard output
javauml path/to/repo --stdout puml > diagram.puml
```

Git URLs are copied (cloned) shallowly, meaning only the latest state without
its history, into a temporary folder that is deleted afterwards. With
`--keep-clone` the clone stays in `<output>/<repo>/quelle`, and `--ref` lets
you pick a branch or tag. The cloned code is only read, never run.

The output file names are German: `klassendiagramm` means "class diagram",
`uml-ausgabe` "UML output" and `quelle` "source".

From your own Python program (as a library):

```python
from javauml import Options, extract

result = extract("path/to/repo", Options(mode="intellij"))
print(result.plantuml())
graph = result.graph          # nodes, edges, where each was found, diagnostics
```

## Two modes

The `literal` mode (the default) shows what is in the declarations: classes
with their attributes and methods, inheritance (`extends`), realization
(`implements`) and fields whose type is a class of the project. The kind of
field relationship (association, aggregation, composition) and the
multiplicity (how many objects can hang off the other end) are estimated from
the type, `final`, how the field is initialised and JPA annotations (database
hints such as `@OneToMany`). External supertypes such as `JFrame` stay in as
nodes because they say a lot about what a class is for.

The `intellij` mode reproduces the class diagram of the IntelliJ IDEA
programming environment. For that it also reads the code inside the methods.
Every reference in the code becomes a dependency, even through chains of calls
such as `RaiseMeUp.getCurrentJob().getImpactenergy()`, where the target class
`Job` never appears in the text. `new X()` becomes `«create»`, fields get "1"
or "*", and inner classes get an edge of their own. With `--classes FILE` (one
fully qualified name per line) you choose which classes go into the diagram,
just as you would in IntelliJ. Without a selection every class goes in, which
quickly gets cluttered for large projects.

The rules of the IntelliJ mode come from the nine IntelliJ diagrams from
Zhang/Hebig and are described in folder 2, in
[`doku/intellij-nachbildung.en.md`](../2-java-extraktoren-benchmark-forschungsdaten/doku/intellij-nachbildung.en.md).
How the parser is built is described in
[`doku/java-parser.en.md`](../1-llm-pipeline-abstrakte-klassendiagramme/doku/java-parser.en.md)
in folder 1.

## Options

| Option | Meaning |
| :--- | :--- |
| `-o`, `--output` | output folder, default `uml-ausgabe` |
| `-f`, `--format` | any of `json`, `puml`, `png`, `svg`, default `json,puml` |
| `--name` | name to use in the output instead of the folder or repo name |
| `--stdout puml\|json` | print the result instead of writing files |
| `-m`, `--mode` | `literal` or `intellij` |
| `--members` | how much goes into the class boxes in `literal` mode: `structure`, `summary` (default), `public-api`, `full` |
| `--source-sets` | `auto` takes `src/main/java` or the folders named in `pom.xml` and `build.gradle`; `all` takes everything |
| `--include-generated` | read generated sources too |
| `--exclude-dir`, `--exclude-file` | exclude further patterns |
| `--no-default-excludes` | do not skip test folders, `target/`, `*Test.java` and so on |
| `--no-external-supertypes` | leave out external supertypes (`literal`) |
| `--method-dependencies` | dependencies from method signatures (`literal`) |
| `--javac`, `--classpath` | also resolve types through the JDK compiler (`literal`) |
| `--classes` | class selection (`intellij`) |
| `--ide-no-jdk`, `--ide-no-same-package` | imitate IntelliJ without a JDK or with a wrong source root (`intellij`) |
| `--ref`, `--keep-clone` | pick a branch or tag; keep the cloned copy |
| `--plantuml` | PlantUML JAR for PNG and SVG |
| `-v`, `--verbose` | print progress and hints |

## Output

One folder per repo, containing:

- `klassendiagramm.puml`: the PlantUML text.
- `klassendiagramm.json`: the graph with packages, nodes, edges and where each
  edge was found (file, line, field or method). The format is the same as
  `javagraph.json` in folder 1, so the pipeline can read it directly.
- `klassendiagramm.diagnostics.json`: only if there is something to report,
  such as files with syntax errors, duplicate classes or types that could not
  be resolved unambiguously.
- `klassendiagramm.png` or `.svg`, if requested.

Class IDs are shortened by the shared package prefix:
`de.firma.app.model.Kunde` becomes `model.Kunde`.

## How good the parser is

The measurements were made in [folder
2](../2-java-extraktoren-benchmark-forschungsdaten/README.en.md) with the code
from folder 1. The results apply here unchanged, because the two copies give
character-for-character identical output on all 59 projects from folder 2 in
four configurations (see [phase 6 in the main
README](../README.en.md#phase-6-the-parser-as-a-standalone-tool-november-2026)).

- Against diagrams drawn by people (30 Lindholmen projects and 9 Zhang/Hebig
  projects), the `literal` mode ties with javalang and is ahead of the other
  tools we tested. The tools that read bytecode did not run at all on most
  projects because those projects could not be compiled.
- Against IntelliJ: on seven of the nine projects the `intellij` mode produces
  exactly the same diagram as IntelliJ, with no edge missing and none extra.
  For Orekit and Neuroph every edge that could be checked in the picture
  matches (28 of 35 and 16 of 103). This needs the same class selection and
  the same environment (JDK or not, source root right or wrong) that the
  project had when it was opened in IntelliJ.

## Limits

- Without a build there is no information from libraries. A return type from a
  library ends a chain of calls, except for the common JDK collections.
- Overloaded methods (several methods with the same name) are told apart only by
  the number of arguments. Lambdas (short, nameless functions) without a
  declared type and hard-to-infer `var` declarations also end a chain of calls.
- Ambiguous types are left out and reported. When in doubt that costs a correct
  edge, but it avoids wrong ones.
- The `literal` mode only sees declarations. The fact that one class creates or
  calls another only shows up in `intellij` mode.
- Whether a field is a composition, aggregation or association in UML terms is
  not written in the code. The `literal` mode estimates it.

## Tests

Tests are small checking programs that automatically confirm the parser still
delivers what it should.

```bash
.venv/bin/python -m pytest
```

| File | Checks |
| :--- | :--- |
| `tests/test_java_parsing.py` | syntax tree, fields and multiplicities, encodings, prefix, modules, literal graph, javac, file selection |
| `tests/test_java_resolution.py` | resolving type names: imports, nested and inherited types, ambiguity |
| `tests/test_java_intellij.py` | IntelliJ mode: call chains, self-loops, fields with "1" and "*", environments |
| `tests/test_java_literal_benchmark.py` | the 20 small projects in [`benchmarks/java_literal/`](benchmarks/java_literal/README.en.md), each with a hand-checked graph |
| `tests/test_cli.py` | command line, output files, recognising URLs |

The first three were copied from folder 1 and adapted to the standalone
tool. The benchmark with the 20 small projects now only exists here.

## Layout

| Path | Contents |
| :--- | :--- |
| `javauml/cli.py` | command line |
| `javauml/api.py` | `extract` and `Options`; puts the steps together |
| `javauml/repo.py` | local path or Git URL |
| `javauml/sources.py` | which `.java` files are read |
| `javauml/java/ts_pass.py` | syntax tree with tree-sitter; classes, fields, methods |
| `javauml/java/resolution.py` | maps type names to classes in the project |
| `javauml/java/graph_builder.py` | `literal` mode |
| `javauml/java/intellij.py` | `intellij` mode |
| `javauml/java/javac_solver.py` | extra resolution through the JDK compiler |
| `javauml/java/import_graph.py` | package dependencies, only used by the tests copied from folder 1 |
| `javauml/model.py` | data classes for classes and fields |
| `javauml/schema/` | graph model, JSON, PlantUML |
| `javauml/render.py` | PNG and SVG through PlantUML |
| `benchmarks/java_literal/` | small test projects with the expected graph |
