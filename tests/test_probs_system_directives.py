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

    assert """<div class="toggle process nested-1 system admonition">
<p class="admonition-title" id="process-P1"><em>Process: </em><code class="sig-name descname">P1</code><em> / Making crumble</em></p>""" in content

    assert """
<p>Parent: <a class="reference internal" href="#process-ParentOfP1P2" title="process-ParentOfP1P2"><span>ParentOfP1P2</span></a></p>""" in content
