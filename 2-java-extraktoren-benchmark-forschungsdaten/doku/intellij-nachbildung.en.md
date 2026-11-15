[Deutsch](intellij-nachbildung.md) · **English**

# Reproducing IntelliJ's class diagrams

As of 23 October 2026.

IntelliJ IDEA is a widely used programming environment that can draw class
diagrams from Java code automatically. This file describes the rules IntelliJ
follows when it does this, how our extractor reproduces them, and how well that
works: for seven of nine projects the result is completely the same. The
[main README](../../README.en.md#glossary) explains the technical terms.

Commercial UML tools show connections that our extractor used to miss. The
extractor only read fields, `extends` and `implements`. IntelliJ also reads the
method bodies, and so it also shows connections that run through a third class.
The aim was for the extractor to produce the same diagram as IntelliJ for the
same classes.

The reference pictures are the nine diagrams that Zhang/Hebig produced with
IntelliJ by reverse engineering (`daten/zhang-hebig/models/reverse/`).

## Example of a transitive connection

Transitive means that the connection takes a detour, through a third class.

In RaiseMeUp, IntelliJ draws a dependency from `PetObserver` to `Job`.
`PetObserver` has no field of type `Job` and does not even import `Job`. But it
calls `RaiseMeUp.getCurrentJob().getImpactenergy()`. `getCurrentJob()` returns
a `Job`, and `getImpactenergy()` is declared in `Job`. So `PetObserver` depends
on `Job` by way of `RaiseMeUp`.

A second form is hidden in inheritance. In Orekit, `AdaptedStepInterpolator`
implements the interface `OrekitStepInterpolator`, which is not in the
diagram. Its supertype `PVCoordinatesProvider` is, and IntelliJ draws the
realization straight to it.

## Rules

The rules were derived from the nine pictures and checked against the source
code. The column "how it looks" describes what the line looks like in the
IntelliJ picture. A cast converts a value to another type; `instanceof` asks
"is this object of type X?". A self-loop is a line that leads from a class
back to itself.

| Edge | When IntelliJ draws it | How it looks |
| --- | --- | --- |
| Inheritance | `extends`. If the supertype is not in the diagram, the line goes to the nearest supertype that is | solid, triangle |
| Realization | `implements`, also skipping over types that are not shown | dashed, triangle |
| Field | a field (including `static`) whose type is a class in the diagram | solid, diamond at the owner, "1" at both ends, field name at the target |
| Field with many elements | an array or a JDK collection (`List`, `Set`, ...), or a class of the project's own that inherits from one. `Map` does not count | as above, "*" at the target |
| Inner class | a class declared inside another class in the diagram | red line with a circled plus |
| Dependency | any reference in the code: types in signatures, fields, local variables, casts, `instanceof`, class literals (`X.class`), static access through the class name, and method calls, including through call chains. A method call counts for the class that declares the method | dashed, open arrow |
| `«create»` | `new X(...)` anywhere in the class | dashed, with `«create»` |
| Self-loop | the class calls its own methods or uses its own type (cast, `instanceof`, return type) | dashed self-loop |

There are also three exceptions:

- Reading and writing fields does not create a dependency. `EvaluationReview`
  in PatrickFromTheMOOC only uses its own fields and has no self-loop.
- A plain dependency is left out if there is already an inheritance,
  realization or field relationship between the same classes in the same
  direction, or if an inner class uses its outer class.
- `«create»` is always drawn, even when there is already a field relationship.
  In ZooTypers, `SinglePlayer` has the field `model` and also creates it, and
  the picture shows both lines.

Which classes appear in the diagram was chosen by the authors in IntelliJ.
This selection is an input and is stored per project in
`daten/intellij/projekte.json`.

## Environment per project

IntelliJ only draws what it can resolve, and that depended on how each project
was opened. The JDK is Java's basic kit, with standard classes such as `List`.
The source root is the folder that IntelliJ treats as the start of the source
code. Two cases occur:

- No JDK set up: IntelliJ then does not know `List`, `LinkedList` and so on,
  and draws only a dependency for collection fields. You can see this in
  PatrickFromTheMOOC (five `LinkedList` fields without a line) and EAPLI
  (`List<Income>` without a line), while myblog and Neuroph show a "*" for
  `Set` and `List`.
- Source root set wrongly: IntelliJ then no longer finds classes from the same
  package, but it does find explicitly imported classes. In Artemis the three
  field relationships within one package are missing, while all relationships
  across package boundaries with `import` are drawn. In FreeDaysIntern all
  classes are in one package, and the picture shows nothing apart from one
  self-loop.

| Project | JDK | classes from the same package |
| --- | --- | --- |
| ZooTypers | yes | yes |
| RaiseMeUp | yes | yes |
| EAPLI_PL_2NB | no | yes |
| FreeDaysIntern | yes (cannot be determined, see below) | no |
| NeurophChanges | yes | yes |
| PatrickFromTheMOOC | no | yes |
| myblog | yes | yes |
| Orekit | yes | yes |
| Artemis | yes | no |

For FreeDaysIntern it is impossible to say whether a JDK was set up, because
nothing was resolved anyway.

## Comparison

The script `intellij_abgleich.py` builds the diagram for each project and
compares it with the edges read off the IntelliJ picture
(`daten/intellij/referenz/`). The results are in
`ergebnisse/messungen/intellij/`, and the diagrams, as PlantUML and PNG, are
next to the IntelliJ picture in `ergebnisse/diagramme-intellij/<Projekt>/`.

One thing to know before reading the table: after they had been checked in the
picture, the transcriptions were copied from the extractor's output. The
agreement is therefore the result of the visual check described below it. When
the extractor is changed later, the comparison shows whether anything shifts.

| Project | edges | transcription from the picture | agreement |
| --- | ---: | --- | --- |
| ZooTypers | 16 | complete | 16 of 16, none extra |
| RaiseMeUp | 36 | complete | 36 of 36, none extra |
| EAPLI_PL_2NB | 22 | complete | 22 of 22, none extra |
| FreeDaysIntern | 1 | complete | 1 of 1, none extra |
| PatrickFromTheMOOC | 18 | complete | 18 of 18, none extra |
| myblog | 12 | complete | 12 of 12, none extra |
| Artemis | 19 | complete | 19 of 19, none extra |
| Orekit | 35 | partial (28 edges) | all 28 checked edges match, 7 unchecked |
| NeurophChanges | 103 | partial (16 edges) | all 16 checked edges match, 87 unchecked |

How the transcriptions were made:

- For six projects, every line in the picture was traced from end to end and
  compared with the extractor's output.
- In RaiseMeUp many dashed lines overlap. There, the number and kind of
  incoming and outgoing lines were counted at each box and checked against the
  labels. All 16 boxes match, but not every single dashed line was traced from
  end to end.
- For Orekit, all inheritances, realizations, inner classes, field
  relationships, the `«create»` edges shown and the visible self-loops were
  checked.
- For Neuroph, the field relationships with a readable role name and two
  `«create»` edges were checked. The picture has around 100 lines, which
  overlap heavily.


## Open points

- Neuroph has only been checked against the picture to a small extent.
- In Orekit, several dashed lines in the picture run on top of each other to
  `AbstractPropagator`. The extractor predicts four dependencies from inner
  classes to it, which cannot be told apart in the picture. It also predicts a
  self-loop on `AbstractPropagator` that cannot be seen in the picture. It may
  be hidden among the overlapping lines.
- The two environment switches were inferred from the pictures. A wrong source
  root in IntelliJ would explain every missing line in Artemis, but this has not
  been proven directly.
- Overloaded methods are told apart only by the number of arguments. Lambdas
  without a type, `var` with a type that is hard to work out, and methods from
  libraries other than the common JDK collections end a call chain.

## Usage

In the pipeline (folder 1):

```bash
python -m src /pfad/zum/repo --language java --java-relations intellij \
  --java-diagram-classes klassen.txt --java-member-profile full
```

Here `/pfad/zum/repo` means "/path/to/repo". `klassen.txt` (a list of classes)
holds one fully qualified class name per line. Without this file, all classes of
the project go into the diagram. `--java-ide-no-jdk` and
`--java-ide-no-same-package` reproduce the two environment cases. The result is
in `javagraph.json` and `javagraph.puml` as usual.

To repeat the comparison (from folder 2):

```bash
PYTHONPATH=../1-llm-pipeline-abstrakte-klassendiagramme \
  .venv/bin/python skripte/intellij_abgleich.py --render
```
