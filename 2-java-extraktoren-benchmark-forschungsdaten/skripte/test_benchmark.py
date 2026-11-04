from pathlib import Path

from benchmark import reference, puml, metrics, jl_graph


def test_uml2_relations_and_typed_properties_are_deduplicated(tmp_path):
    p=tmp_path/'model.uml'
    p.write_text('''<uml:Model xmlns:uml="http://www.eclipse.org/uml2/5.0.0/UML" xmlns:xmi="http://www.omg.org/XMI">
      <packagedElement xmi:type="uml:Class" xmi:id="a" name="A">
        <ownedAttribute xmi:id="ab" type="b" association="assoc"/>
        <generalization xmi:id="g" general="b"/>
        <interfaceRealization xmi:id="r" contract="i"/>
      </packagedElement>
      <packagedElement xmi:type="uml:Class" xmi:id="b" name="B"/>
      <packagedElement xmi:type="uml:Interface" xmi:id="i" name="I"/>
      <packagedElement xmi:type="uml:Association" xmi:id="assoc" memberEnd="ab ba">
        <ownedEnd xmi:id="ba" type="a"/>
      </packagedElement>
    </uml:Model>''')
    g=reference(p)
    assert set(g['nodes'])=={'a','b','i'}
    assert set(g['edges'])=={('a','b','association'),('a','b','inheritance'),('a','i','realization')}


def test_uml1_ids_and_association_ends(tmp_path):
    p=tmp_path/'model.xmi'
    p.write_text('''<XMI xmlns:UML="http://schema.omg.org/spec/UML/1.3">
      <UML:Class xmi.id="a" name="A"/><UML:Class xmi.id="b" name="B"/>
      <UML:Generalization xmi.id="g" child="b" parent="a"/>
      <UML:Association xmi.id="assoc"><UML:Association.connection>
        <UML:AssociationEnd xmi.id="e1" type="b"/><UML:AssociationEnd xmi.id="e2" type="a"/>
      </UML:Association.connection></UML:Association>
    </XMI>''')
    assert set(reference(p)['edges'])=={('b','a','inheritance'),('a','b','association')}


def test_duplicate_simple_names_keep_distinct_model_ids(tmp_path):
    p=tmp_path/'m.uml'
    p.write_text('''<root xmlns:xmi="http://www.omg.org/XMI">
      <e xmi:type="uml:Class" xmi:id="x" name="Item"/>
      <e xmi:type="uml:Class" xmi:id="y" name="Item"/>
    </root>''')
    assert len(reference(p)['nodes'])==2


def test_javalang_adapter_retains_nested_identity_and_self_reference(tmp_path):
    p=tmp_path/'A.java';p.write_text('package demo; class A { A next; class Inner {} }')
    r=jl_graph([p],tmp_path)
    assert set(r['nodes'])=={'demo.A','demo.A.Inner'}
    assert ('demo.A','demo.A','association') in r['edges']


def test_java2plantuml_dialect():
    r=puml('class Child{\n}\ninterface Parent{\n}\nChild ..|> Parent\nChild--"- member" Other\n')
    assert set(r['edges'])=={('Child','Parent','realization'),('Child','Other','association')}
    assert not r['unparsed_relation_lines']


def test_empty_failure_is_scored_not_dropped():
    r=metrics(set(),{('a','b','association')})
    assert (r['tp'],r['fp'],r['fn'],r['recall'],r['f1'])==(0,0,1,0.0,0.0)


def test_unresolved_reference_endpoint_is_reported(tmp_path):
    p=tmp_path/'model.uml';p.write_text('''<root xmlns:xmi="http://www.omg.org/XMI">
      <e xmi:type="uml:Class" xmi:id="a" name="A"><generalization general="missing"/></e>
    </root>''')
    r=reference(p)
    assert not r['edges']
    assert r['unresolved'][0]['target']=='missing'
