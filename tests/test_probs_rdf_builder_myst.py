import pytest

from rdflib import Graph, Namespace, Literal
from rdflib.namespace import RDF, RDFS
from sphinx_probs_rdf.directives import PROBS, PROBS_RECIPE

SYS = Namespace("http://example.org/system/")


@pytest.mark.sphinx(
    'probs_rdf', testroot='myst',
    confoverrides={'probs_rdf_system_prefix': str(SYS)})
def test_probs_rdf_builder(app, status, warning):
    app.builder.build_all()

    # assert "build succeeded" in status.getvalue()
    warnings = warning.getvalue().strip()
    assert warnings == ""

    g = Graph()
    g.parse(app.outdir / 'output.ttl', format='ttl')
    print((app.outdir / 'output.ttl').read_text())

    # All processes should give the same result, in different ways
    for P in [SYS.P1, SYS.P2, SYS.P3]:
        assert (P, RDF.type, PROBS.Process) in g
        assert (P, PROBS.consumes, SYS.Apples) in g
        assert (P, PROBS.consumes, SYS.Blackberries) in g
        assert (P, PROBS.produces, SYS.Crumble) in g

        # Check the quantified recipes
        recipe = g.value(P, PROBS_RECIPE.hasRecipe)
        print(recipe)
        produces_items = g.objects(recipe, PROBS.produces)
        consumes_items = g.objects(recipe, PROBS.consumes)
        produces = {(g.value(item, PROBS_RECIPE.object), float(g.value(item, PROBS_RECIPE.quantity)))
                    for item in produces_items}
        consumes = {(g.value(item, PROBS_RECIPE.object), float(g.value(item, PROBS_RECIPE.quantity)))
                    for item in consumes_items}
        assert consumes == {(SYS.Apples, 0.7), (SYS.Blackberries, 0.3)}
        assert produces == {(SYS.Crumble, 1.0)}


@pytest.mark.sphinx(
    'html', testroot='myst',
    confoverrides={'probs_rdf_system_prefix': str(SYS)})
def test_recipe_output(app, status, warning):
    app.builder.build_all()
    content = (app.outdir / "index.html").read_text()
    print(content)

    assert """
<p>Consumes: </p>
<table class="colwidths-auto docutils align-default">
<thead>
<tr class="row-odd"><th class="head"><code class="docutils literal notranslate"><span class="pre">Object</span></code></th>
<th class="head"><code class="docutils literal notranslate"><span class="pre">Amount</span></code></th>
</tr>
</thead>
<tbody>
<tr class="row-even"><td><p><a class="reference internal" href="#object-Apples" title="object-Apples"><span>Apples</span></a></p></td>
<td><code class="docutils literal notranslate"><span class="pre">0.7</span> <span class="pre">kg</span></code></td>
</tr>
<tr class="row-odd"><td><p><a class="reference internal" href="#object-Blackberries" title="object-Blackberries"><span>Blackberries</span></a></p></td>
<td><code class="docutils literal notranslate"><span class="pre">0.3</span> <span class="pre">kg</span></code></td>
</tr>
</tbody>
</table>""" in content
