# Der Java-Parser

Stand 23.10.2026.

Diese Datei beschreibt, wie der eigene Java-Parser aus einem Repository einen
Klassengraphen macht, welche Datei welchen Schritt übernimmt und wo die Grenzen
liegen. Der Parser liest nur Quelltext. Das Projekt muss also weder gebaut noch
kompiliert werden. An diesem Punkt sind die Bytecode-Werkzeuge im Vergleich in
Ordner 2 gescheitert, weil sich von neun Projekten nur drei kompilieren ließen.

## Überblick

```
Repo
  -> src/io/filters.py           welche .java-Dateien gelesen werden
  -> src/parsing/java/ts_pass.py Syntaxbaum pro Datei, Klassen mit Feldern,
                                 Methoden und Obertypen (ClassInfo)
  -> src/parsing/java/resolution.py
                                 Typnamen auf Klassen im Repo abbilden
  -> einer von zwei Graphen:
       graph_builder.py          wörtlicher Graph (Standard)
       intellij.py               Klassendiagramm wie in IntelliJ
     optional javac_solver.py    Ergänzung über den JDK-Compiler
  -> src/schema/                 Graph-JSON prüfen, PlantUML erzeugen
  -> src/runs/output_writer.py   javagraph.json, javagraph.puml, Diagnosen
```

Zusammengesetzt werden die Schritte in `src/parsing/code_graph.py`. Das Ergebnis
ist ein `CodeGraph`, mit dem danach die LLM-Varianten arbeiten.

Wer lieber an einem konkreten Fall liest: Weiter unten läuft ein kleines
Programm mit zwei Klassen durch alle Stufen.

## 1. Dateien auswählen: `src/io/filters.py`

`collect_source_files` sammelt alle `*.java`-Dateien und wendet die Ausschlüsse
aus `configs/default.yaml` an. Ausgeschlossen werden Testordner, Build-Ausgaben
wie `target/`, `bin/` und `out/` sowie Dateien wie `*Test.java`.

Bei Java kommt noch `_select_java_source_sets` dazu. Wer rekursiv nach `*.java`
sucht, findet in vielen Projekten neben `src/main/java` noch alte oder
generierte Kopien derselben Klassen. Mit `source_sets: auto` (Standard) werden
deshalb die main-Verzeichnisse nach Maven/Gradle-Konvention bevorzugt. Abweichende
Quellverzeichnisse liest die Funktion aus `pom.xml` bzw. `build.gradle`
(`_configured_java_roots`). Generierte Dateien bleiben draußen, solange
`include_generated` nicht gesetzt ist. Mit `source_sets: all` wird alles gelesen,
was nach den Ausschlüssen übrig bleibt. Das braucht man bei alten Projekten ohne
übliche Struktur.

`src/parsing/languages.py` hält nur die Angaben pro Sprache fest: Dateiendung
`.java` und den Basisnamen `javagraph` für die Ausgabedateien.

## 2. Syntaxbaum lesen: `src/parsing/java/ts_pass.py`

Geparst wird mit tree-sitter und der Grammatik `tree-sitter-java`. tree-sitter
liefert auch bei Syntaxfehlern einen Baum, aus dem sich das Brauchbare noch
herauslesen lässt. Dateien mit Fehlern werden als `partial-parse` gemeldet und
trotzdem ausgewertet.

`read_source` liest jede Datei als Bytes und probiert die Encodings UTF-8,
CP1252 und Latin-1 der Reihe nach. Alter Java-Code ist oft nicht in UTF-8
gespeichert. Werkzeuge, die stur UTF-8 annehmen, verlieren solche Dateien meist,
ohne etwas zu sagen.

`_parse_file` holt aus jeder Datei zuerst die `package`-Zeile und alle Imports.
Statische Imports werden dabei wie normale Imports gespeichert. Danach läuft
`visit` durch den Baum und legt für jede Klasse, jedes Interface, Enum, Record
und jeden Annotationstyp einen Eintrag an, auch für verschachtelte Typen. Über
einen Stapel der umgebenden Namen entsteht dabei der lokale Name, zum Beispiel
`Bestellung.Position`.

`_build_record` sammelt pro Typ:

- die Art (`interface`, `enum`, `record`, `annotation`, `abstract` oder normale
  Klasse),
- `extends` und `implements` mit dem Namen, wie er im Code steht. Bei
  `interface A extends B` landet `B` unter `extends`, weil das in UML eine
  Vererbung ist und keine Realisierung,
- Felder über `_collect_field`, Record-Komponenten zählen ebenfalls als Felder,
- Methoden als Signatur, je nach Detailgrad (`member_profile`),
- die Typen in Methodensignaturen (`_method_type_refs`), die man für die
  optionalen Methodenabhängigkeiten braucht,
- die Typparameter der Klasse, damit ein `T` später nicht als Klasse gesucht
  wird.

`_split_type` zerlegt einen Typ in den Grundtyp, die Typargumente und die Angabe,
ob es um viele Elemente geht. Bei `List<Kunde>` ist das Element `Kunde`
interessant und nicht `List`. Arrays werden genauso behandelt. Qualifizierte
Namen wie `java.util.Comparator` bleiben vollständig, damit sie nicht mit einer
gleichnamigen Klasse im Projekt verwechselt werden.

`_collect_field` legt für jedes Feld eine `FieldRef` an und schätzt dabei die Art
der Beziehung:

| Fall | Beziehung | Kardinalität am Ziel |
| :--- | :--- | :--- |
| einfaches Feld | Assoziation | keine |
| Array oder Collection | Aggregation | `0..*` |
| `Optional<X>` | Assoziation | `0..1` |
| `final` und im Feld selbst mit `new` erzeugt | Komposition | `1` |
| `@OneToMany`, `@ManyToMany` | Aggregation | `0..*` |
| `@OneToOne`, `@ManyToOne` | Assoziation | `0..1` |
| `@Embedded`, `@ElementCollection` | Komposition | `1` bzw. `0..*` |

Private Felder zählen mit. In Java ergibt erst das private Feld zusammen mit dem
öffentlichen Getter die Assoziation.

`analyze_java` ruft das alles für die ausgewählten Dateien auf und räumt danach
auf:

- Kommt derselbe voll qualifizierte Name in einem Modul zweimal vor, bleibt die
  Datei mit dem kürzesten Pfad. Der Konflikt wird als `duplicate-declaration`
  gemeldet.
- Kommt derselbe Name in verschiedenen Maven/Gradle-Modulen vor, bekommen die
  Klassen IDs mit Modulpräfix (`modules.<modul>...`).
- Das gemeinsame Paketpräfix aller Klassen wird abgeschnitten. Aus
  `de.firma.app.model.Kunde` wird `model.Kunde`. So haben Java-IDs dieselbe Form
  wie die repo-relativen Python-Module, und der erste Teil des Pakets taugt als
  Gruppe für das Clustering. Der ursprüngliche Name bleibt in
  `source_qualified_name` erhalten.

Das Ergebnis ist eine Liste von `ClassInfo` (definiert in
`src/parsing/models.py`) plus eine Liste von Diagnosen.

## 3. Typnamen auflösen: `src/parsing/java/resolution.py`

Im Code steht meistens nur `Kunde`, gebraucht wird aber die Klasse, die damit
gemeint ist. `JavaTypeResolver.resolve(name, quelle)` sucht in dieser
Reihenfolge, die ungefähr der Regel des Compilers folgt:

1. Typparameter der Klasse. Ein `T` ist keine Klasse und ergibt nichts.
2. Eigene und umschließende Typen, von innen nach außen, einschließlich
   verschachtelter Typen, die von einer Oberklasse geerbt werden.
3. Ausdrückliche Imports. Ein Import gilt auch dann, wenn er auf eine
   Bibliotheksklasse zeigt und es im Projekt eine Klasse mit demselben Kurznamen
   gibt.
4. Dasselbe Paket.
5. Voll qualifizierte Namen.
6. Stern-Importe und `java.lang`.

Gibt es mehrere Kandidaten, wird zuerst im eigenen Build-Modul gesucht. Bleibt
es mehrdeutig, wird die Beziehung weggelassen und als `ambiguous-type` gemeldet.
Ein falscher Pfeil wäre schlimmer als ein fehlender. Ergebnisse werden pro
(Klasse, Name) zwischengespeichert.

`external_name` liefert für Typen außerhalb des Projekts den Namen aus dem
passenden Import, also `javax.swing.JFrame` statt nur `JFrame`.

Der Resolver ist kein Ersatz für einen Compiler. Er kennt keine JARs und keine
lokalen Variablen. Für den IntelliJ-Modus, der auch Methodenrümpfe auswertet,
gibt es deshalb eine eigene Typbestimmung (Abschnitt 5).

## 4. Der wörtliche Graph: `src/parsing/java/graph_builder.py`

`build_java_graph` ist der Standard und das Gegenstück zu pyreverse bei Python.
Diesen Graphen bekommen die `catalog`-Varianten als Kontext, und die
`prune`-Varianten starten mit ihm. Er enthält alles, was sich aus den
Deklarationen ablesen lässt. Abstrahiert wird erst später durch das LLM.

- Jede deklarierte Klasse wird ein Knoten mit Paket, Stereotyp, Attributen,
  Methoden und Fundstelle. Der Stereotyp kommt aus `_STEREOTYPE_MAP`, ein Record
  wird zum Beispiel zu `dataclass`.
- `extends` ergibt eine Vererbung, `implements` eine Realisierung.
- Obertypen außerhalb des Projekts bleiben als Knoten im Paket `external`
  erhalten. Dass eine Klasse von `JFrame` erbt, sagt viel über ihre Rolle. Felder
  mit externen Typen wie `String` oder `Timer` ergeben dagegen keine Kante, sonst
  ginge die Architektur zwischen lauter Bibliotheksknoten unter.
- Jede `FieldRef`, deren Typ sich auf eine Projektklasse auflösen lässt, wird
  eine Kante mit der Art und Kardinalität aus Schritt 2 und dem Feldnamen als
  Rolle. Zwei Felder auf dasselbe Ziel (`primary` und `history`) bleiben zwei
  Kanten.
- Mit `include_method_dependencies` kommen Abhängigkeiten aus
  Methodensignaturen dazu, standardmäßig nicht.
- Kanten aus dem javac-Modus werden zusammengeführt. Gibt es die Beziehung schon
  aus dem Quelltext, bekommt sie nur die zusätzliche Fundstelle. Die Art der
  Beziehung aus dem Quelltext bleibt, weil javac nichts über Besitz im Sinn von
  UML weiß.

Jede Kante trägt `EdgeEvidence` mit Feld oder Methode, geschriebenem Typ, Datei
und Zeile. Damit lässt sich jeder Pfeil im Diagramm bis zur Codezeile
zurückverfolgen.

## 5. Der IntelliJ-Modus: `src/parsing/java/intellij.py`

Mit `relation_style: intellij` (bzw. `--java-relations intellij`) wird statt
des wörtlichen Graphen das Klassendiagramm erzeugt, das IntelliJ IDEA für
dieselben Klassen zeichnet. Der wichtigste Unterschied: IntelliJ liest auch die
Methodenrümpfe und findet dadurch Verbindungen über eine dritte Klasse. In
RaiseMeUp ruft `PetObserver` zum Beispiel
`RaiseMeUp.getCurrentJob().getImpactenergy()` auf. `getImpactenergy` ist in
`Job` deklariert, also hängt `PetObserver` von `Job` ab, obwohl `Job` in der
Datei nirgends steht.

`build_intellij_graph` arbeitet in zwei Durchläufen.

Im ersten Durchlauf entsteht eine Symboltabelle. `analyze_java` liefert die
Klassen, `_collect_bodies` parst die Dateien noch einmal und hält pro Klasse den
Syntaxknoten, die Felder und Methoden mit ihren Typknoten, Parametern und
Typparametern sowie die statischen Imports fest. `_Model` bündelt das und bietet:

- `resolve_name` und `type_of_node`: Typnamen werden zu einem `JType` mit Art
  `project`, `jdk` oder `external`, dazu Typargumente und Array-Dimensionen,
- `lineage`: die Klasse und alle Obertypen im Projekt,
- `find_method`, `find_field`: Member auch in Oberklassen suchen. Überladene
  Methoden werden über die Zahl der Argumente unterschieden,
- `member_type`: Rückgabetyp bzw. Feldtyp, mit einfacher Ersetzung von
  Typparametern (`Box<Kunde>.get()` liefert `Kunde`),
- `jdk_member_type`: Rückgabetypen der wenigen JDK-Methoden, die man für
  Aufrufketten braucht, etwa `get` auf einer Liste oder `values()` auf einer Map,
- `iterable_element`: Elementtyp von Arrays, JDK-Collections und Projektklassen,
  die von einer JDK-Collection erben.

Im zweiten Durchlauf geht `_BodyScanner` durch den Rumpf jeder Klasse im
Diagramm. Er merkt sich lokale Variablen, Parameter, Variablen aus `for`,
`catch`, `try` mit Ressourcen und `instanceof`-Mustern samt Gültigkeitsbereich.
`type_of` bestimmt den Typ eines Ausdrucks Schritt für Schritt. Bei
`a.b().c()` wird erst der Typ von `a` gesucht, dann die Methode `b` in dieser
Klasse und ihr Rückgabetyp, dann `c`. Jeder Verweis unterwegs wird mit `note`
festgehalten:

- Typen in Signaturen, Feldern, lokalen Variablen, Casts, `instanceof`,
  Klassenliteralen und statische Zugriffe über den Klassennamen zählen für diesen
  Typ.
- Ein Methodenaufruf zählt für die Klasse, die die Methode deklariert. Wird eine
  geerbte Methode aufgerufen, ist das die Oberklasse.
- `new X()` wird als `create` vermerkt.
- `this(...)` und `super(...)` im Konstruktor zählen für die eigene bzw. die
  Oberklasse.
- Zugriffe auf Felder zählen nicht.
- Verschachtelte Klassen werden übersprungen, sie haben ihren eigenen Durchlauf.

Danach werden die Kanten zusammengesetzt:

1. Vererbung und Realisierung. Steht ein Obertyp nicht im Diagramm, sucht eine
   Breitensuche weiter oben nach dem nächsten Obertyp, der drinsteht.
2. Felder (`_field_relation`). Ein Feld mit einer Klasse aus dem Diagramm als Typ
   wird eine Komposition mit "1" an beiden Enden. Bei Arrays, JDK-Collections und
   Projektklassen, die von einer JDK-Collection erben, steht "*" am Ziel. Maps
   ergeben nichts.
3. Verschachtelung. Eine innere Klasse bekommt eine `nesting`-Kante von der
   äußeren Klasse aus.
4. Abhängigkeiten aus dem zweiten Durchlauf. Eine einfache Abhängigkeit fällt
   weg, wenn in derselben Richtung schon eine Vererbung, Realisierung oder
   Feldbeziehung besteht oder wenn eine innere Klasse ihre äußere benutzt. Eine
   Abhängigkeit mit `«create»` bleibt immer stehen.

Zwei Eingaben steuern das Ergebnis zusätzlich:

- `diagram`: die voll qualifizierten Namen der Klassen, die im Diagramm stehen
  sollen. In IntelliJ wählt das der Mensch aus, deshalb wird es übergeben. Ohne
  Auswahl kommen alle Klassen hinein. Für Aufrufketten werden trotzdem alle
  Dateien des Projekts gelesen.
- `IdeEnvironment`: wie das Projekt in IntelliJ geöffnet war. Mit `jdk=False`
  kennt IntelliJ `List` usw. nicht, und Collection-Felder bekommen keine Linie.
  Mit `same_package=False` findet IntelliJ Klassen aus demselben Paket nur noch,
  wenn sie ausdrücklich importiert sind. Beide Fälle kommen in den Bildern von
  Zhang/Hebig vor.

Externe Klassen bekommen im IntelliJ-Modus IDs der Form `external.<Kurzname>`.
Bei Stern-Imports lässt sich der volle Name aus dem Quelltext allein nicht
bestimmen. Die javac-Ergänzung wird in diesem Modus nicht eingemischt.

Wie die Regeln aus den neun IntelliJ-Bildern abgeleitet und daran geprüft
wurden, steht in Ordner 2 unter `doku/intellij-nachbildung.md`.

## 6. Ergänzung über javac: `src/parsing/java/javac_solver.py`

Mit `symbol_solver: javac` wird zusätzlich der JDK-Compiler gefragt. Das Modul
schreibt ein kleines Java-Hilfsprogramm in ein temporäres Verzeichnis, übersetzt
es und lässt es pro Build-Modul über die Quelldateien laufen. Das Programm nutzt
die öffentliche Compiler-API (`javax.tools`, `com.sun.source`), löst Feldtypen
und Obertypen auf und gibt pro Fund eine Zeile aus. Fehlende Bibliotheken führen
nur zu einer Diagnose (`javac-partial-resolution`). Was javac trotzdem einer
Projektklasse zuordnen konnte, kommt als Kante mit `resolver="javac"` zurück.
Über `classpath` lassen sich JARs mitgeben. Ohne installiertes JDK gibt es die
Diagnose `javac-unavailable` und sonst keine Änderung.

## 7. Paketabhängigkeiten: `src/parsing/java/import_graph.py`

Für das Clustering und die Paketübersicht braucht die Pipeline Abhängigkeiten
zwischen Paketen. Bei Python kommen die aus den Importzeilen. Bei Java taugen
Imports dafür wenig, weil Klassen im selben Paket gar keinen Import brauchen und
Stern-Importe keine Klasse nennen. `build_import_graphs` baut den Graphen
deshalb aus aufgelösten Obertypen und Feldtypen, also aus denselben Angaben wie
den Klassengraphen. Es gibt zwei Ebenen: Paket zu Paket und oberstes Paket zu
oberstem Paket.

## 8. Zusammensetzen: `src/parsing/code_graph.py`

`_build_java` ruft der Reihe nach `analyze_java`, `build_import_graphs`,
optional `resolve_with_javac` und dann je nach `relation_style`
`build_intellij_graph` oder `build_java_graph` auf. Dazu kommt eine einfache
Vererbungstabelle. Alles landet in einem `CodeGraph`.

Die Optionen stehen in `JavaConfig` (`src/config/models.py`), werden in
`src/config/loader.py` geprüft und lassen sich über `src/cli.py` setzen:

| Option | Kommandozeile | Bedeutung |
| :--- | :--- | :--- |
| `source_sets` | `--java-source-sets` | `auto` oder `all`, siehe Abschnitt 1 |
| `include_generated` | `--java-include-generated` | generierte Quelldateien mitlesen |
| `member_profile` | `--java-member-profile` | `structure`, `summary`, `public-api` oder `full` |
| `include_external_supertypes` | `--no-java-external-supertypes` | externe Obertypen als Knoten behalten (Standard) bzw. weglassen |
| `include_method_dependencies` | `--java-method-dependencies` | Abhängigkeiten aus Methodensignaturen |
| `symbol_solver`, `classpath` | `--java-symbol-solver`, `--java-classpath` | javac-Ergänzung |
| `relation_style` | `--java-relations` | `literal` oder `intellij` |
| `diagram_classes` | `--java-diagram-classes DATEI` | Klassenauswahl für den IntelliJ-Modus |
| `ide_jdk` | `--java-ide-no-jdk` | IntelliJ ohne JDK nachbilden |
| `ide_same_package` | `--java-ide-no-same-package` | IntelliJ mit falschem Source-Root nachbilden |

`src/parsing/cache.py` speichert den fertigen `CodeGraph` zwischen. Der
Schlüssel enthält Pfad, Größe und Änderungszeit jeder Datei, die Java-Optionen
und eine Versionsnummer des Parsers. Ändert sich der Parser so, dass alte
Ergebnisse nicht mehr stimmen, wird die Versionsnummer erhöht.

## 9. Graph-Modell und Ausgabe

`src/schema/graph.py` definiert `AbstractGraph`, `Node`, `Edge`, `EdgeEvidence`
und `Diagnostic`. `src/schema/validator.py` prüft Kantenarten und Stereotypen
und behält bei doppelten Kanten die stärkere. `src/schema/plantuml.py` erzeugt
daraus PlantUML:

| Kantenart | PlantUML |
| :--- | :--- |
| `inheritance` | `--\|>` |
| `realization` | `..\|>` |
| `composition` | `*--` |
| `aggregation` | `o--` |
| `association` | `-->` |
| `dependency` | `..>` |
| `nesting` | `+--` |

Beschriftungen wie `«create»` werden als `<<create>>` geschrieben, weil PlantUML
die Guillemets sonst verschluckt.

`write_static_graph_outputs` in `src/runs/output_writer.py` schreibt pro Repo
`javagraph.json`, `javagraph.puml` und, falls es Diagnosen gibt,
`javagraph.diagnostics.json`.

## 10. Tests

| Datei | Prüft |
| :--- | :--- |
| `tests/test_java_parsing.py` | Syntaxbaum, Felder und Kardinalitäten, Encodings, Präfix, Module, wörtlicher Graph, javac-Modus |
| `tests/test_java_resolution.py` | Auflösungsreihenfolge, Imports, verschachtelte und geerbte Typen, Mehrdeutigkeit |
| `tests/test_java_intellij.py` | IntelliJ-Modus: Aufrufketten, Schleifen, Felder mit "1" und "*", Umgebungen, PlantUML |

Gemessen gegen echte Diagramme wurde der Parser in Ordner 2.

## Beispiel: zwei Klassen durch alle Stufen

Ein kleines Programm mit zwei Klassen in zwei Paketen. Die Ausgaben unten
stammen aus einem echten Lauf des Parsers und sind nur gekürzt.

```java
// src/main/java/de/uni/bib/Bibliothek.java
package de.uni.bib;

import de.uni.bib.model.Buch;
import java.util.ArrayList;
import java.util.List;

public class Bibliothek {
    private final List<Buch> buecher = new ArrayList<>();                     // Zeile 8

    public void hinzufuegen(String titel) { buecher.add(new Buch(titel)); }    // Zeile 11
    public String ersterTitel() { return buecher.get(0).getTitel(); }          // Zeile 15
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

Zusätzlich liegen im Projekt ein Test unter `src/test/java/` und eine alte Kopie
von `Buch.java` unter `target/classes/`.

### Dateien auswählen

```
gefunden: src/main/java/de/uni/bib/Bibliothek.java
gefunden: src/main/java/de/uni/bib/model/Buch.java
gefunden: src/test/java/BibliothekTest.java
gefunden: target/classes/de/uni/bib/model/Buch.java
gewählt:  src/main/java/de/uni/bib/Bibliothek.java
gewählt:  src/main/java/de/uni/bib/model/Buch.java
```

`test` und `target` stehen in den Ausschlüssen. Ohne diese Regel gäbe es `Buch`
zweimal, und womöglich würde die veraltete Kopie gelesen.

### Syntaxbaum und ClassInfo

tree-sitter liefert für `Buch.java` diesen Baum (verkürzt):

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

Daraus entstehen zwei `ClassInfo`:

| | Bibliothek | Buch |
| :--- | :--- | :--- |
| `source_qualified_name` | `de.uni.bib.Bibliothek` | `de.uni.bib.model.Buch` |
| `qualified_name` (ID) | `Bibliothek` | `model.Buch` |
| `module` | leer | `model` |
| `interfaces` | | `Comparable` |
| `imports` | `de.uni.bib.model.Buch`, `java.util.ArrayList`, `java.util.List` | |
| `attributes` | `buecher: List<Buch>` | `titel: String` |
| `methods` | `hinzufuegen(String)`, `ersterTitel()` | `compareTo(Buch)`, `getTitel()` |

Beide Pakete beginnen mit `de.uni.bib`. Dieses Präfix wird abgeschnitten, deshalb
hat `Bibliothek` kein Paket mehr und `Buch` liegt in `model`.

Für das Feld `buecher` zerlegt `_split_type` den Typ `List<Buch>` in den Container
`List` und das Element `Buch`. `_collect_field` legt daraus an:

```
FieldRef(field_name='buecher', type_name='Buch', many=True,
         declared_type='List<Buch>', line=8,
         relation_type='aggregation', target_card='0..*')
```

Die Methodenrümpfe werden in dieser Stufe nicht gelesen, nur die Signaturen.

### Auflösung

```
in Bibliothek: 'Buch'       -> model.Buch   (ausdrücklicher Import)
in Bibliothek: 'List'       -> keine Projektklasse, extern java.util.List
in Buch:       'Comparable' -> keine Projektklasse, extern Comparable (java.lang)
in Buch:       'Bibliothek' -> nichts (anderes Paket, nicht importiert)
```

### Wörtlicher Graph

```
Knoten  Bibliothek
Knoten  model.Buch
Knoten  external.Comparable
Kante   aggregation  Bibliothek -> model.Buch  buecher 0..*
        Fundstelle: Feld buecher, List<Buch>, Bibliothek.java Zeile 8
Kante   realization  model.Buch -> external.Comparable
        Fundstelle: implements Comparable, Buch.java Zeile 3
```

`Comparable` bleibt als externer Knoten stehen, weil es ein Obertyp ist. Das Feld
`titel` vom Typ `String` ergibt keine Kante. Der Paketgraph aus
`import_graph.py` ist `{'': ['model']}`: Das oberste Paket hängt von `model` ab.

```
Bibliothek o-- "0..*" Buch : buecher
Buch ..|> Comparable
```

Dass `Bibliothek` ein `Buch` erzeugt und `getTitel()` aufruft, sieht dieser Modus
nicht.

### IntelliJ-Modus

Der erste Durchlauf baut die Symboltabelle:

```
Bibliothek  Felder {buecher: List<Buch>}   Methoden {hinzufuegen: 1 Parameter, ersterTitel: 0}
model.Buch  Felder {titel: String}         Methoden {<init>: 1, getTitel: 0, compareTo: 1}
```

Im zweiten Durchlauf ist `buecher.get(0).getTitel()` die interessante Stelle.
`type_of` geht sie Schritt für Schritt durch:

1. `buecher` ist keine lokale Variable, also ein Feld vom Typ `List<Buch>`.
2. `.get(0)` auf einer `List` liefert über `jdk_member_type` das Element `Buch`.
3. `.getTitel()` wird mit `find_method` in `Buch` gefunden. Der Aufruf zählt
   damit als Verweis auf `Buch`.

Alle Verweise, die `_BodyScanner` notiert:

```
Bibliothek -> Buch        create, use  (Feldtyp Zeile 8, new Buch Zeile 11, getTitel Zeile 15)
Bibliothek -> ArrayList   create
Bibliothek -> List, String use
Buch -> Buch              use          (Comparable<Buch>, Parameter Buch other, other.getTitel())
Buch -> Comparable, String use
```

Ohne Klassenauswahl stehen nur die beiden Projektklassen im Diagramm. `List`,
`String` und `Comparable` fallen deshalb weg. Für den Rest gelten die Regeln aus
Abschnitt 5:

| Regel | Ergebnis |
| :--- | :--- |
| Feld `List<Buch>`, eine JDK-Collection | `Bibliothek "1" *-- "*" Buch : buecher` |
| `new Buch(...)` | `Bibliothek ..> Buch : <<create>>`, bleibt trotz Feldkante |
| einfache Abhängigkeit Bibliothek zu Buch | entfällt, weil es schon die Feldkante gibt |
| `Buch` benutzt den eigenen Typ und ruft eine eigene Methode auf | Schleife `Buch ..> Buch` |
| `Comparable` | keine Realisierung, weil `Comparable` nicht im Diagramm steht |

```
Bibliothek "1" *-- "*" Buch : buecher
Bibliothek ..> Buch : <<create>>
Buch ..> Buch
```

Steht `java.lang.Comparable` in der Klassenauswahl, kommt auch die Realisierung
dazu. In echten Projekten laufen solche Ketten oft über drei Klassen, etwa
`RaiseMeUp.getCurrentJob().getImpactenergy()` in RaiseMeUp.

### Ausgabe

`to_plantuml` erzeugt die PlantUML-Texte oben, `write_static_graph_outputs`
schreibt `javagraph.json` und `javagraph.puml`. Diagnosen gab es in diesem
Beispiel keine, also auch keine `javagraph.diagnostics.json`.

## Grenzen

- Ohne Build gibt es keine Informationen aus Bibliotheken. Ein Rückgabetyp aus
  einer Bibliothek beendet eine Aufrufkette, abgesehen von den gängigen
  JDK-Collections.
- Überladene Methoden werden nur über die Zahl der Argumente unterschieden.
- Lambdas ohne Typangabe und `var` mit schwer bestimmbarem Typ beenden eine
  Aufrufkette ebenfalls.
- Mehrdeutige Typen werden weggelassen. Das kostet im Zweifel eine richtige
  Kante, vermeidet aber falsche.
- Die Art einer Feldbeziehung im wörtlichen Graphen (Assoziation, Aggregation,
  Komposition) ist eine Schätzung aus Typ, `final`, Initialisierung und
  JPA-Annotationen. Ob eine Klasse ein Objekt wirklich besitzt, steht so nicht im
  Code.
