[Deutsch](fallstudien.md) · **English**

# Case studies: RaiseMeUp, NeurophChanges, PatrickFromTheMOOC

When a tool does not find a line from the reference diagram, there can be two
reasons: the tool reads the code wrongly, or the diagram shows something that
is not in the code in that form. For three projects we checked this line by
line. The result up front: for RaiseMeUp, the project with the largest
reference diagram, most of the differences come from the diagram. The
[main README](../../README.en.md#glossary) explains the technical terms.

On 5 and 6 October 2026 the results for three projects of the Zhang/Hebig
suite were reviewed one by one. They are the three projects that can be
compiled, so the bytecode tools ran on them too. The tools were not run again
for this. The review was based on the existing outputs, the transcription in
`daten/zhang-hebig/reference.json`, the authors' comparison tables and the
source code.

The question was whether missing edges are the tools' fault or due to the
reference diagram differing from the code.

## RaiseMeUp

The reference contains 17 classes and 22 relationships (after normalisation).
All tools that read out the structure find the same 12 classes. Dog, Cat,
Fish, Penguin and ItemDecorator are missing. Edges found: our extractor,
javalang and plantuml-generator 8 each, jdeps 9, java2plantuml and juanmf 6
each, genuml 0.

For anyone who wants to check, these were the sources for this review (you do
not need them to follow the results below): `daten/zhang-hebig/reference.json`,
`comparisons/2_RaiseMeUp.xlsx` (columns Real Abstraction, Disagreements,
Inaccuracies), the 12 selected `.java` files from commit `f3796c5`,
`UmlTranslator.writeAssociations`, `benchmark.py` (`jl_graph` only looks at
fields), `curated_tools_benchmark.py` (`run_jdeps` discards self-edges and
knows nothing about inheritance) and the PlantUML outputs under
`ergebnisse/diagramme/RaiseMeUp/`.

Reasons for the missing classes and edges:

- The classes Dog, Cat, Fish and Penguin do not exist in the code. The kind of
  animal is represented by `Pet.type` and the fields
  `Food.valuedog/valuecat/valuefish/valuepenguin`. So the diagram shows four
  subclasses of pet, while the code only stores the kind of animal as a value
  in a field.
- ItemDecorator is implemented in the code as `Slot` with `LeftUpgradeSlot`
  and `RightUpgradeSlot` (`view/decorator/`). These files were not among the
  12 input files, because the tools only get the files in which a class from
  the diagram is declared.
- In the diagram, the edge `DAO–DAO` stands for the singleton `instance` (a
  singleton is a class of which there is only one single object, which the
  class manages itself). The code has five maps instead, which are counted as
  extra edges DAO–User/Pet/Food/Upgrade/Job.
- `Pet.owner` is an `int` (a whole number), and `User` has no list of pets.
- `RaiseMeUp.java` uses neither `Item` nor `ItemVisitor`.
- In the code, `Pet–PetBuilder` and `User–UserBuilder` are only the return
  types of `createPet()` and `createUser()`.
- `PetObserver` has no field of type Pet and calls `RaiseMeUp.getCurrentPet()`
  instead.
- `owneditems` and `ownedjobs` have the types `Map<Item,Integer>` and
  `Map<Job,Integer>`. javalang and plantuml-generator resolve the type
  parameter. java2plantuml compares `type.asString()` with the exact class
  name and so finds nothing; juanmf does not draw an edge either.
- genuml never outputs any relationships. It also does not recognise
  `abstract Item {` without `class` as a declaration, and for DAO the
  generation failed (`classes_ok` 157, `classes_failed` 1).
- The renaming of Control to RaiseMeUp is recorded in `reference.json` as an
  alias and does not explain any missing edge.

Of the 14 edges that an extractor working from fields does not find, two are
return types: `PetBuilder.createPet` (lines 44 to 45) and
`UserBuilder.createUser` (lines 38 to 39). Method dependencies were not
switched on in this run (`include_method_dependencies` in `graph_builder.py`).
The remaining twelve edges are implemented differently in the code: the four
kinds of animal as `int` or `String`, ItemDecorator as `Slot` outside the 12
files, `Pet.owner` as `int`, the DAO singleton as five maps, `PetObserver`
through `RaiseMeUp.getCurrentPet()`, and Food, Item and ItemVisitor only as
method parameters.

So for RaiseMeUp, most of the differences come from the diagram. It describes
a design that was implemented differently in the code.

## NeurophChanges

Diagram and code come from the same commit `848a3aa`. The diagram has 10
classes and 9 relationships and shows no attributes or methods.

- Our extractor and javalang find all 9 edges, plus the edge
  `NeuralNetwork–Neuron` (`NeurophArrayList<Neuron> inputNeurons`). According
  to the authors, this edge exists in the code but was left out of the
  diagram.
- java2plantuml misses only `TrainingSet–TrainingElement`, because the field
  has the type `List<DataSetRow>`. The renamings `TrainingSet`/`DataSet` and
  `TrainingElement`/`DataSetRow` are recorded as aliases.
- plantuml-generator and juanmf stop while loading the classes.
- jdeps finds all 9 edges, plus six edges from the use of classes.

## PatrickFromTheMOOC

The diagram comes from commit `e2b99c7` (27 April 2015), the code from
`5846aa2` (15 May 2015).

- Our extractor, javalang and plantuml-generator find all 8 edges, with no
  extra edges within the model scope.
- java2plantuml and juanmf miss the four fields of type `LinkedList<…>` that
  lie within the model scope, but
  find `Review.member` and the two inheritances.
- jdeps outputs `Book extends Item` and `Film extends Item` as ordinary edges,
  and also finds `SocialNetwork–Film`, `SocialNetwork–Book` and `Item–Member`
  through methods.
- According to the authors, the diagram was not generated from the code. The
  only later addition is the value `valeurinitialekarma`.

## Conclusions

For the two smaller projects, the extractors working from fields find almost
all edges in the diagram. The remaining differences come from generics, an
edge left out of the diagram, extra edges from jdeps, and bytecode tools that
stopped. For RaiseMeUp, the problem lies mainly with the diagram.

So a reference diagram taken from a repo is not necessarily a good yardstick.
Before a diagram produced by the LLM is compared with such a reference, we
should check how far reference and code differ from each other.
