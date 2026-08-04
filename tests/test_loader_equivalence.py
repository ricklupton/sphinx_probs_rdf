"""For each MyST-based test root, the standalone loader's IR and the RDF graph the
Sphinx path builds from the *same* source file should agree on the set of objects,
processes, recipe connectivity and recipe quantities/metrics.

"""

from typing import Set, Tuple

import pytest
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF

from sphinx_probs_rdf.directives import PROBS, PROBS_RECIPE, parse_uri
from sphinx_probs_rdf.loader import parse_system_definitions
from sphinx_probs_rdf.units import DEFAULT_UNITS

SYS = Namespace("http://example.org/system/")
PREFIX = Namespace("http://example.org/prefix/")


#: rdflib's Turtle serializer writes doubles in a shortened form (e.g.
#: 0.30000000000000004 -> "3e-01"), so a value read back from `output.ttl` can differ
#: from the in-memory value by a tiny amount. Round both sides before comparing.
_QUANTITY_PLACES = 6


def _rdf_recipe_items(g: Graph, process_uri: URIRef, relation) -> Set[Tuple[URIRef, URIRef, float]]:
    recipe = g.value(process_uri, PROBS_RECIPE.hasRecipe)
    if recipe is None:
        return set()
    items = set()
    for item in g.objects(recipe, relation):
        items.add((
            g.value(item, PROBS_RECIPE.object),
            g.value(item, PROBS_RECIPE.metric),
            round(float(g.value(item, PROBS_RECIPE.quantity)), _QUANTITY_PLACES),
        ))
    return items


def _assert_equivalent(system, graph: Graph, config) -> None:
    units = DEFAULT_UNITS

    def uri(name: str) -> URIRef:
        return parse_uri(config, name)

    # Objects: same set of names, mapped through the same parse_uri the RDF path uses.
    rdf_objects = {s for s in graph.subjects(RDF.type, PROBS.Object)}
    assert rdf_objects == {uri(name) for name in system.objects}

    # Processes: the RDF graph additionally carries a synthetic "<Object>_Market"
    # process per object (see Object.define_graph) that has no counterpart in the
    # IR -- exclude those before comparing.
    market_uris = {URIRef(str(uri(name)) + "_Market") for name in system.objects}
    rdf_processes = {s for s in graph.subjects(RDF.type, PROBS.Process)} - market_uris
    assert rdf_processes == {uri(name) for name in system.processes}

    for name, process in system.processes.items():
        process_uri = uri(name)

        # Connectivity (PROBS.consumes/produces), regardless of amount.
        assert set(graph.objects(process_uri, PROBS.consumes)) == {
            uri(item.object_name) for item in process.consumes
        }
        assert set(graph.objects(process_uri, PROBS.produces)) == {
            uri(item.object_name) for item in process.produces
        }

        # Quantified recipe items: object, metric and quantity must all agree.
        for relation, items, rdf_relation in (
            ("consumes", process.consumes, PROBS_RECIPE.consumes),
            ("produces", process.produces, PROBS_RECIPE.produces),
        ):
            expected = {
                (
                    uri(item.object_name),
                    URIRef(item.basis(units)),
                    round(item.quantity(units), _QUANTITY_PLACES),
                )
                for item in items
                if item.amount is not None
            }
            assert _rdf_recipe_items(graph, process_uri, rdf_relation) == expected, (
                f"{name}.{relation}"
            )


@pytest.mark.sphinx(
    "probs_rdf", testroot="myst", confoverrides={"probs_rdf_system_prefix": str(SYS)}
)
def test_loader_matches_rdf_myst(app, status, warning):
    app.builder.build_all()
    assert warning.getvalue().strip() == ""

    graph = Graph()
    graph.parse(app.outdir / "output.ttl", format="ttl")

    system = parse_system_definitions(
        [app.srcdir / "index.md"], units=DEFAULT_UNITS, validate=False
    )
    _assert_equivalent(system, graph, app.config)


@pytest.mark.sphinx(
    "probs_rdf",
    testroot="myst-mixed-units",
    confoverrides={"probs_rdf_system_prefix": str(SYS)},
)
def test_loader_matches_rdf_myst_mixed_units(app, status, warning):
    app.builder.build_all()
    assert warning.getvalue().strip() == ""

    graph = Graph()
    graph.parse(app.outdir / "output.ttl", format="ttl")

    system = parse_system_definitions(
        [app.srcdir / "index.md"], units=DEFAULT_UNITS, validate=False
    )
    _assert_equivalent(system, graph, app.config)


@pytest.mark.sphinx(
    "probs_rdf",
    testroot="prefixes",
    confoverrides={
        "probs_rdf_system_prefix": str(SYS),
        "probs_rdf_extra_prefixes": {"prefix": str(PREFIX)},
    },
)
def test_loader_matches_rdf_prefixes(app, status, warning):
    app.builder.build_all()
    assert warning.getvalue().strip() == ""

    graph = Graph()
    graph.parse(app.outdir / "output.ttl", format="ttl")

    system = parse_system_definitions(
        [app.srcdir / "index.md"], units=DEFAULT_UNITS, validate=False
    )
    _assert_equivalent(system, graph, app.config)
