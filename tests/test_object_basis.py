"""``:basis:`` becomes ``probs:objectMetric`` in RDF.
"""

import pytest

from rdflib import Graph, Namespace
from sphinx_probs_rdf.directives import PROBS

SYS = Namespace("http://example.org/system/")
QUANTITYKIND = Namespace("http://qudt.org/vocab/quantitykind/")


@pytest.mark.sphinx(
    "probs_rdf",
    testroot="object-basis",
    confoverrides={
        "probs_rdf_system_prefix": str(SYS),
        "probs_rdf_extra_prefixes": {"quantitykind": str(QUANTITYKIND)},
    },
)
def test_basis_emits_object_metric(app, status, warning):
    app.builder.build_all()
    assert warning.getvalue().strip() == ""

    g = Graph()
    g.parse(app.outdir / "output.ttl", format="ttl")

    assert (SYS.Electricity, PROBS.objectMetric, QUANTITYKIND.Energy) in g
    # An object with no :basis: gets no objectMetric triple at all.
    assert (SYS.Steel, PROBS.objectMetric, None) not in g
    # A bare (no-prefix) :basis: value with no probs_rdf_basis_prefix set falls back
    # to the system namespace, same as any other bare reference.
    assert (SYS.Wood, PROBS.objectMetric, SYS.mass) in g


BASIS = Namespace("http://example.org/basis/")


@pytest.mark.sphinx(
    "probs_rdf",
    testroot="object-basis",
    confoverrides={
        "probs_rdf_system_prefix": str(SYS),
        "probs_rdf_extra_prefixes": {"quantitykind": str(QUANTITYKIND)},
        "probs_rdf_basis_prefix": str(BASIS),
    },
)
def test_basis_prefix_config_used_for_bare_basis_values(app, status, warning):
    """A bare :basis: value defaults into probs_rdf_basis_prefix, not the system
    namespace, once a project sets one -- an explicit prefix (quantitykind:Energy)
    is unaffected either way."""
    app.builder.build_all()
    assert warning.getvalue().strip() == ""

    g = Graph()
    g.parse(app.outdir / "output.ttl", format="ttl")

    assert (SYS.Wood, PROBS.objectMetric, BASIS.mass) in g
    assert (SYS.Electricity, PROBS.objectMetric, QUANTITYKIND.Energy) in g
