[Deutsch](README.md) · **English**

# Abstract class diagrams with LLMs

This project looks at whether a language model (an LLM, the kind of model
behind ChatGPT) can read the code of a piece of software and draw a clear
picture of how it is built. The picture should show only what matters, the way
an experienced developer who knows the system would draw it.

This page is the starting point. It explains the project for readers who have
never programmed and points to every other document. Technical terms are
explained the first time they come up, and you can look them all up again in
the [glossary](#glossary) at the end.

## Contents

- [What this is about](#what-this-is-about)
- [Why it is useful](#why-it-is-useful)
- [Why a language model](#why-a-language-model)
- [How it works](#how-it-works)
- [How to tell whether a diagram is good](#how-to-tell-whether-a-diagram-is-good)
- [What we have found so far](#what-we-have-found-so-far)
- [Guide to the documents](#guide-to-the-documents)
- [How the project developed](#how-the-project-developed)
- [Where things stand](#where-things-stand)
- [Problems and how they were solved](#problems-and-how-they-were-solved)
- [Open questions](#open-questions)
- [Glossary](#glossary)

## What this is about

Software is made of **source code**: text written in a programming language
that tells the computer what to do. Larger programs are split into
**classes**. A class describes one kind of thing the program deals with.
Software for a public library might have a class `Book` and a class `Library`.
A class has **attributes** (the data it keeps, such as a book's title) and
**methods** (the things it can do, such as adding a book).

Here is what that looks like in the Java programming language:

```java
public class Book {
    private String title;           // every book has a title
}

public class Library {
    private List<Book> books;       // a library holds a list of books
    public void add(Book b) { ... }
}
```

Classes depend on each other. A library contains books, a novel is a special
kind of book, a loan refers to a book and to a person. A **class diagram**
draws these connections: every class is a box and every relationship is a
line. **UML** (Unified Modeling Language) is the standard set of drawing
rules for software that says what the boxes and lines look like. A diamond at
the end of a line means "has as a part", a triangle means "is a special kind
of".

```
┌────────────┐               ┌──────────┐
│  Library   │◇──────────────│   Book   │
│            │ books    0..* │ title    │
└────────────┘               └──────────┘
                                   △
                                   │  "is a"
                             ┌──────────┐
                             │  Novel   │
                             └──────────┘
```

In words: a library has any number (`0..*`) of books, and a novel is a book.
This project writes diagrams in **PlantUML**, a text format that a program turns
into a picture. The line `Library o-- "0..*" Book : books` produces the
connection at the top.

A diagram like this is quick to draw for two classes. Real programs, though,
have hundreds or thousands of classes, and a diagram that shows all of them is
so crowded that nobody can make sense of it. When people explain a system they
draw an **abstract** class diagram instead. It leaves out helper classes,
technical detail and test code and shows only the central classes and how they
fit together. Think of a subway map: it leaves out the streets, the buildings
and the real distances, and that is exactly why it beats a street map when you
want to know how to get from A to B.

The goal of the project is to produce diagrams like that automatically.

## Why it is useful

- Anyone who joins a software project first has to work out how it is put
  together. A good overview diagram saves days of reading.
- Hand-drawn diagrams go stale because the code keeps changing and nobody
  updates the picture. A diagram you can regenerate at any time stays current.
  This project, too, found that drawn diagrams can drift a long way from the
  code (see the [case
  studies](2-java-extraktoren-benchmark-forschungsdaten/doku/fallstudien.en.md)).
- Many companies run software that was written years ago by people who have long
  since left. You have to understand such a system before you can change or
  replace it.
- Research and teaching are interested in how people abstract when they draw:
  what they leave out and what they keep. This is still poorly understood. A
  tool that imitates those choices makes them measurable.

## Why a language model

A program that reads source code and works out its structure is called a
**parser**. It is a bit like someone parsing a sentence in grammar class: they
can pick out the subject, verb and object without caring what the sentence
means. A parser reliably finds every class and every relationship in the code.
What it cannot do is judge which of them matter for understanding the system.
Nothing in the code says that `Library` is central and `DateFormatter` is a
side issue.

That judgement is the LLM's job. An **LLM** (large language model) is a program
trained on huge amounts of text, including a lot of source code, so it can read
code and answer questions about it. GPT, Gemini and DeepSeek are well-known
examples. In this project the model does not get the raw code. It gets what the
parser found and picks from that. So the work is split: the parser supplies
exactly what is in the code, and the LLM makes the selection.

## How it works

The processing runs as a series of steps, one after the other. A chain like
this is called a **pipeline**.

1. **Read the code.** You point the pipeline at a **repository** (repo for
   short: the folder of a software project, often hosted on GitHub). It
   collects all the source files and skips tests and generated files.
2. **Static analysis.** The parser reads the code without running it (that is
   what "static" means). It lists every class with its attributes and methods
   and builds the full **class graph**: all classes as points (**nodes**) and
   all relationships as connections (**edges**).
3. **The LLM picks.** The model works with **tools**, commands it is allowed to
   call, such as "show me class X", "read this file" or "add this class and
   this line to the diagram". It builds the diagram over several steps and
   decides for itself what to do next. A model that works on its own with
   tools like this is called an **agent**. So that it does not go on forever,
   it has a **budget**, a cap on how much text it may use up.
4. **Check and repair.** A checking program (the **validator**) removes lines
   to classes that do not exist, duplicates and the like.
5. **Output.** At the end you get the diagram as PlantUML and as **JSON** (a
   text format for structured data that programs read easily), plus a log of
   every request sent to the model with its cost and duration.

There are eight ways to set up how the model works (the **variants**). It can
start from a blank page and add the important classes, or it can be handed the
complete diagram and cross out what does not matter (the project calls this
`prune`). At the start it sees either an overview of the **packages** (folders
that hold classes belonging together), groups of closely connected classes, or
the full list of all classes. And it is either allowed to look at the source
code itself or not (`peek`). Not every combination makes sense. A model that is
handed the complete diagram already sees every class, so for it the choice of
starting overview falls away and only `peek` remains. That gives six variants
that start empty (three kinds of overview, each with and without `peek`) and two
that cross out, eight in all. All variants share the same instructions and the
same budget, so they can be compared fairly. The details are in the [folder 1
README](1-llm-pipeline-abstrakte-klassendiagramme/README.en.md).

The pipeline handles two programming languages, **Python** and **Java**. For
Java we wrote our own parser because the existing tools were not good enough
(more on that below). The parser also exists as a standalone program,
`javauml`, which draws a complete class diagram of a Java project without any
LLM.

## How to tell whether a diagram is good

To measure how good a generated diagram is, you need a correct answer to
compare it with. That reference is called the **ground truth**. Here it means
diagrams that people drew for real projects, or, when checking the parser,
the relationships that are provably in the code.

A **benchmark** is a fixed comparison test: every tool gets the same input,
and every result is compared with the reference in the same way. We count how
many classes and lines match. That gives three standard scores, each between 0
and 1:

- **Precision**: what share of the lines a tool drew are correct?
- **Recall**: what share of the correct lines did it find?
- **F1**: a single score that combines the two. It is only high when both are
  high.

An example: the reference has 4 lines. A tool draws 5 lines, 3 of which are
correct. Precision is 3 out of 5 = 0.60, recall is 3 out of 4 = 0.75, and F1
is 2 · 0.60 · 0.75 / (0.60 + 0.75) = 0.67. A tool that simply drew every
possible line would get a recall of 1 but a terrible precision, and F1
punishes that.

Across many projects there are two ways to average. **Micro F1** adds up the
hits of all projects first and then calculates once. **Macro F1** calculates
the score for each project and then takes the mean, so a small project counts
as much as a large one.

For the parser, a comparison like this is clear-cut, because it is supposed to
deliver exactly what is in the code. For the LLM's diagrams it is harder. An
abstract diagram leaves out a lot on purpose, and two experts would not keep
exactly the same classes. How best to measure the quality of such a diagram is
therefore still open (see [open questions](#open-questions)).

One thing to keep in mind when reading the results: a score below 1 does not
necessarily mean the tool got it wrong. Drawn diagrams are often out of date or
describe a design that ended up being built differently. The case studies in
folder 2 show this with real projects.

## What we have found so far

- On the small Python project `schedule`, the best
  variants running on the DeepSeek model found the two central classes in every
  repetition. All 24 runs together cost about 0.15 US dollars. The project is
  too small to draw general conclusions from, though.
- For Java there is a parser of our own. It was tested on 39 public Java
  projects with drawn diagrams from two research datasets: 30 projects from the
  Lindholmen dataset and 9 from a study by Zhang, Zhang, Strüber and Hebig
  (Zhang/Hebig for short). There it scores exactly the same as javalang, the
  best of the other tools we tested. That is no surprise, since both read
  the same information from the code and are scored by the same rules. Its
  advantages lie elsewhere: it understands newer versions of Java, copes with
  old file formats, works even when a project cannot be built, and records for
  every line the place in the code it comes from.
- IntelliJ IDEA is a widely used programming
  environment that can draw class diagrams itself. The parser got a second
  mode that reproduces exactly those diagrams. On seven of nine projects the
  result matches IntelliJ's picture completely.
- The most important step is still open: the LLM variants have not yet been
  run with a real model on Java projects and compared with the diagrams people
  drew.

The details and numbers are in the documents listed in the guide below.

## Guide to the documents

The project has three numbered folders. They were created in that order, and
each builds on the one before.

| Folder | What it contains | When |
| :--- | :--- | :--- |
| [`1-llm-pipeline-abstrakte-klassendiagramme/`](1-llm-pipeline-abstrakte-klassendiagramme/) | the pipeline of parser and LLM with its eight variants, for Python and Java, and the runs with real models | May to September 2026 |
| [`2-java-extraktoren-benchmark-forschungsdaten/`](2-java-extraktoren-benchmark-forschungsdaten/) | a comparison of Java tools on public research data: 30 projects from the Lindholmen dataset and 9 projects from Zhang/Hebig with hand-abstracted diagrams, plus case studies and the IntelliJ reproduction | September and October 2026 |
| [`3-java-parser-klassendiagramme/`](3-java-parser-klassendiagramme/) | the Java parser as the standalone tool `javauml`: a Java project goes in, a class diagram comes out, no LLM involved | November 2026 |

The folder names are German because the project was run in German. Every
document exists in German and in English. The English version has the same
name with `.en` added, so `README.en.md` sits next to `README.md`.

The project comes in two forms. The **repository on GitHub**
(`jg512/abstrakte-klassendiagramme-mit-llms`) holds the code, the documents and
our own metadata, but no large data. The **full project folder**, as handed over
to the university, also contains the downloaded datasets, the built third-party
tools and all stored runs and measurement results (just under 1 GB in total).
Wherever it says "only in the full project folder" below, that file is not in
the GitHub repository. How to download the data yourself is described in
[`INSTALLATION.en.md`](INSTALLATION.en.md).

### General

| Document | What you find there | Read it when |
| :--- | :--- | :--- |
| [`INSTALLATION.en.md`](INSTALLATION.en.md) | how to set everything up on a new machine, directly or with Docker, and how to repeat the measurements | you want to try something yourself or rerun the measurements |

### Folder 1: the LLM pipeline

| Document | What you find there | Read it when |
| :--- | :--- | :--- |
| [`1-…/README.en.md`](1-llm-pipeline-abstrakte-klassendiagramme/README.en.md) | how the pipeline works, the eight variants and why they are built the way they are, results on `schedule` and `loguru`, how to run it | you want to understand how the LLM works and what it has achieved so far |
| [`1-…/doku/java-parser.en.md`](1-llm-pipeline-abstrakte-klassendiagramme/doku/java-parser.en.md) | how the Java parser turns code into a class graph step by step, with a worked example of two classes | you want to understand, change or check the parser |

The stored runs are in `1-…/runs/`. Each run has a short `summary.md` that the
program wrote itself. That folder is too big for GitHub and only exists in the
full project folder.

### Folder 2: benchmark on research data

| Document | What you find there | Read it when |
| :--- | :--- | :--- |
| [`2-…/README.en.md`](2-java-extraktoren-benchmark-forschungsdaten/README.en.md) | the research questions, the main results and how the folder is laid out | as your way into folder 2 |
| [`2-…/doku/recherche-datensätze.en.md`](2-java-extraktoren-benchmark-forschungsdaten/doku/recherche-datensätze.en.md) | which datasets with Java code and diagrams exist, which ones we picked and why, and the rules for comparing | you want to know where the reference data comes from |
| [`2-…/doku/ergebnisse-lindholmen.en.md`](2-java-extraktoren-benchmark-forschungsdaten/doku/ergebnisse-lindholmen.en.md) | three tools on 30 Lindholmen projects and the Zhang/Hebig projects, the bugs found and fixed in the parser, a table per project | you want the full numbers of the first comparison |
| [`2-…/doku/ergebnisse-zhang-hebig.en.md`](2-java-extraktoren-benchmark-forschungsdaten/doku/ergebnisse-zhang-hebig.en.md) | all seven tools on the Zhang/Hebig projects and why most of them fail at building the projects | you want the big tool comparison |
| [`2-…/doku/fallstudien.en.md`](2-java-extraktoren-benchmark-forschungsdaten/doku/fallstudien.en.md) | three projects in detail: is a mismatch the tool's fault or the diagram's? | you want to see why diagram and code drift apart |
| [`2-…/doku/intellij-nachbildung.en.md`](2-java-extraktoren-benchmark-forschungsdaten/doku/intellij-nachbildung.en.md) | the rules IntelliJ follows when it draws diagrams and how closely the parser reproduces them | you are interested in the IntelliJ mode |
| [`2-…/doku/werkzeuge.en.md`](2-java-extraktoren-benchmark-forschungsdaten/doku/werkzeuge.en.md) | where the seven compared tools come from, their versions and how to build them | you want to build the tools yourself |
| [`2-…/doku/reproduzieren.en.md`](2-java-extraktoren-benchmark-forschungsdaten/doku/reproduzieren.en.md) | every command needed to repeat the measurements | you want to rerun them |
| [`2-…/daten/zhang-hebig/README.en.md`](2-java-extraktoren-benchmark-forschungsdaten/daten/zhang-hebig/README.en.md) | what is in the data package of the Zhang/Hebig study and how the reference was built from it | you work with that data |
| [`2-…/ergebnisse/diagramme/README.en.md`](2-java-extraktoren-benchmark-forschungsdaten/ergebnisse/diagramme/README.en.md) | what the comparison pictures show, the reference next to every tool | you look at the pictures (only in the full project folder, not on GitHub) |

`2-…/ergebnisse/pipeline-trockenlauf/` also holds automatically generated
summaries of a test run of the pipeline without an LLM, again only in the full
project folder. The READMEs under `2-…/werkzeuge/` and
`2-…/daten/lindholmen/corpus/` belong to other people's projects that are only
here as study material.

### Folder 3: javauml

| Document | What you find there | Read it when |
| :--- | :--- | :--- |
| [`3-…/README.en.md`](3-java-parser-klassendiagramme/README.en.md) | installing and using the tool, its two modes, options, output and limits | you want a class diagram of a Java project |
| [`3-…/benchmarks/java_literal/README.en.md`](3-java-parser-klassendiagramme/benchmarks/java_literal/README.en.md) | 20 small test projects that check whether the parser reads exactly what is in the code | you want to know how the parser itself is tested |

## How the project developed

The project ran from January to November 2026 in seven phases. They are
described in some detail here because each decision grew out of the problems
of the phase before.

### Phase 0: local open-source models and fine-tuning (January to April 2026)

The first plan was to run a freely available (**open-source**) model on our
own hardware and possibly specialise it for the task through **fine-tuning**,
that is, extra training on examples. That did not work, for several reasons:

- The hardware we had could only run models up to about 24 billion
  **parameters** (the size of a model, roughly the number of values it can
  adjust), and fine-tuning needs even more.
- Models of that size could not reliably tell which classes matter.
- A whole repository did not fit into the **context window**, the amount of
  text a model can take in at once.
- The models often ignored the required JSON format, so their answers could
  not be processed further.

So the approach changed. Instead of a model of our own, the aim became a
general program around the model (a **harness**) in which the model can be
swapped out and which steers it through well-designed instructions (**prompt
engineering**; a **prompt** is the instruction you give the model). The focus
moved to the pipeline: static analysis, tools for the model, and checking and
repairing its answers.

### Phase 1: a Python pipeline with five methods (until the end of May 2026)

This is when the pipeline in folder 1 was built, at first for Python only.
Instead of raw code, the LLM gets what a parser found (the classes, their
attributes and methods, the **import graph**, meaning which file uses which
other file, and the full class graph from the tool `pyreverse`) and picks from
that. We tried five methods:

- additive, starting from an empty diagram and building it up: package by
  package (M1), as an agent that can read the code (M2), or separately for each
  group of closely connected files (a **cluster**) and merging the results
  afterwards (M3)
- subtractive, starting from the full class graph and removing classes:
  without (M4a) and with the ability to read the code (M4b)

The models were connected through the `litellm` library (a **library** is
ready-made code you build into your own programs), which puts many providers
behind one interface. The test subjects were three Python repos:
`schedule` (about 1,000 lines of code), and `loguru` and `transitions` (about
5,000 lines each).

First we tried an open-source model again (`qwen2.5:14b`), run locally through a
program called Ollama. The problems from phase 0 came back but were easier to
deal with. Ollama's context window defaults to 2,048 **tokens** (a token is a
piece of a word, about four letters in English; text size, limits and prices are
all counted in tokens), and we raised it to 32,768. When a model returns invalid
JSON, the request is repeated once with a hint about what to fix. Very small
models such as `qwen2:0.5b` were only good for checking that the plumbing
worked.

After that we tried Gemini (`gemini-2.5-pro`, runs on 22 and 29 May) and later
DeepSeek (`deepseek-chat`) through their **APIs**, that is, over the internet
on the provider's servers. Both produced usable diagrams. With weaker models
such as `flash-lite`, a small and cheap version of Gemini, the methods M2 and
M3, in which the model works as an agent, returned empty or nearly empty
diagrams.

The biggest problem was the growing context. An agent sends the whole
conversation so far with every single step. Each tool call makes the requests
bigger, until the budget or the context window runs out. DeepSeek, for
example, read the entire codebase first and only then started adding classes,
which came to about 1,500 tokens per class. Beyond roughly 20 classes, the
variants that start from an empty diagram used up their budget before they
ever produced a diagram.

### Phase 2: one shared process instead of five programs (June and July 2026)

The five methods were separate programs with their own prompts and budgets,
which made them hard to compare. At the start of July they were merged into
one control program (the **driver**). Since then the methods differ in only
three settings: what the diagram starts from, what goes into the first prompt,
and whether the model may read the code. Together these give the eight
variants, all with the same tools, prompts and budgets.

Several changes came in along the way to deal with the growing context and the
models' typical mistakes: a single tool that adds classes and lines in one
call, feedback on the current size of the diagram after every change, a
reminder to finish up that depends on how much budget is left, access to the
code only after a first draft exists, and an optional summary of the
conversation so far. The reasons for each are in the
[folder 1 README](1-llm-pipeline-abstrakte-klassendiagramme/README.en.md).

On 7 July we compared against a ground truth for the first time, on
`schedule` with `deepseek-chat`. The ground truth there has only two classes:
`Scheduler` (the schedule) and `Job` (a scheduled task). The variants that work
with the full class graph (`prune`, `prune-peek`, `catalog`) found both in
every repetition and added nothing else. The 24 runs together cost about
0.15 US dollars. On 13 July a run with five repetitions per variant on
`schedule` and `loguru` followed, to see how much the results vary from run to
run. Each repetition uses a different **seed**, a starting value for the
randomness the model uses when it writes its answers.

### Phase 3: switching to Java and choosing a parser (August 2026)

A meaningful evaluation needed reference diagrams, and there were none.
`schedule` has only two relevant classes, and for Python there are hardly any
collections of projects that come with code and a matching UML diagram. For
Java there are many more: the Lindholmen dataset alone lists over 93,000 UML
files in projects on GitHub.

So the pipeline was extended to Java. Everything after the static analysis
stays the same; only the parser is different.

First we tested existing open-source tools. As the reference we used a ground
truth taken from the **bytecode**. Before Java code runs, a **compiler**
translates it into a lower-level form (this is called compiling), and the
relationships can be read off that bytecode exactly. (The material from this
first comparison is not kept in this project, only its result.) None of the
tools was up to the job:

- The tools that read bytecode (plantuml-generator, Java2PlantUML by juanmf,
  genuml) need
  a project that compiles completely. That requires every **library** to be
  present, meaning the third-party code the project relies on. If one is
  missing, they fail. genuml does not output any relationships at all.
- java2plantuml by mirajp1, a different tool with almost the same name that
  reads source code, crashes on files that store umlauts and other special
  characters in an older form (the ISO-8859-1 **encoding** instead of today's
  usual UTF-8). It still reports success and outputs an empty diagram.
- javalang reads older code very accurately but only understands Java up to
  version 8, so it fails on newer language features such as records (a short
  way to write classes that only hold data) and sealed types (classes that say
  who may inherit from them).
- jdeps (which ships with Java) only reports which class uses which, without
  saying what kind of relationship it is, and it misses inheritance.

So we wrote our own parser, based on the `tree-sitter-java` library. It reads
only the source code and never needs to build the project, detects the
encoding of each file separately, and keeps superclasses from third-party
libraries (such as `JFrame` for program windows, which says a lot about what a
class is for). The comparison turned up three bugs in the parser (inheritance
between interfaces, resolving nested types, shortened names), which were fixed
straight away. After that, on the projects checked at the time, it found every
relationship that is present in the source code.

Something else came up along the way. If you compare classes only by their
short name (`Kunde` instead of `de.firma.model.Kunde`), mistakes go unnoticed
whenever two classes in different packages share a short name. So the parser
works out for every name exactly which class is meant (the **resolution** of a
name). When that is ambiguous, it reports the case instead of guessing.

### Phase 4: benchmark on research data (September and October 2026)

The ground truth from bytecode tells you whether the parser reads correctly.
What the project needs, though, are diagrams drawn by people. Folder 2 holds
the search for that kind of data and the measurements:

- 30 projects from the Lindholmen dataset, with code and diagram taken from the
  same point in the project's history (the same **commit**, which is what a
  saved snapshot is called in the version control system Git). Our parser ties
  with javalang and beats java2plantuml. Along the way several bugs in the
  parser were found and fixed. After that new features were added, for example
  recognising the usual folder layout of Java projects and recording for every
  line the place in the code it comes from.
- 9 projects from the study by Zhang, Zhang, Strüber and Hebig (2025,
  Zhang/Hebig for short), whose
  diagrams were deliberately abstracted by people. Seven tools were compared.
  Only three of the nine projects can be compiled, so the bytecode tools
  barely ran. The tools that read source code ran on every project.
- The case studies (5 and 6 October) showed that in the project RaiseMeUp
  most of the mismatches are down to the diagram. It describes a design that
  was built differently in the code. The diagram has classes `Dog`, `Cat`,
  `Fish` and `Penguin`, for instance, while the code just stores the kind of
  animal as a value in a field.

### Phase 5: indirect connections, the way IntelliJ draws them (October 2026)

Commercial UML tools show connections the parser did not see, because it only
read the **declarations**, the places where classes, fields and methods are
announced. That means it looked at the fields and at `extends` ("inherits from")
and `implements` ("fulfils the interface"), but not at the code inside the
methods. IntelliJ also reads what is inside the methods. In the RaiseMeUp
project this means `PetObserver` depends on `Job` even though the word `Job`
never appears in it. The connection runs through a third class, via the call
`RaiseMeUp.getCurrentJob().getImpactenergy()`: the class `RaiseMeUp` hands back
a `Job`, and a value is read from that job. Connections that take a detour like
this are called **transitive**.

So the parser got a second mode that reproduces IntelliJ's class diagrams. We
worked out the rules from the nine IntelliJ diagrams in the Zhang/Hebig data
package: dependencies from every reference in the code, including chains of
calls, the label `«create»` when one class creates an object of another,
fields marked "1" or "*" (one or many), inner classes (classes written inside
another class), and inheritance that
skips over classes not shown in the diagram. This also revealed that IntelliJ
had loaded the projects with varying success, sometimes without Java's
standard library (the **JDK**), sometimes with the source folder set up
wrongly. The parser can imitate both.

On seven of the nine projects the parser produces the same diagram as IntelliJ.
For the other two, Orekit and Neuroph, IntelliJ's pictures are so crowded that
not every line can be traced. There, every line that could be checked in the
picture matches. The details are in
[`intellij-nachbildung.en.md`](2-java-extraktoren-benchmark-forschungsdaten/doku/intellij-nachbildung.en.md).

### Phase 6: the parser as a standalone tool (November 2026)

The Java parser is useful without the LLM pipeline too, for example to get a
complete class diagram of any Java project in a hurry. Folder 3 therefore
packages it as a program of its own that you run from the **command line**
(typing commands into a terminal). It needs nothing but `tree-sitter`: no LLM
libraries and no pipeline settings. Unlike IntelliJ it needs no licence and no
project that builds, and you can run it on many projects in one go.

The parser code is a copy of the one in folder 1. On all 59 projects stored in
folder 2 (all 50 downloaded Lindholmen projects, 30 of which went into the
measurements, plus the 9 from Zhang/Hebig), the two produce
character-for-character identical output in four configurations, and the
IntelliJ comparison gives the same lines when run through the new tool.

## Where things stand

- The pipeline supports Python and Java. For Java there is a parser of our
  own that never needs to build the project and scores as well on the research
  data as the best tool we tested.
- With the Zhang/Hebig data we have a dataset of Java diagrams that people
  abstracted by hand.
- The eight variants have not yet been run with a real LLM on Java projects
  and compared with the Zhang/Hebig diagrams. On Java there have only been
  **dry runs**, in which a stand-in with fixed answers takes the model's place.
  They show that all the parts work together but say nothing about quality.
  The real run is the next step.
- The Java parser can reproduce IntelliJ's class diagrams. On seven of the nine
  projects this has been checked completely against IntelliJ's pictures, for
  Orekit and Neuroph only in part.
- The parser is also available as a standalone tool in folder 3. It lives
  there as a copy, so any change to the parser has to be made in both folder 1
  and folder 3.
- There are four presentations on the project: on the Python pipeline with
  five methods (29 May 2026), on the shared driver with eight variants (7 July
  2026), on the comparison of the seven Java tools (21 September 2026) and on
  `javauml` compared with IntelliJ (3 November 2026). They are not part of this
  project yet and will be added later.

## Problems and how they were solved

| Problem | Phase | Solution |
| :--- | :--- | :--- |
| Local hardware can only run models up to about 24 billion parameters | 0 | switch to models accessed through an API; local models only as an option through Ollama |
| Models do not stick to the JSON format | 0 and 1 | a validator that repairs broken diagrams, one retry with a hint about what to fix, and tools instead of free-text answers |
| Context keeps growing with repeated tool calls | 1 and 2 | a shared budget, a reminder that depends on the remaining budget, one tool for classes and lines, code access only after a draft, an optional summary of the conversation |
| The five methods are hard to compare | 1 | one driver, eight variants with the same prompts and budgets |
| Test projects too small to support firm conclusions | 2 | search for larger datasets that come with diagrams |
| Hardly any UML datasets for Python | 3 | switch to Java |
| Existing Java tools fail on missing libraries, encodings or newer syntax | 3 | our own parser based on tree-sitter |
| Matching by short names hides mistakes with classes that share a name | 3 | our own check of name resolution; ambiguous cases are reported rather than guessed |
| Some reference diagrams do not match the code | 4 | case studies against the code. The scores show agreement with the diagram and say nothing about correctness |
| The parser does not see connections made through method calls | 5 | IntelliJ mode: read the inside of methods and work out the type of every intermediate result in a chain of calls |

## Open questions

- Runs with a real LLM on Java projects, compared with the Zhang/Hebig
  diagrams.
- Deciding how to measure the quality of a diagram: against a reference, by
  human judgement, or by having an LLM judge it. This question has been open
  since the first presentation in May 2026.

## Glossary

In alphabetical order. The other documents link here.

| Term | Meaning |
| :--- | :--- |
| Abstraction, abstract diagram | Leaving out what does not matter. An abstract class diagram shows only the central classes and relationships. |
| Agent | An LLM that calls tools on its own over several steps, reads the results and then decides what to do next. |
| API | An interface through which one program uses another. Here: access to a language model on the provider's servers over the internet, paid per token. |
| Association, aggregation, composition | Three kinds of "has a" relationship in UML. Association: knows about another object (a plain line). Aggregation: has other objects as parts that could also exist on their own (hollow diamond). Composition: the parts belong firmly to the whole (filled diamond). |
| Attribute, field | A piece of data an object keeps, such as a book's title. Java calls it a field. |
| Benchmark | A fixed comparison test. Every tool gets the same input and is scored the same way. |
| Branch, tag | A branch is a line of development in Git; a tag is a named fixed state, such as a version number. |
| Budget | A cap on how much text (in tokens) a run may use. |
| Build, compile, bytecode, compiler | Before Java code runs, the compiler translates it into bytecode. This is called compiling or building. It only works when every library the code uses is available. |
| Class, method | A class describes one kind of thing in a program. Methods are the actions it can carry out. |
| Class diagram | A drawing of a program's classes as boxes and their relationships as lines, following the UML rules. |
| Cluster | A group of closely connected files or classes. |
| Command line, terminal | A window where you type commands as text instead of clicking. |
| Commit | A saved snapshot of a project in the version control system Git. |
| Constant pool | A table inside the bytecode of every Java class that, among other things, lists all the classes it refers to. |
| Context window | The largest amount of text a language model can handle at once. |
| Corpus | The collection of projects that measurements are run on. |
| Declaration | The place in the code where a class, field or method is announced, with its name and type. The code that runs inside a method is not part of it. |
| Dependency | One class uses another somewhere in its code, for example as a return value or in a call. In UML a dashed line with an open arrowhead. |
| Docker, image, container, Compose | Docker delivers a ready-made environment as a package (an image). A running image is called a container. Compose is the part of Docker that describes how the container is started. You do not have to install anything separately. |
| Driver | The control program in folder 1 that leads the LLM through a run step by step. |
| Dry run | A test run in which a stand-in with fixed answers takes the place of the language model. It checks that the parts work together, not the quality. |
| Encoding | How letters are stored as bytes. Older files often store umlauts differently (ISO-8859-1, CP1252) from today's usual UTF-8. |
| Environment variable | A named value you set in the terminal that programs can read, such as the API key. |
| Extractor | In folder 2, the general term for tools that produce a class diagram from code. Our own parser is one of them. |
| F1, micro F1, macro F1 | A single score between 0 and 1 that combines precision and recall. Micro F1 adds up the hits of all projects; macro F1 averages the scores of the individual projects. See [how to tell whether a diagram is good](#how-to-tell-whether-a-diagram-is-good). |
| Fine-tuning | Extra training of a finished model on examples for a particular task. |
| Graph, node, edge | A graph is made of points (nodes) and connections (edges). In the class graph the classes are the nodes and the relationships are the edges. In a drawn diagram an edge appears as a line; the documents use both words for the same thing. |
| Ground truth, reference | The answer assumed to be correct, which results are compared against. |
| Harness | The program around a language model that gives it tasks and tools and checks its answers. |
| Import graph | Who uses whom, at the level of files or packages. |
| Inheritance | One class is a special kind of another (Java: `extends`). A novel is a book. In UML a solid line with a triangle. |
| IntelliJ IDEA | A widely used commercial programming environment that can draw class diagrams from code. |
| Interface, realization | An interface states what a class must be able to do without saying how. A class that fulfils it "realizes" the interface (Java: `implements`). In UML a dashed line with a triangle. |
| Java, Python | Two widely used programming languages. |
| JDK | The Java Development Kit, the basic toolkit for compiling and running Java, including the standard library (`List`, `String` and so on). |
| JSON | A text format for structured data that programs read and write easily. |
| JVM | The Java Virtual Machine, the program that runs Java bytecode. Starting it takes a moment every time. |
| Lambda | A short, nameless function written right where it is needed. |
| Library (in programming) | Ready-made third-party code a project uses, for example for windows or databases. |
| LLM | Large language model. A program trained on vast amounts of text that understands and produces text. |
| Model | Two meanings. In folder 1, the language model. In folder 2, the drawn class diagram in machine-readable form, as the research datasets call it. |
| Module (build module) | A subproject within a larger Java project that is built on its own. Two modules can contain classes with the same name. |
| Multiplicity | The "1", "0..1" or "0..*" at the end of a line, saying how many objects can be at that end. |
| Normalisation | Making data uniform before comparing it. Here mainly: association, aggregation and composition are merged into one kind of relationship, because people and tools use them very differently. |
| Open source | Software whose code is freely available. |
| Package | A folder that holds classes that belong together. |
| Parameters (of a model) | The adjustable numbers inside a language model. How many there are is a rough measure of the model's size. |
| Parser | A program that reads text in a fixed language (here, program code) and works out its structure. |
| Pipeline | A chain of processing steps in which each step works on the result of the one before. |
| PlantUML | A text format for diagrams and the program that turns it into pictures (PNG, SVG). |
| Precision, recall | Precision: the share of a tool's output that is correct. Recall: the share of the correct items that it found. |
| Prompt | The instruction or question you send to a language model. |
| Render | Turn a diagram written as text (PlantUML) into a picture. |
| Replication package | Data and material that a study's authors publish so others can check their results. |
| Repository, repo | The folder of a software project with all its files and its version history, often on GitHub. |
| Resolution (of a name) | Working out which class a name in the code refers to. If the code says `Kunde`, the parser checks package and imports to see whether `de.firma.model.Kunde` or another class of that name is meant. |
| Seed | A starting value for randomness. With many programs the same seed gives the same sequence of random numbers. |
| Source code | The program text that people write. |
| Static analysis | Examining code without running it. |
| Stereotype | An extra label on a class box in UML, such as `«interface»` or `«enum»`, that says what kind of class it is. |
| Test, test code | Small checking programs that automatically confirm the actual code does what it should. They belong to the project but not to what it does, which is why diagrams leave them out. |
| Token | A piece of a word that language models count text in, about four letters in English. Limits and prices are measured in tokens. |
| Tool | A command an LLM may call during a run, for example to read a file or change the diagram. |
| Transitive connection | A connection by way of a detour: A uses B, and through B, A reaches class C. |
| UML | Unified Modeling Language, a standardised visual language for software. |
| Validator | A checking program that finds and repairs broken diagrams. |
| Variant | One of the eight ways the LLM can work in the pipeline (start empty or cross out, what it sees at the start, whether it may read the code). |
