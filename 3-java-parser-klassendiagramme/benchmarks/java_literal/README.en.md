[Deutsch](README.md) · **English**

# Benchmark: class graphs from modern Java

A benchmark is a fixed test that gets the same input every time it runs. This
suite (a collection of test cases) checks whether the Java parser reads the
classes and relationships inside a project exactly as they are written in the
code. Unlike the benchmark in
[folder 2](../../../2-java-extraktoren-benchmark-forschungsdaten/README.en.md),
the reference here is not an abstracted diagram drawn by a person. The
comparison is with what is provably in the code.

The suite consists of 20 small, independent projects, each only a few lines of
code and each testing one particular case. Together they cover plain fields,
arrays, standard and home-made generics, `Optional`, maps, records, sealed
types, nested types, imports, inheritance between interfaces, realization,
self-references, composition, multiplicities taken from JPA annotations and
the optional method dependencies.

The expected graphs in `manifest.json` were checked by hand against the code
samples. The general terms are explained in the [main
README](../../../README.en.md#glossary), the Java terms in the [parser
description](../../../1-llm-pipeline-abstrakte-klassendiagramme/doku/java-parser.en.md#java-terms-used-here).
The suite runs as part of the normal tests and can also be started on its own
(from the folder `3-java-parser-klassendiagramme`):

```bash
.venv/bin/python -m benchmarks.java_literal.run --output benchmarks/java_literal/results.json
```

At the moment all 20 cases pass (`results.json`). The suite needs no build and
gives the same result on every run.
