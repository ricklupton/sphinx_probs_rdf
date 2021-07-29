import logging
from rdflib import Graph, Namespace
from rdflib.namespace import RDF
import pytest

from sphinx_probs_rdf.postprocess import postprocess_composed_of_children
from sphinx_probs_rdf.directives import PROBS

SYS = Namespace("http://ukfires.org/probs/system/")

def test_postprocess_composed_of_children():
    graph = Graph()
    graph.add((SYS.P1, RDF.type, PROBS.Process))
    graph.add((SYS.P1, PROBS.processComposedOf, SYS.P1a))
    graph.add((SYS.P1, PROBS.processComposedOf, SYS.P1b))
    graph.add((SYS.P2, PROBS.processComposedOfChildrenOf, SYS.P1))

    postprocess_composed_of_children(graph)

    assert set(graph.triples((SYS.P2, PROBS.processComposedOf, None))) == {
        (SYS.P2, PROBS.processComposedOf, SYS.P1a),
        (SYS.P2, PROBS.processComposedOf, SYS.P1b),
    }
    assert set(graph.triples((SYS.P2, PROBS.processComposedOfChildrenOf, None))) == set()
