import os.path
from typing import Any, Dict, List, Set, Tuple
from docutils.nodes import Node
from sphinx.application import Sphinx
from sphinx.builders import Builder
from sphinx.locale import __

from sphinx.util import logging
logger = logging.getLogger(__name__)


from .postprocess import postprocess


class ProbsSystemRDFBuilder(Builder):
    """
    Extracts RDF from system definitions
    """
    name = 'probs_rdf'
    epilog = __('System definitions written to '
                '%(outdir)s/output.ttl')

    def get_target_uri(self, docname: str, typ: str = None) -> str:
        return ''

    def get_outdated_docs(self) -> Set[str]:
        return self.env.found_docs

    def prepare_writing(self, docnames: Set[str]) -> None:
        return

    def write_doc(self, docname: str, doctree: Node) -> None:
        return

    def finish(self) -> None:
        env = self.app.builder.env
        filename = os.path.join(self.outdir, 'output.ttl')
        if hasattr(env, 'probs_graph'):
            graph = env.probs_graph
            postprocess(graph)
            with open(filename, 'wb') as f:
                graph.serialize(f, format="turtle")
        else:
            logger.warning('No graph found!')
