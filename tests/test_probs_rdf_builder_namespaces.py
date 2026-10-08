"""Per-file namespaces, placeholders and ``rdfs:isDefinedBy`` on the Sphinx path, and
that the standalone loader reads the same files to the same identifiers."""

import re

import pytest
from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS

from sphinx_probs_rdf.directives import PROBS
from sphinx_probs_rdf.loader import parse_system_definitions

SYS = Namespace("http://example.org/system/")
FRAG = Namespace("http://example.org/fragment/")
CONF = {
    "probs_rdf_system_prefix": str(SYS),
    "probs_rdf_extra_prefixes": {"base": str(SYS), "frag": str(FRAG)},
}


def _graph(app) -> Graph:
    app.builder.build_all()
    g = Graph()
    g.parse(app.outdir / "output.ttl", format="ttl")
    return g


@pytest.mark.sphinx("probs_rdf", testroot="namespaces", confoverrides=CONF)
def test_an_included_fragment_keeps_its_own_namespace(app, status, warning):
    g = _graph(app)
    assert warning.getvalue().strip() == ""
    assert (FRAG.Slab, RDF.type, PROBS.Object) in g
    assert (FRAG.Cast, PROBS.consumes, SYS.Steel) in g
    assert (FRAG.Cast, PROBS.produces, FRAG.Slab) in g
    # Back in the including page, bare names are the project's again.
    assert (SYS.AfterTheInclude, RDF.type, PROBS.Object) in g
    assert (SYS.Cast, RDF.type, PROBS.Process) in g


@pytest.mark.sphinx("probs_rdf", testroot="namespaces", confoverrides=CONF)
def test_every_definition_states_its_namespace(app, status, warning):
    g = _graph(app)
    assert (FRAG.Cast, RDFS.isDefinedBy, URIRef(str(FRAG))) in g
    assert (FRAG.Slab, RDFS.isDefinedBy, URIRef(str(FRAG))) in g
    assert (SYS.Cast, RDFS.isDefinedBy, URIRef(str(SYS))) in g


@pytest.mark.sphinx("probs_rdf", testroot="namespaces", confoverrides=CONF)
def test_a_placeholder_is_a_blank_node(app, status, warning):
    g = _graph(app)
    consumed = list(g.objects(SYS.Sale, PROBS.consumes))
    assert len(consumed) == 1 and isinstance(consumed[0], BNode)


@pytest.mark.sphinx("html", testroot="namespaces", confoverrides=CONF)
def test_a_placeholder_is_shown_by_its_label(app, status, warning):
    app.builder.build_all()
    html = (app.outdir / "index.html").read_text()
    assert "<em>_:HotBand</em>" in html


@pytest.mark.sphinx("probs_rdf", testroot="namespaces", confoverrides=CONF)
def test_a_basis_never_takes_a_file_s_namespace(app, status, warning):
    g = _graph(app)
    assert (FRAG.Slab, PROBS.objectMetric, SYS.mass) in g


@pytest.mark.sphinx("html", testroot="namespaces", confoverrides=CONF)
def test_a_qualified_reference_names_exactly_one_definition(app, status, warning):
    app.builder.build_all()
    assert "more than one target" not in warning.getvalue()
    html = (app.outdir / "index.html").read_text()
    assert html.count('class="reference internal"') >= 2


@pytest.mark.sphinx("probs_rdf", testroot="namespaces", confoverrides=CONF)
def test_the_loader_reads_the_same_identifiers(app, status, warning):
    g = _graph(app)
    system = parse_system_definitions(
        [app.srcdir / "index.md", app.srcdir / "_fragments" / "casting.md"],
        prefixes={"": str(SYS), **CONF["probs_rdf_extra_prefixes"]},
        validate=False,
    )
    rdf_objects = {str(s) for s in g.subjects(RDF.type, PROBS.Object)}
    assert set(system.objects) == rdf_objects
    markets = {o + "_Market" for o in system.objects}
    rdf_processes = {str(s) for s in g.subjects(RDF.type, PROBS.Process)} - markets
    assert set(system.processes) == rdf_processes
    for name, definition in [*system.objects.items(), *system.processes.items()]:
        assert {str(o) for o in g.objects(URIRef(name), RDFS.isDefinedBy)} == {
            definition.namespace
        }


@pytest.mark.sphinx("probs_rdf", testroot="namespaces", confoverrides=CONF)
def test_one_way_trade_is_recorded_as_traded_without_an_error(app, status, warning):
    g = _graph(app)
    assert "fully traded" not in warning.getvalue()
    assert (SYS.Steel, PROBS.objectIsTraded, Literal(True)) in g


@pytest.mark.sphinx("html", testroot="namespaces", confoverrides=CONF)
def test_a_recipe_amount_is_shown_as_written(app, status, warning):
    app.builder.build_all()
    html = (app.outdir / "index.html").read_text()
    text = " ".join(re.sub(r"<[^>]+>", " ", html).replace("&#160;", " ").split())
    assert "_:HotBand 1 kg" in text
    assert "quantitykind" not in text
