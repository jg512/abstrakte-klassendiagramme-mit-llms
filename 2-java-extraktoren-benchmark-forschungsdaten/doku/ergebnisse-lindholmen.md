**Deutsch** · [English](ergebnisse-lindholmen.en.md)

# Ergebnisse: Extraktoren auf 30 Lindholmen-Projekten und der Zhang/Hebig-Suite

Stand 20.09.2026, Erweiterungen am Extraktor vom 21.09.2026.

Hier stehen die Ergebnisse des ersten Vergleichs: Drei Werkzeuge, die aus
Java-Quelltext ein Klassendiagramm erzeugen, darunter der eigene Parser, wurden
mit den Diagrammen verglichen, die zu 30 Projekten aus dem Lindholmen-Datensatz
und zu den neun Projekten von Zhang/Hebig gehören. Die neun Projekte von
Zhang/Hebig heißen hier "Suite" (eine feste Zusammenstellung von Testfällen).
Außerdem beschreibt die Datei, welche Fehler im eigenen Parser dabei auffielen
und behoben wurden. Precision, Recall und F1 erklärt das
[Haupt-README](../../README.md#begriffe). "Fertig" heißt in den Tabellen, dass
das Werkzeug ohne Absturz eine Ausgabe geliefert hat.

Für den Benchmark wurden 30 Projekte aus dem Lindholmen-Datensatz
heruntergeladen, jeweils zusammen mit ihrem UML/XMI-Modell aus demselben
Git-Commit. Zusammen sind das 4.040 Java-Dateien. Drei Extraktoren bekamen
dieselben Eingaben und wurden miteinander verglichen.

Die Werte geben an, wie gut die Ausgabe zum Diagramm passt. Wie korrekt der
Code gelesen wurde, lässt sich daraus nicht ablesen. Die Diagramme in den Repos
können unvollständig, abstrahiert, generiert oder veraltet sein und sind deshalb
keine geprüfte Ground Truth.

## Zhang/Hebig-Suite mit drei Extraktoren

Zusätzlich wurde das Replikationspaket der Studie von Zhang, Zhang, Strüber und
Hebig (2025) heruntergeladen und gemessen. Es enthält neun Java-Projekte in der
untersuchten Version, 79 Klassen in den Modellen, 82 von den Autoren gezählte
Beziehungen, die Originaldiagramme, die Annotationen der Autoren, per Reverse
Engineering erzeugte Diagramme und eine Vergleichstabelle pro Projekt. In drei
Diagrammen gibt es doppelte gerichtete Assoziationen zwischen denselben Klassen.
Wenn man Assoziationen ungerichtet zählt, bleiben 79 Beziehungen.
`daten/zhang-hebig/reference.json` ist eine von Hand erstellte Abschrift der
Diagramme, die Originalbilder, PDFs und Tabellen liegen daneben. Die
Laufzeiten stammen aus diesem Lauf. Die spätere Messung mit sieben Werkzeugen
in [`ergebnisse-zhang-hebig.md`](ergebnisse-zhang-hebig.md) ist ein eigener
Lauf mit leicht anderen Zeiten.

| Extraktor | fertig | Knoten-Recall | Kanten-Precision | Kanten-Recall | Micro-F1 | Zeit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| eigener Extraktor (korrigiert) | 9/9 | 0,924 | 0,757 | 0,671 | 0,711 | 0,24 s |
| javalang + Adapter | 9/9 | 0,924 | 0,757 | 0,671 | 0,711 | 0,79 s |
| java2plantuml (mirajp1) | 9/9 | 0,924 | 0,827 | 0,544 | 0,656 | 6,83 s |

Alle drei finden dieselben 73 von 79 Klassen. Die sechs fehlenden Klassen gibt
es laut den Autoren so nicht im Code: fünf Klassen aus RaiseMeUp, die im Code
fehlen oder anders umgesetzt sind, und die Klasse `Link` in myblog, die nur im
Modell vorkommt. Bei den Beziehungen liegen der eigene Extraktor und javalang
gleichauf. java2plantuml hat eine höhere Precision, findet aber weniger
Beziehungen.

Die spätere Messung mit allen sieben Werkzeugen steht in
[`ergebnisse-zhang-hebig.md`](ergebnisse-zhang-hebig.md), die genauere Analyse
einzelner Projekte in [`fallstudien.md`](fallstudien.md).

## Ergebnisse auf den 30 Lindholmen-Projekten

Micro-F1 zählt alle Linien aller Projekte zusammen, Macro-F1 ist der
Mittelwert der F1-Werte der einzelnen Projekte.

| Extraktor | fertig | Kanten-Precision | Kanten-Recall | Micro-F1 | Macro-F1 | Zeit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| eigener Extraktor, vorher | 30/30 | 0,770 | 0,561 | 0,649 | 0,739 | 7,51 s |
| eigener Extraktor, korrigiert | 30/30 | 0,739 | 0,574 | 0,646 | 0,736 | 8,56 s |
| javalang + Adapter | 30/30 | 0,739 | 0,574 | 0,646 | 0,736 | 29,00 s |
| java2plantuml (mirajp1) | 30/30 | 0,756 | 0,466 | 0,577 | 0,684 | 59,68 s |

Bewertet wurden 470 Klassen und 399 Beziehungen, die sich zwischen Modell und
Quelltext zuordnen ließen. Insgesamt enthielten die Modelle 1.182 benannte
Klassen und 829 Beziehungen. Nicht zugeordnete Namen, mehrdeutige Treffer und
nicht unterstützte Referenzen sind in `daten/lindholmen/manifest.json`
festgehalten.

Alle Werkzeuge haben alle zugeordneten Klassen gefunden (Knoten-Recall 1,0). Da
die Zuordnung selbst mit javalang vorbereitet wurde, sagt das aber wenig über
die Genauigkeit bei den Knoten aus. Klassen aus dem Modell, die sich nicht
zuordnen ließen, wurden ausgeschlossen. Klassen aus dem Quelltext, die nicht im
Diagramm vorkommen, zählen nicht als Fehler.

Der korrigierte Extraktor findet fünf Referenzbeziehungen mehr (229 statt 224
von 399). Gleichzeitig gibt er 14 zusätzliche Beziehungen aus, die zwar im
Quelltext vorhanden sind, aber nicht im Diagramm stehen (81 statt 67). Dadurch
sinkt der Micro-F1 leicht von 0,649 auf 0,646. Die Extraktion ist dadurch nicht
schlechter geworden, der Wert zeigt eher den Unterschied zwischen dem, was im
Code steht, und dem, was im Diagramm dargestellt wurde.

Die Laufzeiten sind einzelne Messungen auf einem Rechner und enthalten das
Parsen und den Aufbau des Graphen, bei java2plantuml auch den Start der JVM und
das Umkodieren nach UTF-8. Download und Vorbereitung der Referenzen sind nicht
enthalten.

## Korrekturen am eigenen Extraktor

Die folgenden Punkte sind eher technisch. Kurz gesagt wurden Fälle behoben, in
denen der Parser einen Namen der falschen Klasse zugeordnet oder eine
Beziehung übersehen hat.

- Die vollständigen Java-Namen sowie Paket- und Importinformationen bleiben
  erhalten. Explizite Imports werden nicht mehr fälschlich gleichnamigen
  Projektklassen zugeordnet.
- Stern-Importe und geerbte verschachtelte Typen werden aufgelöst. Mehrdeutige
  Treffer werden gemeldet und weggelassen.
- Klassengraph, Abhängigkeitsgraph und Vererbungsgraph verwenden dieselbe
  Auflösung, damit das Clustering keine widersprüchlichen Daten bekommt.
- Felder und Methoden in Enums, Konstanten in Interfaces und Array-Klammern
  hinter dem Variablennamen werden jetzt erkannt.
- Projektklassen in eigenen generischen Klassen wie `NeurophArrayList<Neuron>`
  werden erkannt.
- Selbstassoziationen bleiben erhalten, und Klassen im Standardpaket werden nicht
  mehr mit gleichnamigen Klassen in benannten Paketen verwechselt.
- Der Parser-Cache (Zwischenspeicher für schon gelesene Projekte) hat eine
  Versionsnummer bekommen, damit keine veralteten Einträge geladen werden.

Nebenbei wurden zwei Dinge an der Arbeitsumgebung repariert, die mit dem
Extraktor selbst nichts zu tun haben: Die Python-Umgebung (`.venv`) war
beschädigt und wurde neu aufgesetzt, und ein Eintrag `runs/` in `.gitignore`
hatte auch das Quellpaket `src/runs/` ausgeschlossen (jetzt `/runs/`).

Für diese Fälle und für zyklische Vererbung kamen 13 neue Tests dazu. Sieben der
ersten acht Tests schlugen vor den Änderungen fehl. Der achte (geerbter Typ) lief
durch Zufall auch mit der alten Version durch und wurde deshalb verschärft.
Danach liefen 385 Tests erfolgreich (1 Netztest abgewählt), dazu 10 Tests für
die Normalisierung und die Referenzdaten. In den 4.040 Java-Dateien gab es keine
Datei, die tree-sitter nicht parsen konnte.

Die Pipeline wurde außerdem mit allen acht Varianten als Trockenlauf
(`--dry-run --no-cleanup`) auf einem Java-Projekt ausgeführt und hat jeweils
Diagramme und Zusammenfassungen geschrieben. Damit ist nur geprüft, dass die
einzelnen Teile zusammenarbeiten, nicht die Qualität echter LLM-Diagramme. Der
Platzhalter für das LLM erfindet bei den prune-Varianten zusätzliche Klassen,
deshalb meldet die Pipeline dort, dass das Diagramm zu viele Klassen hat. Das
ist erwartet und kein Fehler.

## Erweiterungen am Extraktor

Im Anschluss wurde der Extraktor weiter ausgebaut. Er erkennt jetzt die üblichen
und die konfigurierten Quellverzeichnisse von Maven und Gradle, unterscheidet
gleichnamige Klassen in verschiedenen Build-Modulen, bietet vier Detailstufen für
Member und kann auf Wunsch Abhängigkeiten über Parameter und Rückgabetypen
ausgeben. Zu jeder Kante werden Rolle (Feld oder Methode), deklarierter Typ und
Fundstelle gespeichert. Aus `Optional`, Collections, Arrays, `final`-Feldern und
gängigen JPA-Annotationen werden Kardinalität und Besitz abgeleitet.
Verschachtelte Klassen mit gleichem Namen bekommen in PlantUML eindeutige
Beschriftungen. Mehrdeutigkeiten, doppelte Deklarationen, Parse-Fehler und
Fehler bei der javac-Auflösung werden in einer eigenen Datei ausgegeben.

Über einen optionalen `javac`-Modus kann die Auflösung zusätzlich über die
Compiler-API des JDK und einen angegebenen Classpath ergänzt werden. Die
Ergebnisse aus dem Quelltext haben dabei Vorrang. Standardmäßig läuft der
Extraktor ohne Build.

Ein eigener Benchmark mit 20 fest vorgegebenen Fällen in modernem Java (Records,
Sealed-Typen, verschachtelte Typen, Imports, Generics, Selbstbeziehungen,
Kardinalität, Komposition, JPA-Annotationen, Methodenabhängigkeiten) lag damals
in Ordner 1 und liegt heute in Ordner 3 unter
[`benchmarks/java_literal/`](../../3-java-parser-klassendiagramme/benchmarks/java_literal/README.md).
Der Extraktor besteht alle 20 Fälle. Von den Projekttests laufen 402 erfolgreich
durch (1 Netztest abgewählt).

Der erweiterte Extraktor wurde noch einmal auf denselben Eingaben gemessen. Die
Werte auf den 30 Projekten sind gleich geblieben (Knoten-Recall 1,000,
Kanten-Precision 0,739, Recall 0,574, F1 0,646), auf der Zhang/Hebig-Suite
ebenfalls (Knoten-F1 0,961, Kanten-F1 0,711). Die Ergebnisse liegen in
`ergebnisse/messungen/enhanced/` und `ergebnisse/messungen/curated-enhanced/`.

## Am Code geprüfte Beispiele

- `hodiqual/projet2015`: Die Treffer steigen von 31 auf 33. Das Enum `TypePoint`
  enthält ein Feld `Map<String, TypePoint>`, also ein Feld im Enum, das auf sich
  selbst verweist.
- `jainebri/Super-Simple-Stocks`: Die Treffer steigen von 10 auf 11. Das
  Interface `SimpleStockServicesFactory` deklariert ein eigenes Singleton
  `INSTANCE`.
- `Neseek77/gwt-ent`: Die Treffer steigen von 2 auf 3, durch Selbstbeziehungen in
  einer Reflection-API.
- `shadeven/cerebrumehr`: Kein Werkzeug findet eine der 96 Kanten. Im Quelltext
  hängen die Beziehungen meist an generierten `*Base`-Klassen, während das
  Diagramm die Fachklassen zeigt. Das Diagramm bildet hier also eine andere Ebene
  ab als der Code.
- Die meisten zusätzlichen Kanten sind Selbstassoziationen, etwa Wertetabellen in
  Enums oder Singletons. Bei Neuroph wurde außerdem eine Beziehung über eine
  eigene generische Klasse übersehen, die jetzt erkannt wird.

## Einschränkungen

- Die 30 Projekte sind eine eigene Auswahl aus einem veröffentlichten Datensatz
  und kein von Menschen geprüfter Goldstandard.
- Die Auswahl bevorzugt kleine, erreichbare Projekte mit XML-Modellen, die sich
  mit Java 8 parsen lassen. Pro Repo wurde nur ein Modell verwendet.
- Assoziationen werden ohne Richtung, Multiplizität und Besitz verglichen,
  Vererbung und Realisierung mit Richtung und Typ.
- Der Vergleich mit javalang beruht auf einem eigenen Adapter mit einfacherer
  Typauflösung.
- Zeitlimits: 120 Sekunden pro Adapter, 90 Sekunden für java2plantuml. Alle Läufe
  wurden innerhalb dieser Zeit fertig.
- Nicht gemessen wurde, wie gut ein LLM daraus abstrahiert, ob Annotationen
  richtig gedeutet werden, ob mit vorhandenen Bibliotheken (über den Classpath)
  mehr gefunden würde und ob jede gefundene Beziehung inhaltlich stimmt.

Zur Kontrolle wurden alle 90 Läufe auf den Lindholmen-Projekten (30 Projekte mal
3 Werkzeuge) und alle 27 Läufe auf der Zhang/Hebig-Suite (9 mal 3) wiederholt.
Status, Knoten- und Kantenwerte und Abweichungen waren identisch
(`ergebnisse/messungen/reproduction-verification.json`).

## Dateien

- [`doku/recherche-datensätze.md`](recherche-datensätze.md): Papers, verworfene
  Alternativen, Regeln der Auswertung
- `daten/lindholmen/manifest.json`: die 30 festgelegten Paare aus Projekt,
  Commit, Modell und Quelltext
- `daten/lindholmen/reference-graphs/`: normalisierte Referenzen in JSON und
  PlantUML, die Originale liegen unter `daten/lindholmen/corpus/`
- `ergebnisse/messungen/before/`, `ergebnisse/messungen/final/`,
  `ergebnisse/messungen/comparison.json`, `ergebnisse/messungen/aggregate.json`:
  Rohdaten und Ergebnisse
- `daten/zhang-hebig/` und `ergebnisse/messungen/curated-final/`:
  Zhang/Hebig-Paket, Abschrift, Prüfsummen und Ergebnisse
- `daten/lindholmen/discovery.json`, `daten/lindholmen/acquisition.json`,
  `daten/lindholmen/preparation-exclusions.json`: Auswahl und Fehlschläge
- `ergebnisse/protokolle/`: Logs aller Läufe und Tests
- `daten/lindholmen/syntax-audit.json`, `ergebnisse/pipeline-trockenlauf/`:
  Syntaxprüfung und Trockenlauf der Pipeline
- `ergebnisse/messungen/enhanced/`, `ergebnisse/messungen/curated-enhanced/`:
  Läufe nach den Erweiterungen

## Übereinstimmung pro Projekt

| Projekt | Java-Dateien | zugeordnete Knoten | Referenzkanten | F1 eigener vorher | F1 eigener korrigiert | F1 javalang | F1 java2plantuml |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| [qingyu1229/hhxxttxs](https://github.com/qingyu1229/hhxxttxs/tree/fc72e129a8142ff5b221e6902926b4bb3b5b3404) | 58 | 3 | 3 | 0,800 | 0,800 | 0,800 | 0,500 |
| [greengie/PigRunGame](https://github.com/greengie/PigRunGame/tree/385315d553d498e3482f5ca3e4440c7078703f86) | 9 | 9 | 7 | 1,000 | 1,000 | 1,000 | 0,833 |
| [brunotriggolabs/testepoo](https://github.com/brunotriggolabs/testepoo/tree/e9ad647daabfdacb1c6dde6fe31670b995a6f362) | 48 | 4 | 2 | 0,000 | 0,000 | 0,000 | 0,000 |
| [ConfuddledPenguin/Countdown](https://github.com/ConfuddledPenguin/Countdown/tree/47cee83485e24b291ae077dc7f4d769ac919e483) | 16 | 18 | 22 | 0,978 | 0,978 | 0,978 | 1,000 |
| [shadeven/cerebrumehr](https://github.com/shadeven/cerebrumehr/tree/02dab5a8185d5db2c9128aa0cd2c908d09cc64f9) | 507 | 84 | 96 | 0,000 | 0,000 | 0,000 | 0,000 |
| [cjurden/calc](https://github.com/cjurden/calc/tree/5fe187148feadb86aecf68219830d83ff6ba824e) | 5 | 9 | 2 | 1,000 | 1,000 | 1,000 | 1,000 |
| [SofiaReis/mfes-green-way](https://github.com/SofiaReis/mfes-green-way/tree/8558ac8bda63a77d1faea8531daf7e122f6fe89e) | 20 | 9 | 6 | 1,000 | 1,000 | 1,000 | 1,000 |
| [zenki2001cn/Erengine](https://github.com/zenki2001cn/Erengine/tree/f5e38a62d437b4cfde72efe9582db316c57709cc) | 588 | 6 | 4 | 0,750 | 0,667 | 0,667 | 0,667 |
| [juli1/rdalte](https://github.com/juli1/rdalte/tree/79090e3ae766c162c1dff65432fd52612e704de6) | 653 | 30 | 41 | 0,473 | 0,426 | 0,426 | 0,473 |
| [lorandszakacs/UPT-Projects](https://github.com/lorandszakacs/UPT-Projects/tree/9398bc0c81a225d10492a94bf2b436fe4f1abd48) | 240 | 7 | 2 | 0,333 | 0,250 | 0,250 | 0,400 |
| [sfotiadis/SEMonitor](https://github.com/sfotiadis/SEMonitor/tree/bff188fb74b3c1cc4351c1826fb2da1421fe45b9) | 12 | 10 | 5 | 0,769 | 0,769 | 0,769 | 0,545 |
| [adichad/lucene-new](https://github.com/adichad/lucene-new/tree/ddfd6f2b12c34d97e70b1a92de69d138ee1b666d) | 696 | 28 | 32 | 0,316 | 0,339 | 0,339 | 0,250 |
| [hodiqual/projet2015](https://github.com/hodiqual/projet2015/tree/95f605e54b6435c75d211f4c41d4d7ab249c9d7f) | 68 | 49 | 35 | 0,873 | 0,880 | 0,880 | 0,788 |
| [21268879/University](https://github.com/21268879/University/tree/6d8fbefd1f7e08823a2a40f7305569af8d5ff365) | 6 | 6 | 2 | 0,800 | 0,800 | 0,800 | 1,000 |
| [l7ol2aGol7z/To-The-Skies](https://github.com/l7ol2aGol7z/To-The-Skies/tree/d5df0d46a7a04f268179fb1f1833dcf7e0d6441a) | 12 | 12 | 19 | 1,000 | 1,000 | 1,000 | 0,848 |
| [KourdacheHoussam/UMLRefactoringTP3](https://github.com/KourdacheHoussam/UMLRefactoringTP3/tree/130edb7ad533207c0c5207b8eaacfa6bc18ec246) | 30 | 5 | 1 | 1,000 | 1,000 | 1,000 | 1,000 |
| [Neseek77/gwt-ent](https://github.com/Neseek77/gwt-ent/tree/c623f538e192b0e63793c20042bf859c73237e61) | 411 | 9 | 12 | 0,267 | 0,375 | 0,375 | 0,267 |
| [rewiko/LocateWind](https://github.com/rewiko/LocateWind/tree/4c7b7140088ee27979a1fba3dfa7f426ffd31f83) | 11 | 9 | 4 | 1,000 | 1,000 | 1,000 | 0,857 |
| [rtyanas/MyPics](https://github.com/rtyanas/MyPics/tree/a88c0dbb0ac87f74245c158fe4ebaa7e1f5e8567) | 11 | 12 | 2 | 0,500 | 0,500 | 0,500 | 0,500 |
| [LipliStyle/Liplis-Android](https://github.com/LipliStyle/Liplis-Android/tree/b3c27c53ad7faa206f6aabddcd4a32fc4dc6b92c) | 93 | 24 | 17 | 0,970 | 0,970 | 0,970 | 0,867 |
| [xyzker/Survey](https://github.com/xyzker/Survey/tree/cecebc67a75985121eb0fe45d90312fc501fd0f1) | 60 | 4 | 3 | 1,000 | 1,000 | 1,000 | 1,000 |
| [UbiCompForAll/UbiComposer](https://github.com/UbiCompForAll/UbiComposer/tree/eb2dfc62fed779f0a981a60f2465dc5e56b867f1) | 154 | 21 | 12 | 0,621 | 0,621 | 0,621 | 0,720 |
| [Simondin/ModelCombinationTree](https://github.com/Simondin/ModelCombinationTree/tree/43623cf9ee97b65b355a1a4edb04c84bde0e755d) | 35 | 18 | 26 | 1,000 | 1,000 | 1,000 | 0,667 |
| [jainebri/Super-Simple-Stocks](https://github.com/jainebri/Super-Simple-Stocks/tree/fef3b126e4b384e71e2662f0be3d07a8c2dd4b7c) | 14 | 12 | 11 | 0,952 | 0,957 | 0,957 | 0,842 |
| [Abdielja/AsiDriver](https://github.com/Abdielja/AsiDriver/tree/ed09f0573e98f7fc7078ed40d1c6fc001865f139) | 10 | 9 | 4 | 0,667 | 0,667 | 0,667 | 0,667 |
| [BGCX262/zyw-bank-management-svn-to-git](https://github.com/BGCX262/zyw-bank-management-svn-to-git/tree/c24ac18259d08c06022e1ca0adb2fc649acb93f1) | 39 | 7 | 6 | 0,923 | 0,923 | 0,923 | 1,000 |
| [dearsalisa/HappyWhale](https://github.com/dearsalisa/HappyWhale/tree/2b4fe24e2e71aada6d7afb09a793c3c8d3020ab6) | 6 | 4 | 4 | 1,000 | 1,000 | 1,000 | 0,667 |
| [aheizenreder/pac-ressys](https://github.com/aheizenreder/pac-ressys/tree/78468dc1a2cab23c996359535614da660a26f25b) | 67 | 5 | 4 | 0,857 | 0,857 | 0,857 | 0,857 |
| [TristanFAURE/pickerExplorer](https://github.com/TristanFAURE/pickerExplorer/tree/6145e466f1aa6065761fa3ea8e95c5d352fde002) | 85 | 37 | 7 | 0,368 | 0,359 | 0,359 | 0,378 |
| [CMCDelhiQuasar/Quasar-3-June](https://github.com/CMCDelhiQuasar/Quasar-3-June/tree/e0be833b1f20db5798111e67b40157875e262338) | 76 | 10 | 8 | 0,941 | 0,941 | 0,941 | 0,941 |
