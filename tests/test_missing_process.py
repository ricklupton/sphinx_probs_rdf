import pytest

from rdflib import Graph, Namespace, Literal
from rdflib.namespace import RDF, RDFS
from sphinx_probs_rdf.directives import PROBS

SYS = Namespace("http://example.org/system/")

@pytest.mark.sphinx(
    'probs_rdf', testroot='missing',
    confoverrides={'probs_rdf_system_prefix': str(SYS)})
def test_builder_reports_warning_for_missing_process(app, status, warning):
    app.builder.build_all()

    assert "build succeeded" not in status.getvalue()
    warnings = warning.getvalue().strip()
    assert 'ERROR: Requested child "http://example.org/system/Missing" of "http://example.org/system/ErrorMissingProcess" is not a Process' in warnings
