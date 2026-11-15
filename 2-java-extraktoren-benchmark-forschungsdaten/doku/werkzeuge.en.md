[Deutsch](werkzeuge.md) · **English**

# Tools

Folder 2 compares seven tools that produce a class diagram from Java code. The
built tools are in `werkzeuge/` (64 MB in total, only in the full project
folder). This file describes where they come from, which version was used and
how to build them again. You only need this if you want to repeat the
measurement yourself. The [main README](../../README.en.md#glossary) explains
the technical terms.

Measurement environment: OpenJDK 25.0.4.1 (2026-08-18), Apache Maven 3.9.12,
Python 3.13.15, and PlantUML with its built-in layout `smetana`, which works
without the add-on program Graphviz.

## The seven tools

| Tool | reads | source | note |
| --- | --- | --- | --- |
| our extractor | source code | folder 1, via `PYTHONPATH` | tree-sitter-java |
| javalang 0.13.0 + adapter | source code | PyPI, adapter in `benchmark.py` | a plain parser; a small add-on program of our own (the adapter), about 40 lines long, turns its output into a class graph |
| java2plantuml (mirajp1) | source code | github.com/mirajp1/java2plantuml, commit `cadd0f0` | JavaParser 3.4.0 |
| jdeps | bytecode | part of the JDK | edges without a type, no inheritance |
| plantuml-generator 2.3.0 | bytecode | Maven Central `de.elnarion.util` | classgraph and javassist |
| Java2PlantUML (juanmf) | bytecode | github.com/juanmf/Java2PlantUML | despite its name it works with reflection (it loads the compiled classes and asks them how they are built) |
| genuml 0.6.1 | bytecode | PyPI | wrapper around `javap` |

## Checksums of the JARs

A JAR is a packed file of compiled Java code. The checksum (SHA-256, shortened
here) is its fingerprint. If you download the file again and the checksum
matches, you have the same file.

| Tool | file | size | SHA-256 (shortened) |
| --- | --- | ---: | --- |
| plantuml (for rendering the PNGs) | `plantuml-1.2025.4.jar` | 22.6 MB | `1e7964277a6c3907…` |
| plantuml-generator-util 2.3.0 | `plantuml-generator-util-2.3.0.jar` | 0.2 MB | `37acc5ef41374758…` |
| Java2PlantUML (juanmf) 1.0.1 | `java2PlantUML-maven-plugin-1.0.1.jar` | 0.1 MB | `2976c50b78b9dff6…` |
| javaparser-core 3.4.0 (for mirajp1) | `javaparser-core-3.4.0.jar` | 0.9 MB | `d75382e0e660d08d…` |

## Building again

```bash
cd werkzeuge

# plantuml-generator with its dependencies (classgraph, javassist)
mvn -f pug/pom.xml dependency:copy-dependencies -DoutputDirectory=lib
javac -cp "$(ls pug/lib/*.jar | tr '\n' ':')" -d pug/driver pug/Run.java

# Java2PlantUML (juanmf); on JDK 25 it only builds after raising source/target
git clone --depth 1 https://github.com/juanmf/Java2PlantUML.git juanmf
sed -i 's|<source>1.7</source>|<source>8</source>|; s|<target>1.7</target>|<target>8</target>|' juanmf/pom.xml
mvn -f juanmf/pom.xml -DskipTests package
mvn -f juanmf/pom.xml dependency:build-classpath -Dmdep.outputFile=cp.txt
javac -cp "juanmf/target/java2PlantUML-maven-plugin-1.0.1.jar:$(cat juanmf/cp.txt)" -d juanmf/driver juanmf/JuanmfRun.java

# genuml in its own virtual environment, because it needs click<8.2
python3 -m venv /tmp/genumlvenv
/tmp/genumlvenv/bin/pip install genuml 'click<8.2'

# extra libraries for the projects (41 JARs) and PlantUML for rendering
mvn -f extra/pom.xml dependency:copy-dependencies -DoutputDirectory=jars
mvn dependency:get -Dartifact=net.sourceforge.plantuml:plantuml:1.2025.4
```

## Known problems

Java2PlantUML (juanmf) cannot be built with a current JDK without a change,
because its pom sets `source` and `target` to 1.7, which javac 25 no longer
supports. On top of that, the `Main` that comes with it finds no classes from
Java 9 onwards: the library `reflections` 0.9.10 expects a `URLClassLoader`,
which has not been the default class loader since Java 9. With our own driver
`JuanmfRun.java`, which passes in a `URLClassLoader`, the tool works.

Do not install genuml into the benchmark's virtual environment. It needs
`click<8.2` and would change the versions pinned in
`werkzeuge/requirements.lock.txt`.

## Extra libraries for the projects

These 41 libraries were added so that as many of the nine projects as possible
could be compiled (Android, JPA, Hibernate, Hipparchus, Spring, slf4j and their
dependencies). Even so, this only worked for three projects; the reasons are in
[`ergebnisse-zhang-hebig.en.md`](ergebnisse-zhang-hebig.en.md):

`FastInfoset-1.2.15.jar`, `activation-1.1.1.jar`, `android-4.1.1.4.jar`,
`antlr-2.7.7.jar`, `byte-buddy-1.12.18.jar`, `classmate-1.5.1.jar`,
`commons-codec-1.3.jar`, `commons-logging-1.1.1.jar`,
`hibernate-commons-annotations-5.1.2.Final.jar`,
`hibernate-core-5.6.15.Final.jar`, `hipparchus-core-3.0.jar`,
`hipparchus-filtering-3.0.jar`, `hipparchus-fitting-3.0.jar`,
`hipparchus-geometry-3.0.jar`, `hipparchus-ode-3.0.jar`,
`hipparchus-optim-3.0.jar`, `hipparchus-stat-3.0.jar`, `httpclient-4.0.1.jar`,
`httpcore-4.0.1.jar`, `istack-commons-runtime-3.0.7.jar`,
`jandex-2.4.2.Final.jar`, `javax.activation-api-1.2.0.jar`,
`javax.persistence-api-2.2.jar`, `jaxb-api-2.3.1.jar`, `jaxb-runtime-2.3.1.jar`,
`jboss-logging-3.4.3.Final.jar`,
`jboss-transaction-api_1.2_spec-1.1.1.Final.jar`, `json-20080701.jar`,
`opengl-api-gl1.1-android-2.1_r1.jar`, `slf4j-api-2.0.16.jar`,
`spring-aop-5.3.39.jar`, `spring-beans-5.3.39.jar`, `spring-context-5.3.39.jar`,
`spring-core-5.3.39.jar`, `spring-expression-5.3.39.jar`,
`spring-jcl-5.3.39.jar`, `spring-tx-5.3.39.jar`, `stax-ex-1.8.jar`,
`txw2-2.3.1.jar`, `xmlParserAPIs-2.6.2.jar`, `xpp3-1.1.4c.jar`
