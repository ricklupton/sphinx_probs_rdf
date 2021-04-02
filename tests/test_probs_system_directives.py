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

    assert """<div class="toggle process nested-0 system admonition">
<p class="admonition-title" id="process-P1"><em>Process: </em><code class="sig-name descname">P1</code><em> / Making crumble</em></p>
<p><p>Consumes: Apples Blackberries</p>
<p>Produces: Crumble</p>
</p>
</div>""" in content
