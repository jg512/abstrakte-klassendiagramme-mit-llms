[Deutsch](java-parser.md) · **English**

# The Java parser

As of 23 October 2026.

A parser is a program that reads code and works out its structure. This
project's Java parser reads all the Java files of a software project and
writes down which classes there are, what they contain and how they are
connected. The result is the full class graph, from which the LLM later picks
the important parts. Basic terms such as class, field, method, inheritance and
compiling are explained in the [main README](../../README.en.md#glossary).

This file describes how the parser turns a repository into a class graph,
which program file handles which step, and where the limits are. It is meant
for anyone who wants to understand, check or change the parser. If you would
rather read about a concrete case, skip to the
[example with two classes](#example-two-classes-through-every-stage) and come
back when you need to.

The parser reads source code only. The project does not have to be built or
compiled. This is exactly where the bytecode tools in the comparison in
[folder 2](../../2-java-extraktoren-benchmark-forschungsdaten/README.en.md)
failed, because only three of the nine projects could be compiled.

## Java terms used here

| Term | Meaning, with an example |
| :--- | :--- |
| Type | The umbrella term for classes, interfaces, enums, records and annotation types. `String` (text) and `int` (a whole number) are types too. |
| Interface | Describes what a class must be able to do. `Comparable`, for example, means "can be compared with others". |
| Enum | A type with a fixed list of values, such as `Wochentag` (weekday) with `MONTAG` to `SONNTAG` (Monday to Sunday). |
| Record | A short way of writing a class that only holds data (since Java 16). |
| Annotation | An extra note marked with `@`, such as `@OneToMany` ("one to many") for databases. |
| Package, `package` | A folder for classes that belong together. A class's full name includes the package: `de.uni.bib.model.Buch`. This is called the fully qualified name. |
| Import, wildcard import | `import de.uni.bib.model.Buch;` lets you write just `Buch` (book) in a file. `import de.uni.bib.model.*;` (a wildcard import) brings in all classes of a package without naming them. |
| Supertype | A class that is inherited from (`extends`), or an interface that is fulfilled (`implements`). |
| Nested type, inner class | A class written inside another class, such as `Bestellung.Position` (an order and one of its line items). |
| Generics, type parameter | A stand-in for a type. `List<Buch>` is a list of books. In `class Box<T>`, `T` is a stand-in, not a real class. |
| Collection | A container for many objects, such as `List`, `Set` or `Map` (which maps keys to values). |
| Method body, signature | The signature is a method's header line, with its name, parameters and return type. The body is the code that follows in curly braces. |
| Constructor, `new` | `new Buch("Faust")` creates a new object of the class `Buch`. The constructor is the code that runs when that happens. |
| Syntax tree | The broken-down structure of a file as a tree: the file contains classes, the classes contain fields and methods, and so on. |
| Maven, Gradle | Two widely used tools for building Java projects. They also set which folders the code lives in (usually `src/main/java`). |
| Classpath | The list of places where Java looks for libraries. |
| JAR | A packed file of ready-compiled Java code, usually a library. |

## Overview

```
Repo
  -> src/io/filters.py           which .java files are read
  -> src/parsing/java/ts_pass.py syntax tree per file, classes with fields,
                                 methods and supertypes (ClassInfo)
  -> src/parsing/java/resolution.py
                                 map type names to classes in the repo
  -> one of two graphs:
       graph_builder.py          literal graph (default)
       intellij.py               class diagram as in IntelliJ
     optional javac_solver.py    extra resolution through the JDK compiler
  -> src/schema/                 check the graph JSON, generate PlantUML
  -> src/runs/output_writer.py   javagraph.json, javagraph.puml, diagnostics
```

Each line is a step, and on the right is the program file that carries it out.
The steps are put together in `src/parsing/code_graph.py`. The result is a
`CodeGraph`, which the LLM variants then work with.

Names such as `collect_source_files` or `ClassInfo` in the sections below are
the names of the functions and data structures in the code. You do not need to
know them to follow the process, but they help when you look things up in the
code.

## 1. Choosing the files: `src/io/filters.py`

`collect_source_files` collects all `*.java` files and applies the exclusions
from `configs/default.yaml`. Test folders, build output such as `target/`,
`bin/` and `out/`, and files such as `*Test.java` are left out.

For Java, `_select_java_source_sets` comes on top of that. If you search
recursively for `*.java`, many projects turn up old or generated copies of the
same classes alongside `src/main/java`. With `source_sets: auto` (the default),
the main folders following the Maven/Gradle convention are therefore preferred.
The function reads other source folders from `pom.xml` or `build.gradle`
(`_configured_java_roots`). Generated files stay out unless
`include_generated` is set. With `source_sets: all`, everything that is left
after the exclusions is read. You need this for old projects without the usual
structure.

`src/parsing/languages.py` only records the details for each language: the
file extension `.java` and the base name `javagraph` for the output files.

## 2. Reading the syntax tree: `src/parsing/java/ts_pass.py`

Parsing is done with tree-sitter, a widely used library for breaking code down,
and its grammar (the language rules) for Java, `tree-sitter-java`. Even when
there are syntax errors (typos in the code), tree-sitter still returns a tree
from which the usable parts can be read. Files with errors are reported as
`partial-parse` and analysed anyway.

`read_source` reads each file as bytes and tries the encodings UTF-8, CP1252
and Latin-1 in that order. The encoding decides how letters such as "ä" are
stored as bytes. Old Java code is often not saved as UTF-8. Tools that
insist on UTF-8 usually lose such files without saying anything.

`_parse_file` first takes the `package` line and all imports from each file.
Static imports are stored like normal imports. Then `visit` walks through the
tree and creates an entry for every class, interface, enum, record and
annotation type, nested types included. A stack of the surrounding names gives
the local name, for example `Bestellung.Position`.

`_build_record` collects for each type:

- its kind (`interface`, `enum`, `record`, `annotation`, `abstract` or a normal
  class),
- `extends` and `implements`, with the name as it is written in the code. For
  `interface A extends B`, `B` goes under `extends`, because in UML this is
  inheritance and not realization,
- fields, through `_collect_field`; record components count as fields too,
- methods as signatures, depending on the level of detail (`member_profile`),
- the types in method signatures (`_method_type_refs`), which are needed for
  the optional method dependencies,
- the class's type parameters, so that a `T` is not later looked up as a class.

`_split_type` breaks a type down into the base type, the type arguments and
whether it holds many elements. For `List<Kunde>` (a list of customers), the
element `Kunde` is what matters, not `List`. Arrays are handled the same way.
Qualified names such as `java.util.Comparator` are kept in full, so that they
are not confused with a class of the same name in the project.

`_collect_field` creates a `FieldRef` for each field and estimates the kind of
relationship:

| Case | Relationship | Multiplicity at the target |
| :--- | :--- | :--- |
| plain field | association | none |
| array or collection | aggregation | `0..*` |
| `Optional<X>` | association | `0..1` |
| `final` and created with `new` in the field itself | composition | `1` |
| `@OneToMany`, `@ManyToMany` | aggregation | `0..*` |
| `@OneToOne`, `@ManyToOne` | association | `0..1` |
| `@Embedded`, `@ElementCollection` | composition | `1` or `0..*` |

The "multiplicity" column says how many objects can hang off the other end:
`1` exactly one, `0..1` none or one, `0..*` any number.

Private fields (visible only inside the class) count too, because that is the
usual shape of a relationship in Java: the field is private, and the outside
world only gets a method that reads it (the getter, such as `getTitel()`, "get
title"). Leaving private fields out would lose almost every relationship.

`analyze_java` calls all of this for the chosen files and then tidies up:

- If the same fully qualified name appears twice in one module, the file with
  the shortest path is kept. The conflict is reported as
  `duplicate-declaration`.
- If the same name appears in different Maven/Gradle modules, the classes get
  IDs with a module prefix (`modules.<modul>...`).
- The package prefix shared by all classes is cut off. `de.firma.app.model.Kunde`
  becomes `model.Kunde`. This gives Java IDs the same form as the repo-relative
  Python modules, and the first part of the package can serve as a group for
  clustering. The original name is kept in `source_qualified_name`.

The result is a list of `ClassInfo` (defined in `src/parsing/models.py`) plus a
list of diagnostics.

## 3. Resolving type names: `src/parsing/java/resolution.py`

The code usually just says `Kunde`, but what is needed is the class that name
refers to. `JavaTypeResolver.resolve(name, source)` searches in this order,
which roughly follows the compiler's rule:

1. The class's type parameters. A `T` is not a class and gives nothing.
2. The class itself and the types around it, from the inside out, including
   nested types inherited from a superclass.
3. Explicit imports. An import applies even when it points to a library class
   and the project has a class with the same short name.
4. The same package.
5. Fully qualified names.
6. Wildcard imports and `java.lang`.

If there are several candidates, the class's own build module is searched
first. If it is still ambiguous, the relationship is left out and reported as
`ambiguous-type`. A wrong arrow would be worse than a missing one. Results are
cached for each pair of class and name, so the same question is not worked out
more than once.

For types outside the project, `external_name` returns the name from the
matching import, so `javax.swing.JFrame` instead of just `JFrame`.

The resolver is no substitute for a compiler. It knows nothing about JARs or
local variables (variables that only exist inside a method). The IntelliJ
mode, which also analyses method bodies, therefore has its own way of working
out types (section 5).

## 4. The literal graph: `src/parsing/java/graph_builder.py`

`build_java_graph` is the default and the counterpart of pyreverse for Python.
"Literal" means that the graph shows exactly what the declarations say,
without inferring anything. The `catalog` variants get this graph as context,
and the `prune` variants start from it. It contains everything that can be
read from the declarations. Abstraction only happens later, through the LLM.

- Every declared class becomes a node with its package, stereotype, attributes,
  methods and evidence. The stereotype comes from `_STEREOTYPE_MAP`; a record,
  for example, becomes `dataclass`.
- `extends` gives an inheritance, `implements` a realization.
- Supertypes outside the project are kept as nodes in the package `external`.
  Inheriting from `JFrame` says a lot about a class's role. Fields with external
  types such as `String` or `Timer`, on the other hand, do not give an edge;
  otherwise the architecture would get lost among library nodes.
- Every `FieldRef` whose type resolves to a project class becomes an edge, with
  the kind and multiplicity from step 2 and the field name as its role. Two
  fields pointing to the same target (`primary` and `history`) stay two edges.
- With `include_method_dependencies`, dependencies from method signatures are
  added. This is off by default.
- Edges from javac mode are merged in. If the relationship already exists from
  the source code, it only gets the extra evidence. The kind of relationship
  from the source code stays, because javac knows nothing about ownership in
  the UML sense.

Every edge carries `EdgeEvidence` with the field or method, the type as
written, the file and the line. This means every arrow in the diagram can be
traced back to its line of code.

## 5. IntelliJ mode: `src/parsing/java/intellij.py`

With `relation_style: intellij` (or `--java-relations intellij`), the parser
produces the class diagram that IntelliJ IDEA draws for the same classes,
instead of the literal graph. The main difference is that IntelliJ also reads
the method bodies, and so finds connections that go through a third class. In
RaiseMeUp, for example, `PetObserver` calls
`RaiseMeUp.getCurrentJob().getImpactenergy()`. `getImpactenergy` is declared in
`Job`, so `PetObserver` depends on `Job`, even though `Job` appears nowhere in
the file.

`build_intellij_graph` works in two passes.

The first pass builds a symbol table, a lookup of all classes with their fields
and methods and their types. `analyze_java` supplies the classes;
`_collect_bodies` parses the files a second time and records for each class
the syntax node, the fields and methods with their type nodes, parameters and
type parameters, and the static imports. `_Model` bundles all this and
provides:

- `resolve_name` and `type_of_node`: type names become a `JType` of kind
  `project`, `jdk` or `external`, with type arguments and array dimensions,
- `lineage`: the class and all its supertypes in the project,
- `find_method`, `find_field`: look up members in superclasses too. Overloaded
  methods are told apart by the number of arguments,
- `member_type`: the return type or field type, with simple substitution of
  type parameters (`Box<Kunde>.get()` gives `Kunde`),
- `jdk_member_type`: the return types of the few JDK methods needed for chains
  of calls, such as `get` on a list or `values()` on a map,
- `iterable_element`: the element type of arrays, JDK collections and project
  classes that inherit from a JDK collection.

In the second pass, `_BodyScanner` goes through the body of every class in the
diagram. It keeps track of local variables, parameters, and variables from
`for`, `catch`, `try` with resources and `instanceof` patterns, along with the
scope in which each one is valid. `type_of` works out the type of an
expression step by step. For `a.b().c()`, it first looks up the type of `a`,
then the method `b` in that class and its return type, then `c`. Every
reference along the way is recorded with `note`:

- Types in signatures, fields, local variables, casts, `instanceof` and class
  literals, and static access through the class name, count for that type.
- A method call counts for the class that declares the method. If an inherited
  method is called, that is the superclass.
- `new X()` is recorded as `create`.
- `this(...)` and `super(...)` in a constructor count for the class itself or
  for the superclass.
- Field access does not count.
- Nested classes are skipped; they get a pass of their own.

Then the edges are put together:

1. Inheritance and realization. If a supertype is not in the diagram, the
   parser looks further up, one level at a time, for the nearest supertype
   that is (a so-called breadth-first search).
2. Fields (`_field_relation`). A field whose type is a class in the diagram
   becomes a composition with "1" at both ends. For arrays, JDK collections and
   project classes that inherit from a JDK collection, the target end gets "*".
   Maps give nothing.
3. Nesting. An inner class gets a `nesting` edge from its outer class.
4. Dependencies from the second pass. A plain dependency is dropped if there
   is already an inheritance, realization or field relationship in the same
   direction, or if an inner class uses its outer class. A dependency marked
   `«create»` always stays.

Two further inputs shape the result:

- `diagram`: the fully qualified names of the classes that should be in the
  diagram. In IntelliJ a person picks them, which is why they are passed in.
  Without a selection, all classes go in. All files of the project are still
  read for the chains of calls.
- `IdeEnvironment`: how the project was opened in IntelliJ. With `jdk=False`,
  IntelliJ does not know `List` and the like, and collection fields get no
  line. With `same_package=False`, IntelliJ only finds classes from the same
  package if they are explicitly imported. Both cases occur in the Zhang/Hebig
  pictures.

In IntelliJ mode, external classes only get IDs of the form
`external.<Kurzname>` (short name), because with wildcard imports the full name
cannot be worked out from the source code alone. The javac extra resolution is
not mixed in in this mode.

How the rules were derived from the nine IntelliJ pictures and checked against
them is described in folder 2 under
[`doku/intellij-nachbildung.en.md`](../../2-java-extraktoren-benchmark-forschungsdaten/doku/intellij-nachbildung.en.md).

## 6. Extra resolution through javac: `src/parsing/java/javac_solver.py`

With `symbol_solver: javac`, the Java compiler `javac` from the JDK is asked as
well. It knows the language rules completely, but in return it needs the
libraries the code uses. The module writes a small Java helper program into a
temporary folder, compiles it and runs it over the source files of each build
module. The program uses the public compiler API (`javax.tools`,
`com.sun.source`), resolves field types and supertypes and prints one line for
each finding. Missing libraries only lead to a diagnostic
(`javac-partial-resolution`). Whatever javac could still match to a project
class comes back as an edge with `resolver="javac"`. JARs can be passed in
through `classpath`. Without an installed JDK, there is the diagnostic
`javac-unavailable` and no other change.

## 7. Package dependencies: `src/parsing/java/import_graph.py`

For clustering and the package overview, the pipeline needs dependencies
between packages. For Python they come from the import lines. For Java,
imports are of little use here, because classes in the same package need no
import at all and wildcard imports do not name a class. `build_import_graphs`
therefore builds the graph from resolved supertypes and field types, that is,
from the same information as the class graph. There are two levels: package to
package, and top-level package to top-level package.

## 8. Putting it together: `src/parsing/code_graph.py`

`_build_java` calls, in order, `analyze_java`, `build_import_graphs`,
optionally `resolve_with_javac`, and then, depending on `relation_style`,
`build_intellij_graph` or `build_java_graph`. A simple inheritance table is
added. Everything ends up in a `CodeGraph`.

The options are in `JavaConfig` (`src/config/models.py`), are checked in
`src/config/loader.py` and can be set through `src/cli.py`:

| Option | Command line | Meaning |
| :--- | :--- | :--- |
| `source_sets` | `--java-source-sets` | `auto` or `all`, see section 1 |
| `include_generated` | `--java-include-generated` | also read generated source files |
| `member_profile` | `--java-member-profile` | `structure`, `summary`, `public-api` or `full` |
| `include_external_supertypes` | `--no-java-external-supertypes` | keep external supertypes as nodes (default), or leave them out with the flag |
| `include_method_dependencies` | `--java-method-dependencies` | dependencies from method signatures |
| `symbol_solver`, `classpath` | `--java-symbol-solver`, `--java-classpath` | javac extra resolution |
| `relation_style` | `--java-relations` | `literal` or `intellij` |
| `diagram_classes` | `--java-diagram-classes FILE` | class selection for IntelliJ mode |
| `ide_jdk` | `--java-ide-no-jdk` | reproduce IntelliJ without a JDK |
| `ide_same_package` | `--java-ide-no-same-package` | reproduce IntelliJ with a wrong source root |

`src/parsing/cache.py` stores the finished `CodeGraph` (a cache), so that a
second run on the same project does not have to read everything again. The
key by which a stored result is recognised contains the path, size and
modification time of every file, the Java options and a version number of the
parser. If the parser changes in a way that makes old results wrong, the
version number is raised.

## 9. Graph model and output

`src/schema/graph.py` defines the building blocks of the graph:
`AbstractGraph` (the whole graph), `Node`, `Edge`, `EdgeEvidence` (the evidence
for an edge) and `Diagnostic` (a message). `src/schema/validator.py` checks
edge kinds and stereotypes and, where edges are duplicated, keeps the stronger
one. `src/schema/plantuml.py` generates PlantUML from it:

| Edge kind | PlantUML |
| :--- | :--- |
| `inheritance` | `--\|>` |
| `realization` | `..\|>` |
| `composition` | `*--` |
| `aggregation` | `o--` |
| `association` | `-->` |
| `dependency` | `..>` |
| `nesting` | `+--` |

Labels such as `«create»` are written as `<<create>>`, because otherwise
PlantUML swallows the guillemets.

`write_static_graph_outputs` in `src/runs/output_writer.py` writes
`javagraph.json`, `javagraph.puml` and, if there are diagnostics,
`javagraph.diagnostics.json` for each repo.

## 10. Tests

| File | Checks |
| :--- | :--- |
| `tests/test_java_parsing.py` | syntax tree, fields and multiplicities, encodings, prefix, modules, literal graph, javac mode |
| `tests/test_java_resolution.py` | resolution order, imports, nested and inherited types, ambiguity |
| `tests/test_java_intellij.py` | IntelliJ mode: chains of calls, self-loops, fields with "1" and "*", environments, PlantUML |

The parser was measured against real diagrams in
[folder 2](../../2-java-extraktoren-benchmark-forschungsdaten/README.en.md).

## Example: two classes through every stage

A small program with two classes, `Bibliothek` (library) and `Buch` (book), in
two packages. The outputs below come from a real run of the parser and have
only been shortened. The German identifiers are kept as they appear in that
run: `buecher` means books, `hinzufuegen` add, `ersterTitel` first title and
`titel` title.

```java
// src/main/java/de/uni/bib/Bibliothek.java
package de.uni.bib;

import de.uni.bib.model.Buch;
import java.util.ArrayList;
import java.util.List;

public class Bibliothek {
    private final List<Buch> buecher = new ArrayList<>();                     // line 8

    public void hinzufuegen(String titel) { buecher.add(new Buch(titel)); }    // line 11
    public String ersterTitel() { return buecher.get(0).getTitel(); }          // line 15
}

// src/main/java/de/uni/bib/model/Buch.java
package de.uni.bib.model;

public class Buch implements Comparable<Buch> {
    private String titel;
    public Buch(String titel) { this.titel = titel; }
    public String getTitel() { return titel; }
    public int compareTo(Buch other) { return titel.compareTo(other.getTitel()); }
}
```

The project also contains a test under `src/test/java/` and an old copy of
`Buch.java` under `target/classes/`.

### Choosing the files

```
found:    src/main/java/de/uni/bib/Bibliothek.java
found:    src/main/java/de/uni/bib/model/Buch.java
found:    src/test/java/BibliothekTest.java
found:    target/classes/de/uni/bib/model/Buch.java
selected: src/main/java/de/uni/bib/Bibliothek.java
selected: src/main/java/de/uni/bib/model/Buch.java
```

`test` and `target` are in the exclusions. Without this rule there would be two
`Buch` classes, and the outdated copy might be the one that gets read.

### Syntax tree and ClassInfo

For `Buch.java`, tree-sitter returns this tree (shortened):

```
program
  package_declaration      de.uni.bib.model
  class_declaration
    identifier             Buch
    super_interfaces       Comparable<Buch>
    class_body
      field_declaration        titel
      constructor_declaration
      method_declaration       getTitel
      method_declaration       compareTo
```

This gives two `ClassInfo` entries:

| | Bibliothek | Buch |
| :--- | :--- | :--- |
| `source_qualified_name` | `de.uni.bib.Bibliothek` | `de.uni.bib.model.Buch` |
| `qualified_name` (ID) | `Bibliothek` | `model.Buch` |
| `module` | empty | `model` |
| `interfaces` | | `Comparable` |
| `imports` | `de.uni.bib.model.Buch`, `java.util.ArrayList`, `java.util.List` | |
| `attributes` | `buecher: List<Buch>` | `titel: String` |
| `methods` | `hinzufuegen(String)`, `ersterTitel()` | `compareTo(Buch)`, `getTitel()` |

Both packages start with `de.uni.bib`. This prefix is cut off, so `Bibliothek`
no longer has a package and `Buch` is in `model`.

For the field `buecher`, `_split_type` breaks the type `List<Buch>` down into
the container `List` and the element `Buch`. From that, `_collect_field`
creates:

```
FieldRef(field_name='buecher', type_name='Buch', many=True,
         declared_type='List<Buch>', line=8,
         relation_type='aggregation', target_card='0..*')
```

At this stage the method bodies are not read, only the signatures.

### Resolution

```
in Bibliothek: 'Buch'       -> model.Buch   (explicit import)
in Bibliothek: 'List'       -> not a project class, external java.util.List
in Buch:       'Comparable' -> not a project class, external Comparable (java.lang)
in Buch:       'Bibliothek' -> nothing (different package, not imported)
```

### Literal graph

```
Node  Bibliothek
Node  model.Buch
Node  external.Comparable
Edge  aggregation  Bibliothek -> model.Buch  buecher 0..*
      evidence: field buecher, List<Buch>, Bibliothek.java line 8
Edge  realization  model.Buch -> external.Comparable
      evidence: implements Comparable, Buch.java line 3
```

`Comparable` stays as an external node because it is a supertype. The field
`titel` of type `String` gives no edge. The package graph from
`import_graph.py` is `{'': ['model']}`: the top-level package depends on
`model`.

```
Bibliothek o-- "0..*" Buch : buecher
Buch ..|> Comparable
```

This mode does not see that `Bibliothek` creates a `Buch` and calls
`getTitel()`.

### IntelliJ mode

The first pass builds the symbol table:

```
Bibliothek  fields {buecher: List<Buch>}   methods {hinzufuegen: 1 parameter, ersterTitel: 0}
model.Buch  fields {titel: String}         methods {<init>: 1, getTitel: 0, compareTo: 1}
```

In the second pass, the interesting spot is `buecher.get(0).getTitel()`.
`type_of` goes through it step by step:

1. `buecher` is not a local variable, so it is a field of type `List<Buch>`.
2. `.get(0)` on a `List` gives the element `Buch`, through `jdk_member_type`.
3. `.getTitel()` is found in `Buch` with `find_method`. The call therefore
   counts as a reference to `Buch`.

All references that `_BodyScanner` records:

```
Bibliothek -> Buch        create, use  (field type line 8, new Buch line 11, getTitel line 15)
Bibliothek -> ArrayList   create
Bibliothek -> List, String use
Buch -> Buch              use          (Comparable<Buch>, parameter Buch other, other.getTitel())
Buch -> Comparable, String use
```

Without a class selection, only the two project classes are in the diagram, so
`List`, `String` and `Comparable` drop out. The rules from section 5 apply to
the rest:

| Rule | Result |
| :--- | :--- |
| field `List<Buch>`, a JDK collection | `Bibliothek "1" *-- "*" Buch : buecher` |
| `new Buch(...)` | `Bibliothek ..> Buch : <<create>>`, stays despite the field edge |
| plain dependency from Bibliothek to Buch | dropped, because the field edge already exists |
| `Buch` uses its own type and calls one of its own methods | self-loop `Buch ..> Buch` |
| `Comparable` | no realization, because `Comparable` is not in the diagram |

```
Bibliothek "1" *-- "*" Buch : buecher
Bibliothek ..> Buch : <<create>>
Buch ..> Buch
```

If `java.lang.Comparable` is in the class selection, the realization is added
as well. In real projects such chains often run through three classes, such as
`RaiseMeUp.getCurrentJob().getImpactenergy()` in RaiseMeUp.

### Output

`to_plantuml` generates the PlantUML texts above, and
`write_static_graph_outputs` writes `javagraph.json` and `javagraph.puml`.
There were no diagnostics in this example, so there is no
`javagraph.diagnostics.json` either.

## Limits

- Without a build there is no information from libraries. A return type from a
  library ends a chain of calls, apart from the common JDK collections.
- Overloaded methods are only told apart by the number of arguments.
- Lambdas without a type and `var` with a type that is hard to work out also
  end a chain of calls.
- Ambiguous types are left out. When in doubt this costs a correct edge, but it
  avoids wrong ones.
- The kind of a field relationship in the literal graph (association,
  aggregation, composition) is an estimate based on the type, `final`,
  initialisation and JPA annotations. Whether a class really owns an object is
  not written in the code in that form.
