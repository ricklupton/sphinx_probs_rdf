"""Post-processing operations on the RDF graph."""

from rdflib import Graph  # type: ignore
from rdflib.namespace import RDF  # type: ignore

from .directives import PROBS  # type: ignore

from sphinx.util import logging
logger = logging.getLogger(__name__)


def postprocess(graph: Graph):
    """Apply postprocessing steps to graph."""
    postprocess_composed_of_children(graph)


def postprocess_composed_of_children(graph: Graph):
    """Expand probs:processComposedOfChildrenOf relations."""

    # FIXME: this probably doesn't work properly if there are chains involved,
    # which would need to be sorted into a tree and expanded from the branches
    # backwards.

    for p, _, source in graph.triples((None, PROBS.processComposedOfChildrenOf, None)):
        if (source, RDF.type, PROBS.Process) not in graph:
            logger.error('Requested child "%s" of "%s" is not a Process', source, p)

        for child in graph.objects(source, PROBS.processComposedOf):
            graph.add((p, PROBS.processComposedOf, child))
        graph.remove((p, PROBS.processComposedOfChildrenOf, source))
