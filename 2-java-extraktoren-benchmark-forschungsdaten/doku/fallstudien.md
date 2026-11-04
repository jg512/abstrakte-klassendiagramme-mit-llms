# Fallstudien: RaiseMeUp, NeurophChanges, PatrickFromTheMOOC

Am 05. und 06.10.2026 wurden die Ergebnisse für drei Projekte der
Zhang/Hebig-Suite einzeln durchgesehen. Es sind die drei Projekte, die sich
kompilieren lassen, auf denen also auch die Bytecode-Werkzeuge gelaufen sind.
Die Werkzeuge wurden dafür nicht erneut ausgeführt. Grundlage waren die
vorhandenen Ausgaben, die Abschrift in `daten/zhang-hebig/reference.json`, die
Vergleichstabellen der Autoren und der Quelltext.

Die Frage war, ob fehlende Kanten an den Werkzeugen liegen oder daran, dass das
Referenzdiagramm vom Code abweicht.

## RaiseMeUp

Die Referenz enthält 17 Klassen und 22 Beziehungen (nach Normalisierung). Alle
Werkzeuge, die die Struktur auslesen, finden dieselben 12 Klassen. Es fehlen Dog,
Cat, Fish, Penguin und ItemDecorator. Gefundene Kanten: eigener Extraktor,
javalang und plantuml-generator je 8, jdeps 9, java2plantuml und juanmf je 6,
genuml 0.

Geprüft wurden dafür `daten/zhang-hebig/reference.json`,
`comparisons/2_RaiseMeUp.xlsx` (Spalten Real Abstraction, Disagreements,
Inaccuracies), die 12 ausgewählten `.java`-Dateien aus Commit `f3796c5`,
`UmlTranslator.writeAssociations`, `benchmark.py` (`jl_graph` wertet nur Felder
aus), `curated_tools_benchmark.py` (`run_jdeps` verwirft Selbstkanten und kennt
keine Vererbung) und die PlantUML-Ausgaben unter `ergebnisse/diagramme/RaiseMeUp/`.

Gründe für die fehlenden Klassen und Kanten:

- Die Klassen Dog, Cat, Fish und Penguin gibt es im Code nicht. Die Tierart wird
  über `Pet.type` und die Felder `Food.valuedog/valuecat/valuefish/valuepenguin`
  abgebildet.
- ItemDecorator ist im Code als `Slot` mit `LeftUpgradeSlot` und
  `RightUpgradeSlot` umgesetzt (`view/decorator/`). Diese Dateien gehörten nicht
  zu den 12 Eingabedateien.
- Die Kante `DAO–DAO` steht im Diagramm für das Singleton `instance`. Im Code gibt
  es stattdessen fünf Maps, die als zusätzliche Kanten DAO–User/Pet/Food/Upgrade/Job
  gezählt werden.
- `Pet.owner` ist ein `int`, und `User` hat keine Liste von Pets.
- `RaiseMeUp.java` verwendet weder `Item` noch `ItemVisitor`.
- `Pet–PetBuilder` und `User–UserBuilder` sind im Code nur die Rückgabetypen von
  `createPet()` und `createUser()`.
- `PetObserver` hat kein Feld vom Typ Pet und ruft stattdessen
  `RaiseMeUp.getCurrentPet()` auf.
- `owneditems` und `ownedjobs` haben die Typen `Map<Item,Integer>` und
  `Map<Job,Integer>`. javalang und plantuml-generator lösen den Typparameter auf.
  java2plantuml vergleicht `type.asString()` mit dem genauen Klassennamen und
  findet deshalb nichts, juanmf zeichnet ebenfalls keine Kante.
- genuml gibt grundsätzlich keine Beziehungen aus. Außerdem erkennt es
  `abstract Item {` ohne `class` nicht als Deklaration, und bei DAO schlug die
  Erzeugung fehl (`classes_ok` 157, `classes_failed` 1).
- Die Umbenennung von Control in RaiseMeUp ist in `reference.json` als Alias
  erfasst und erklärt keine fehlende Kante.

Von den 14 Kanten, die ein Extraktor auf Basis von Feldern nicht findet, sind
zwei Rückgabetypen: `PetBuilder.createPet` (Zeile 44 bis 45) und
`UserBuilder.createUser` (Zeile 38 bis 39). Methodenabhängigkeiten waren in
diesem Lauf nicht eingeschaltet (`include_method_dependencies` in
`graph_builder.py`). Die übrigen zwölf Kanten sind im Code anders umgesetzt: die
vier Tierarten als `int` bzw. `String`, ItemDecorator als `Slot` außerhalb der 12
Dateien, `Pet.owner` als `int`, das DAO-Singleton als fünf Maps, `PetObserver`
über `RaiseMeUp.getCurrentPet()` sowie Food, Item und ItemVisitor nur als
Methodenparameter.

Bei RaiseMeUp liegen die Abweichungen also größtenteils am Diagramm. Es
beschreibt einen Entwurf, der im Code anders umgesetzt wurde.

## NeurophChanges

Diagramm und Code stammen aus demselben Commit `848a3aa`. Das Diagramm hat 10
Klassen und 9 Beziehungen und zeigt keine Attribute oder Methoden.

- Der eigene Extraktor und javalang finden alle 9 Kanten und zusätzlich die Kante
  `NeuralNetwork–Neuron` (`NeurophArrayList<Neuron> inputNeurons`). Laut den
  Autoren ist diese Kante im Code vorhanden, wurde im Diagramm aber weggelassen.
- java2plantuml findet nur `TrainingSet–TrainingElement` nicht, weil das Feld den
  Typ `List<DataSetRow>` hat. Die Umbenennungen `TrainingSet`/`DataSet` und
  `TrainingElement`/`DataSetRow` sind als Aliase erfasst.
- plantuml-generator und juanmf brechen beim Laden der Klassen ab.
- jdeps findet alle 9 Kanten und dazu sechs Kanten aus der Verwendung von Klassen.

## PatrickFromTheMOOC

Das Diagramm stammt aus Commit `e2b99c7` (27.04.2015), der Code aus `5846aa2`
(15.05.2015).

- Der eigene Extraktor, javalang und plantuml-generator finden alle 8 Kanten,
  ohne zusätzliche Kanten im Modellumfang.
- java2plantuml und juanmf finden die vier Felder vom Typ `LinkedList<…>` nicht,
  aber `Review.member` und die beiden Vererbungen.
- jdeps gibt `Book extends Item` und `Film extends Item` als normale Kanten aus und
  findet zusätzlich `SocialNetwork–Film`, `SocialNetwork–Book` und `Item–Member`
  über Methoden.
- Laut den Autoren wurde das Diagramm nicht aus dem Code erzeugt. Später
  hinzugekommen ist nur der Wert `valeurinitialekarma`.

## Folgerungen

Bei den beiden kleineren Projekten finden die Extraktoren auf Basis von Feldern
fast alle Kanten aus dem Diagramm. Die übrigen Abweichungen kommen durch
Generics, eine im Diagramm weggelassene Kante, zusätzliche Kanten von jdeps und
abgebrochene Bytecode-Werkzeuge zustande. Bei RaiseMeUp liegt das Problem
hauptsächlich am Diagramm.

Ein Referenzdiagramm aus einem Repo ist also nicht unbedingt ein guter Maßstab.
Bevor ein vom LLM erzeugtes Diagramm mit einer solchen Referenz verglichen wird,
sollte geprüft werden, wie stark Referenz und Code voneinander abweichen.
