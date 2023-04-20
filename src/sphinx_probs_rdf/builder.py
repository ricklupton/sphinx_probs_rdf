import os.path
from typing import Set, cast

from docutils.nodes import Node
from sphinx.builders import Builder
from sphinx.locale import __
from sphinx.util import logging

from .postprocess import postprocess
from .directives import SystemDomain

logger = logging.getLogger(__name__)


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
        assert self.env
        return self.env.found_docs

    def prepare_writing(self, docnames: Set[str]) -> None:
        return

    def write_doc(self, docname: str, doctree: Node) -> None:
        return

    def finish(self) -> None:
        assert self.app.builder
        env = self.app.builder.env
        assert env is not None
        domain = cast(SystemDomain, env.get_domain("system"))
        filename = os.path.join(self.outdir, 'output.ttl')
        graph = domain.graph
        postprocess(graph)
        with open(filename, 'wb') as f:
            graph.serialize(f, format="turtle")
