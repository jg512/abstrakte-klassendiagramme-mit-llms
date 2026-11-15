[Deutsch](ergebnisse-lindholmen.md) · **English**

# Results: extractors on 30 Lindholmen projects and the Zhang/Hebig suite

As of 20 September 2026, with extensions to the extractor from 21 September 2026.

This file holds the results of the first comparison. Three tools that produce a
class diagram from Java source code, among them our extractor (the parser from
folder 1), were compared with the diagrams that belong to 30 projects from the
Lindholmen dataset and to the nine Zhang/Hebig projects. The nine Zhang/Hebig
projects are called the "suite" here (a fixed collection of test cases). The
file also describes which bugs in our extractor came to light along the way and
were fixed. The [main README](../../README.en.md#glossary) explains precision,
recall and F1. In the tables, "completed" means that the tool produced output
without crashing.

For the benchmark, 30 projects were downloaded from the Lindholmen dataset,
each together with its UML/XMI model from the same Git commit. Together that is
4,040 Java files. Three extractors got the same inputs and were compared with
each other.

The scores say how well the output fits the diagram. They do not tell you how
correctly the code was read. The diagrams in the repos may be incomplete,
abstracted, generated or out of date, so they are not a checked ground truth.

## Zhang/Hebig suite with three extractors

We also downloaded the replication package of the study by Zhang, Zhang, Strüber
and Hebig (2025) and ran the measurement on it. It contains nine Java projects
in the version that was studied, 79 classes in the models, 82 relationships as
counted by the authors, the original diagrams, the authors' annotations,
diagrams produced by reverse engineering, and one comparison table per project.
Three diagrams contain duplicate directed associations between the same classes.
If associations are counted without direction, 79 relationships remain.
`daten/zhang-hebig/reference.json` is a transcription of the diagrams made by
hand; the original pictures, PDFs and tables are next to it. The run times come
from this run. The later measurement with seven tools in
[`ergebnisse-zhang-hebig.en.md`](ergebnisse-zhang-hebig.en.md) is a separate run
with slightly different times.

| Extractor | completed | node recall | edge precision | edge recall | micro F1 | time |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| our extractor (fixed) | 9/9 | 0.924 | 0.757 | 0.671 | 0.711 | 0.24 s |
| javalang + adapter | 9/9 | 0.924 | 0.757 | 0.671 | 0.711 | 0.79 s |
| java2plantuml (mirajp1) | 9/9 | 0.924 | 0.827 | 0.544 | 0.656 | 6.83 s |

All three find the same 73 of 79 classes. According to the authors, the six
missing classes do not exist in the code in that form: five classes from
RaiseMeUp that are missing from the code or were implemented differently, and
the class `Link` in myblog, which only appears in the model. For the
relationships, our extractor and javalang are level. java2plantuml has a higher
precision but finds fewer relationships.

The later measurement with all seven tools is in
[`ergebnisse-zhang-hebig.en.md`](ergebnisse-zhang-hebig.en.md), and a closer
look at individual projects is in [`fallstudien.en.md`](fallstudien.en.md).

## Results on the 30 Lindholmen projects

Micro F1 counts all lines of all projects together; macro F1 is the average of
the F1 scores of the individual projects.

| Extractor | completed | edge precision | edge recall | micro F1 | macro F1 | time |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| our extractor, before | 30/30 | 0.770 | 0.561 | 0.649 | 0.739 | 7.51 s |
| our extractor, fixed | 30/30 | 0.739 | 0.574 | 0.646 | 0.736 | 8.56 s |
| javalang + adapter | 30/30 | 0.739 | 0.574 | 0.646 | 0.736 | 29.00 s |
| java2plantuml (mirajp1) | 30/30 | 0.756 | 0.466 | 0.577 | 0.684 | 59.68 s |

The scoring covered 470 classes and 399 relationships that could be matched
between model and source code. In total the models contained 1,182 named
classes and 829 relationships. Names that could not be matched, ambiguous
matches and unsupported references are recorded in
`daten/lindholmen/manifest.json`.

All tools found all matched classes (node recall 1.0). Since the matching
itself was prepared with javalang, though, this says little about how accurate
they are on nodes. Classes from the model that could not be matched were
excluded. Classes in the source code that do not appear in the diagram do not
count as errors.

The fixed extractor finds five more reference relationships (229 instead of 224
out of 399). At the same time it outputs 14 extra relationships that do exist in
the source code but are not in the diagram (81 instead of 67). As a result,
micro F1 drops slightly from 0.649 to 0.646. The extraction has not got worse;
rather, the score reflects the gap between what is in the code and what was
drawn in the diagram.

The run times are single measurements on one computer. They include parsing
and building the graph, and for java2plantuml also starting the JVM and
re-encoding to UTF-8. Downloading and preparing the references is not
included.

## Fixes to our extractor

The following points are fairly technical. In short, we fixed cases in which
the extractor assigned a name to the wrong class or missed a relationship.

- Full Java names as well as package and import information are kept.
  Explicit imports are no longer wrongly assigned to project classes with the
  same name.
- Wildcard imports and inherited nested types are resolved. Ambiguous matches
  are reported and left out.
- The class graph, the dependency graph and the inheritance graph use the same
  resolution, so that the clustering does not get contradictory data.
- Fields and methods in enums, constants in interfaces, and array brackets
  after the variable name are now recognised.
- Project classes inside generic classes of the project's own, such as
  `NeurophArrayList<Neuron>`, are recognised.
- Self-associations are kept, and classes in the default package are no longer
  confused with classes of the same name in named packages.
- The parser cache (a store for projects that have already been read) got a
  version number, so that no outdated entries are loaded.

Two things in the working environment were repaired along the way that have
nothing to do with the extractor itself: the Python environment (`.venv`) was
broken and was set up again, and an entry `runs/` in `.gitignore` had also
excluded the source package `src/runs/` (now `/runs/`).

13 new tests were added for these cases and for cyclic inheritance. Seven of
the first eight tests failed before the changes. The eighth (inherited type)
happened to pass with the old version as well, so it was made stricter. After
that, 385 tests passed (1 network test deselected), plus 10 tests for the
normalisation and the reference data. Among the 4,040 Java files there was no
file that tree-sitter could not parse.

The pipeline was also run with all eight variants as a dry run
(`--dry-run --no-cleanup`) on one Java project, and each time it wrote
diagrams and summaries. This only checks that the parts work together, not the
quality of real LLM diagrams. For the prune variants, the stand-in for the LLM
makes up extra classes, so the pipeline reports that the diagram has too many
classes. That is expected and not a bug.

## Extensions to the extractor

After that, the extractor was developed further. It now recognises the usual
and the configured source folders of Maven and Gradle, tells apart classes of
the same name in different build modules, offers four levels of detail for
members, and can optionally output dependencies through parameters and return
types. For each edge it stores the role (field or method), the declared type
and the evidence. Multiplicity and ownership are derived from `Optional`,
collections, arrays, `final` fields and common JPA annotations. Nested classes
with the same name get unique labels in PlantUML. Ambiguities, duplicate
declarations, parse errors and errors in javac resolution are written to a
separate file.

An optional `javac` mode can add resolution through the JDK's compiler API and
a given classpath. Results from the source code take precedence. By default
the extractor runs without a build.

A benchmark of our own with 20 fixed cases in modern Java (records, sealed
types, nested types, imports, generics, self-associations, multiplicity,
composition, JPA annotations, method dependencies) used to live in folder 1 and
is now in folder 3 under
[`benchmarks/java_literal/`](../../3-java-parser-klassendiagramme/benchmarks/java_literal/README.en.md).
The extractor passes all 20 cases. Of the project tests, 402 pass (1 network
test deselected).

The extended extractor was measured again on the same inputs. The scores on
the 30 projects stayed the same (node recall 1.000, edge precision 0.739,
recall 0.574, F1 0.646), and so did those on the Zhang/Hebig suite (node F1
0.961, edge F1 0.711). The results are in `ergebnisse/messungen/enhanced/` and
`ergebnisse/messungen/curated-enhanced/`.

## Examples checked against the code

- `hodiqual/projet2015`: hits go up from 31 to 33. The enum `TypePoint`
  contains a field `Map<String, TypePoint>`, that is, a field in the enum that
  refers to the enum itself.
- `jainebri/Super-Simple-Stocks`: hits go up from 10 to 11. The interface
  `SimpleStockServicesFactory` declares its own singleton `INSTANCE`.
- `Neseek77/gwt-ent`: hits go up from 2 to 3, through self-associations in a
  reflection API.
- `shadeven/cerebrumehr`: no tool finds any of the 96 edges. In the source
  code the relationships mostly sit on generated `*Base` classes, while the
  diagram shows the domain classes. So here the diagram depicts a different
  level from the code.
- Most of the extra edges are self-associations, such as value tables in enums
  or singletons. In Neuroph, a relationship through a generic class of the
  project's own was also missed; it is now recognised.

## Limitations

- The 30 projects are our own selection from a published dataset, not a gold
  standard checked by people.
- The selection favours small projects that are still available online with XML
  models that can be parsed as Java 8. Only one model per repo was used.
- Associations are compared without direction, multiplicity or ownership;
  inheritance and realization with direction and type.
- The comparison with javalang relies on an adapter of our own with simpler type
  resolution.
- Time limits: 120 seconds per adapter, 90 seconds for java2plantuml. All runs
  finished within this time.
- Not measured: how well an LLM abstracts from this, whether annotations are
  interpreted correctly, whether more would be found with the libraries
  available (on the classpath), and whether every relationship found is right in
  substance.

As a check, all 90 runs on the Lindholmen projects (30 projects times 3 tools)
and all 27 runs on the Zhang/Hebig suite (9 times 3) were repeated. Status,
node and edge scores and differences were identical
(`ergebnisse/messungen/reproduction-verification.json`).

## Files

- [`doku/recherche-datensätze.en.md`](recherche-datensätze.en.md): papers,
  rejected alternatives, scoring rules
- `daten/lindholmen/manifest.json`: the 30 fixed pairs of project, commit,
  model and source code
- `daten/lindholmen/reference-graphs/`: normalised references in JSON and
  PlantUML; the originals are under `daten/lindholmen/corpus/`
- `ergebnisse/messungen/before/`, `ergebnisse/messungen/final/`,
  `ergebnisse/messungen/comparison.json`, `ergebnisse/messungen/aggregate.json`:
  raw data and results
- `daten/zhang-hebig/` and `ergebnisse/messungen/curated-final/`: Zhang/Hebig
  package, transcription, checksums and results
- `daten/lindholmen/discovery.json`, `daten/lindholmen/acquisition.json`,
  `daten/lindholmen/preparation-exclusions.json`: selection and failures
- `ergebnisse/protokolle/`: logs of all runs and tests
- `daten/lindholmen/syntax-audit.json`, `ergebnisse/pipeline-trockenlauf/`:
  syntax check and dry run of the pipeline
- `ergebnisse/messungen/enhanced/`, `ergebnisse/messungen/curated-enhanced/`:
  runs after the extensions

## Agreement per project

| Project | Java files | matched nodes | reference edges | F1 ours before | F1 ours fixed | F1 javalang | F1 java2plantuml |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| [qingyu1229/hhxxttxs](https://github.com/qingyu1229/hhxxttxs/tree/fc72e129a8142ff5b221e6902926b4bb3b5b3404) | 58 | 3 | 3 | 0.800 | 0.800 | 0.800 | 0.500 |
| [greengie/PigRunGame](https://github.com/greengie/PigRunGame/tree/385315d553d498e3482f5ca3e4440c7078703f86) | 9 | 9 | 7 | 1.000 | 1.000 | 1.000 | 0.833 |
| [brunotriggolabs/testepoo](https://github.com/brunotriggolabs/testepoo/tree/e9ad647daabfdacb1c6dde6fe31670b995a6f362) | 48 | 4 | 2 | 0.000 | 0.000 | 0.000 | 0.000 |
| [ConfuddledPenguin/Countdown](https://github.com/ConfuddledPenguin/Countdown/tree/47cee83485e24b291ae077dc7f4d769ac919e483) | 16 | 18 | 22 | 0.978 | 0.978 | 0.978 | 1.000 |
| [shadeven/cerebrumehr](https://github.com/shadeven/cerebrumehr/tree/02dab5a8185d5db2c9128aa0cd2c908d09cc64f9) | 507 | 84 | 96 | 0.000 | 0.000 | 0.000 | 0.000 |
| [cjurden/calc](https://github.com/cjurden/calc/tree/5fe187148feadb86aecf68219830d83ff6ba824e) | 5 | 9 | 2 | 1.000 | 1.000 | 1.000 | 1.000 |
| [SofiaReis/mfes-green-way](https://github.com/SofiaReis/mfes-green-way/tree/8558ac8bda63a77d1faea8531daf7e122f6fe89e) | 20 | 9 | 6 | 1.000 | 1.000 | 1.000 | 1.000 |
| [zenki2001cn/Erengine](https://github.com/zenki2001cn/Erengine/tree/f5e38a62d437b4cfde72efe9582db316c57709cc) | 588 | 6 | 4 | 0.750 | 0.667 | 0.667 | 0.667 |
| [juli1/rdalte](https://github.com/juli1/rdalte/tree/79090e3ae766c162c1dff65432fd52612e704de6) | 653 | 30 | 41 | 0.473 | 0.426 | 0.426 | 0.473 |
| [lorandszakacs/UPT-Projects](https://github.com/lorandszakacs/UPT-Projects/tree/9398bc0c81a225d10492a94bf2b436fe4f1abd48) | 240 | 7 | 2 | 0.333 | 0.250 | 0.250 | 0.400 |
| [sfotiadis/SEMonitor](https://github.com/sfotiadis/SEMonitor/tree/bff188fb74b3c1cc4351c1826fb2da1421fe45b9) | 12 | 10 | 5 | 0.769 | 0.769 | 0.769 | 0.545 |
| [adichad/lucene-new](https://github.com/adichad/lucene-new/tree/ddfd6f2b12c34d97e70b1a92de69d138ee1b666d) | 696 | 28 | 32 | 0.316 | 0.339 | 0.339 | 0.250 |
| [hodiqual/projet2015](https://github.com/hodiqual/projet2015/tree/95f605e54b6435c75d211f4c41d4d7ab249c9d7f) | 68 | 49 | 35 | 0.873 | 0.880 | 0.880 | 0.788 |
| [21268879/University](https://github.com/21268879/University/tree/6d8fbefd1f7e08823a2a40f7305569af8d5ff365) | 6 | 6 | 2 | 0.800 | 0.800 | 0.800 | 1.000 |
| [l7ol2aGol7z/To-The-Skies](https://github.com/l7ol2aGol7z/To-The-Skies/tree/d5df0d46a7a04f268179fb1f1833dcf7e0d6441a) | 12 | 12 | 19 | 1.000 | 1.000 | 1.000 | 0.848 |
| [KourdacheHoussam/UMLRefactoringTP3](https://github.com/KourdacheHoussam/UMLRefactoringTP3/tree/130edb7ad533207c0c5207b8eaacfa6bc18ec246) | 30 | 5 | 1 | 1.000 | 1.000 | 1.000 | 1.000 |
| [Neseek77/gwt-ent](https://github.com/Neseek77/gwt-ent/tree/c623f538e192b0e63793c20042bf859c73237e61) | 411 | 9 | 12 | 0.267 | 0.375 | 0.375 | 0.267 |
| [rewiko/LocateWind](https://github.com/rewiko/LocateWind/tree/4c7b7140088ee27979a1fba3dfa7f426ffd31f83) | 11 | 9 | 4 | 1.000 | 1.000 | 1.000 | 0.857 |
| [rtyanas/MyPics](https://github.com/rtyanas/MyPics/tree/a88c0dbb0ac87f74245c158fe4ebaa7e1f5e8567) | 11 | 12 | 2 | 0.500 | 0.500 | 0.500 | 0.500 |
| [LipliStyle/Liplis-Android](https://github.com/LipliStyle/Liplis-Android/tree/b3c27c53ad7faa206f6aabddcd4a32fc4dc6b92c) | 93 | 24 | 17 | 0.970 | 0.970 | 0.970 | 0.867 |
| [xyzker/Survey](https://github.com/xyzker/Survey/tree/cecebc67a75985121eb0fe45d90312fc501fd0f1) | 60 | 4 | 3 | 1.000 | 1.000 | 1.000 | 1.000 |
| [UbiCompForAll/UbiComposer](https://github.com/UbiCompForAll/UbiComposer/tree/eb2dfc62fed779f0a981a60f2465dc5e56b867f1) | 154 | 21 | 12 | 0.621 | 0.621 | 0.621 | 0.720 |
| [Simondin/ModelCombinationTree](https://github.com/Simondin/ModelCombinationTree/tree/43623cf9ee97b65b355a1a4edb04c84bde0e755d) | 35 | 18 | 26 | 1.000 | 1.000 | 1.000 | 0.667 |
| [jainebri/Super-Simple-Stocks](https://github.com/jainebri/Super-Simple-Stocks/tree/fef3b126e4b384e71e2662f0be3d07a8c2dd4b7c) | 14 | 12 | 11 | 0.952 | 0.957 | 0.957 | 0.842 |
| [Abdielja/AsiDriver](https://github.com/Abdielja/AsiDriver/tree/ed09f0573e98f7fc7078ed40d1c6fc001865f139) | 10 | 9 | 4 | 0.667 | 0.667 | 0.667 | 0.667 |
| [BGCX262/zyw-bank-management-svn-to-git](https://github.com/BGCX262/zyw-bank-management-svn-to-git/tree/c24ac18259d08c06022e1ca0adb2fc649acb93f1) | 39 | 7 | 6 | 0.923 | 0.923 | 0.923 | 1.000 |
| [dearsalisa/HappyWhale](https://github.com/dearsalisa/HappyWhale/tree/2b4fe24e2e71aada6d7afb09a793c3c8d3020ab6) | 6 | 4 | 4 | 1.000 | 1.000 | 1.000 | 0.667 |
| [aheizenreder/pac-ressys](https://github.com/aheizenreder/pac-ressys/tree/78468dc1a2cab23c996359535614da660a26f25b) | 67 | 5 | 4 | 0.857 | 0.857 | 0.857 | 0.857 |
| [TristanFAURE/pickerExplorer](https://github.com/TristanFAURE/pickerExplorer/tree/6145e466f1aa6065761fa3ea8e95c5d352fde002) | 85 | 37 | 7 | 0.368 | 0.359 | 0.359 | 0.378 |
| [CMCDelhiQuasar/Quasar-3-June](https://github.com/CMCDelhiQuasar/Quasar-3-June/tree/e0be833b1f20db5798111e67b40157875e262338) | 76 | 10 | 8 | 0.941 | 0.941 | 0.941 | 0.941 |
