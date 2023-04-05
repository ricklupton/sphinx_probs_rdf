import pytest

from rdflib import Graph, Namespace, Literal
from rdflib.namespace import RDF, RDFS
from sphinx_probs_rdf.directives import PROBS, PROBS_RECIPE, QUANTITYKIND

SYS = Namespace("http://example.org/system/")
PREFIX = Namespace("http://example.org/prefix/")


@pytest.mark.sphinx(
    'probs_rdf', testroot='prefixes',
    confoverrides={
        'probs_rdf_system_prefix': str(SYS),
        'probs_rdf_extra_prefixes': {"prefix": str(PREFIX)},
    })
def test_probs_rdf_builder(app, status, warning):
    app.builder.build_all()

    # assert "build succeeded" in status.getvalue()
    warnings = warning.getvalue().strip()
    assert warnings == ""

    g = Graph()
    g.parse(app.outdir / 'output.ttl', format='ttl')
    print((app.outdir / 'output.ttl').read_text())

    assert (SYS.Apples, RDF.type, PROBS.Object) in g
    assert (SYS.Blackberries, RDF.type, PROBS.Object) in g
    assert (PREFIX.Crumble, RDF.type, PROBS.Object) in g

    for P in [SYS.P1, PREFIX.P2]:
        assert (P, RDF.type, PROBS.Process) in g
        assert (P, PROBS.consumes, SYS.Apples) in g
        assert (P, PROBS.consumes, SYS.Blackberries) in g
        assert (P, PROBS.produces, PREFIX.Crumble) in g

