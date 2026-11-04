# Werkzeuge

Die gebauten Werkzeuge liegen in `werkzeuge/` (zusammen 64 MB). Hier ist
beschrieben, woher sie stammen und wie sie sich neu bauen lassen.

Messumgebung: OpenJDK 25.0.4.1 (2026-08-18), Apache Maven 3.9.12, Python 3.13.15,
PlantUML mit dem Layout `smetana` (ohne Graphviz).

## Die sieben Werkzeuge

| Werkzeug | liest | Quelle | Anmerkung |
| --- | --- | --- | --- |
| eigener Extraktor | Quelltext | Ordner 1, über `PYTHONPATH` | tree-sitter-java |
| javalang 0.13.0 + Adapter | Quelltext | PyPI, Adapter in `benchmark.py` | Parser mit einem Adapter von etwa 40 Zeilen |
| java2plantuml (mirajp1) | Quelltext | github.com/mirajp1/java2plantuml, Commit `cadd0f0` | JavaParser 3.4.0 |
| jdeps | Bytecode | Teil des JDK | Kanten ohne Typ, keine Vererbung |
| plantuml-generator 2.3.0 | Bytecode | Maven Central `de.elnarion.util` | classgraph und javassist |
| Java2PlantUML (juanmf) | Bytecode | github.com/juanmf/Java2PlantUML | arbeitet trotz des Namens mit Reflection |
| genuml 0.6.1 | Bytecode | PyPI | Wrapper um `javap` |

## Prüfsummen der JARs

| Werkzeug | Datei | Größe | SHA-256 (gekürzt) |
| --- | --- | ---: | --- |
| plantuml (zum Rendern der PNGs) | `plantuml-1.2025.4.jar` | 22,6 MB | `1e7964277a6c3907…` |
| plantuml-generator-util 2.3.0 | `plantuml-generator-util-2.3.0.jar` | 0,2 MB | `37acc5ef41374758…` |
| Java2PlantUML (juanmf) 1.0.1 | `java2PlantUML-maven-plugin-1.0.1.jar` | 0,1 MB | `2976c50b78b9dff6…` |
| javaparser-core 3.4.0 (für mirajp1) | `javaparser-core-3.4.0.jar` | 0,9 MB | `d75382e0e660d08d…` |

## Neu bauen

```bash
cd werkzeuge

# plantuml-generator mit Abhängigkeiten (classgraph, javassist)
mvn -f pug/pom.xml dependency:copy-dependencies -DoutputDirectory=lib
javac -cp "$(ls pug/lib/*.jar | tr '\n' ':')" -d pug/driver pug/Run.java

# Java2PlantUML (juanmf), baut auf JDK 25 erst nach Anheben von source/target
git clone --depth 1 https://github.com/juanmf/Java2PlantUML.git juanmf
sed -i 's|<source>1.7</source>|<source>8</source>|; s|<target>1.7</target>|<target>8</target>|' juanmf/pom.xml
mvn -f juanmf/pom.xml -DskipTests package
mvn -f juanmf/pom.xml dependency:build-classpath -Dmdep.outputFile=cp.txt
javac -cp "juanmf/target/java2PlantUML-maven-plugin-1.0.1.jar:$(cat juanmf/cp.txt)" -d juanmf/driver juanmf/JuanmfRun.java

# genuml in einer eigenen virtuellen Umgebung, weil es click<8.2 braucht
python3 -m venv /tmp/genumlvenv
/tmp/genumlvenv/bin/pip install genuml 'click<8.2'

# zusätzliche Bibliotheken für die Projekte (41 JARs) und PlantUML zum Rendern
mvn -f extra/pom.xml dependency:copy-dependencies -DoutputDirectory=jars
mvn dependency:get -Dartifact=net.sourceforge.plantuml:plantuml:1.2025.4
```

## Bekannte Probleme

Java2PlantUML (juanmf) lässt sich mit einem aktuellen JDK nicht ohne Anpassung
bauen, weil in der pom `source` und `target` auf 1.7 stehen und javac 25 das
nicht mehr unterstützt. Außerdem findet die mitgelieferte `Main` ab Java 9 keine
Klassen: Die Bibliothek `reflections` 0.9.10 erwartet einen `URLClassLoader`, den
es seit Java 9 nicht mehr als Standard-Classloader gibt. Mit dem eigenen Treiber
`JuanmfRun.java`, der einen `URLClassLoader` übergibt, funktioniert das Werkzeug.

genuml sollte nicht in die virtuelle Umgebung des Benchmarks installiert werden.
Es braucht `click<8.2` und würde die in `werkzeuge/requirements.lock.txt` festgelegten
Versionen ändern.

## Zusätzliche Bibliotheken für die Projekte

Diese 41 Bibliotheken werden gebraucht, damit sich drei der neun Projekte
kompilieren lassen (Android, JPA, Hibernate, Hipparchus, Spring, slf4j und deren
Abhängigkeiten):

`FastInfoset-1.2.15.jar`, `activation-1.1.1.jar`, `android-4.1.1.4.jar`, `antlr-2.7.7.jar`, `byte-buddy-1.12.18.jar`, `classmate-1.5.1.jar`, `commons-codec-1.3.jar`, `commons-logging-1.1.1.jar`, `hibernate-commons-annotations-5.1.2.Final.jar`, `hibernate-core-5.6.15.Final.jar`, `hipparchus-core-3.0.jar`, `hipparchus-filtering-3.0.jar`, `hipparchus-fitting-3.0.jar`, `hipparchus-geometry-3.0.jar`, `hipparchus-ode-3.0.jar`, `hipparchus-optim-3.0.jar`, `hipparchus-stat-3.0.jar`, `httpclient-4.0.1.jar`, `httpcore-4.0.1.jar`, `istack-commons-runtime-3.0.7.jar`, `jandex-2.4.2.Final.jar`, `javax.activation-api-1.2.0.jar`, `javax.persistence-api-2.2.jar`, `jaxb-api-2.3.1.jar`, `jaxb-runtime-2.3.1.jar`, `jboss-logging-3.4.3.Final.jar`, `jboss-transaction-api_1.2_spec-1.1.1.Final.jar`, `json-20080701.jar`, `opengl-api-gl1.1-android-2.1_r1.jar`, `slf4j-api-2.0.16.jar`, `spring-aop-5.3.39.jar`, `spring-beans-5.3.39.jar`, `spring-context-5.3.39.jar`, `spring-core-5.3.39.jar`, `spring-expression-5.3.39.jar`, `spring-jcl-5.3.39.jar`, `spring-tx-5.3.39.jar`, `stax-ex-1.8.jar`, `txw2-2.3.1.jar`, `xmlParserAPIs-2.6.2.jar`, `xpp3-1.1.4c.jar`
