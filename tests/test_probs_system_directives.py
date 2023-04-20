import pytest

from sphinx_probs_rdf.directives import PROBS

SYS = "http://example.org/system/"


@pytest.mark.sphinx(
    'html', testroot='basic',
    confoverrides={'probs_rdf_system_prefix': str(SYS)})
def test_probs_rdf_builder(app, status, warning):
    app.builder.build_all()
    content = (app.outdir / "index.html").read_text()
    print(content)

    assert """<div class="system process toggle nested-1 admonition">
<p class="sig sig-object admonition-title" id="http-example.org-system-P1"><em>Process: </em><span class="sig-name descname">P1</span><span class="sig-prename descclassname"> / Making crumble</span></p>""" in content

    assert """
<p>Parents: <a class="reference internal" href="#http-example.org-system-ParentOfP1P2" title="http://example.org/system/ParentOfP1P2"><span>sys:ParentOfP1P2</span></a></p>""" in content
