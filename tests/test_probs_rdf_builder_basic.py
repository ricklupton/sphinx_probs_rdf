import pytest

from rdflib import Graph, Namespace, Literal
from rdflib.namespace import RDF, RDFS
from sphinx_probs_rdf.directives import PROBS

SYS = Namespace("http://example.org/system/")

@pytest.mark.sphinx(
    'probs_rdf', testroot='basic',
    confoverrides={'probs_rdf_system_prefix': str(SYS)})
def test_probs_rdf_builder(app, status, warning):
    app.builder.build_all()

    # assert "build succeeded" in status.getvalue()
    warnings = warning.getvalue().strip()
    assert warnings == ""

    g = Graph()
    g.parse(app.outdir / 'output.ttl', format='ttl')
    print((app.outdir / 'output.ttl').read_text())

    assert (SYS.P1, RDF.type, PROBS.Process) in g
    assert (SYS.P1, RDFS.label, Literal("Making crumble")) in g
    assert (SYS.P1, PROBS.consumes, SYS.Apples) in g
    assert (SYS.P1, PROBS.consumes, SYS.Blackberries) in g
    assert (SYS.P1, PROBS.produces, SYS.Crumble) in g

    # Composition
    assert (SYS.ParentOfP1P2, PROBS.processComposedOf, SYS.P1) in g
    assert (SYS.ParentOfP1P2, PROBS.processComposedOf, SYS.P2) in g

    assert (SYS.AnotherParentOfP1P2, PROBS.processComposedOf, SYS.P1) in g
    assert (SYS.AnotherParentOfP1P2, PROBS.processComposedOf, SYS.P2) in g

    # Object is a reference object
    assert (SYS.Obj1, RDF.type, PROBS.Object) in g
    assert (SYS.Obj1, RDF.type, PROBS.ReferenceObject) in g
