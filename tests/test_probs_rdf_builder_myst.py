import pytest

from rdflib import Graph, Namespace, Literal
from rdflib.namespace import RDF, RDFS
from sphinx_probs_rdf.directives import PROBS, PROBS_RECIPE, QUANTITYKIND

SYS = Namespace("http://example.org/system/")


def get_recipe_items(g, recipe, relation):
    """relation is PROBS.produces or PROBS.consumes"""
    items = g.objects(recipe, relation)
    values = {
        (
            g.value(item, PROBS_RECIPE.object),
            g.value(item, PROBS_RECIPE.metric),
            float(g.value(item, PROBS_RECIPE.quantity))
        )
        for item in items
    }
    return values


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
        produces = get_recipe_items(g, recipe, PROBS_RECIPE.produces)
        consumes = get_recipe_items(g, recipe, PROBS_RECIPE.consumes)
        assert consumes == {
            (SYS.Apples, QUANTITYKIND.Mass, 0.7),
            (SYS.Blackberries, QUANTITYKIND.Mass, 0.3)
        }
        assert produces == {
            (SYS.Crumble, QUANTITYKIND.Mass, 1.0)
        }


@pytest.mark.sphinx(
    'probs_rdf', testroot='myst-mixed-units',
    confoverrides={'probs_rdf_system_prefix': str(SYS)})
def test_probs_rdf_builder_mixed_units(app, status, warning):
    app.builder.build_all()

    # assert "build succeeded" in status.getvalue()
    warnings = warning.getvalue().strip()
    assert warnings == ""

    g = Graph()
    g.parse(app.outdir / 'output.ttl', format='ttl')
    print((app.outdir / 'output.ttl').read_text())

    # All processes should give the same result, in different ways
    for P in [SYS.P1, SYS.P2]:
        assert (P, RDF.type, PROBS.Process) in g
        assert (P, PROBS.consumes, SYS.Apples) in g
        assert (P, PROBS.consumes, SYS.Blackberries) in g
        assert (P, PROBS.produces, SYS.Crumble) in g

        # Check the quantified recipes
        recipe = g.value(P, PROBS_RECIPE.hasRecipe)
        print(recipe)
        produces = get_recipe_items(g, recipe, PROBS_RECIPE.produces)
        consumes = get_recipe_items(g, recipe, PROBS_RECIPE.consumes)
        assert consumes == {
            (SYS.Apples, QUANTITYKIND.Mass, 1.0),
            (SYS.Blackberries, QUANTITYKIND.Mass, 0.3)
        }
        assert produces == {
            (SYS.Crumble, QUANTITYKIND.Dimensionless, 1.0)
        }


@pytest.mark.xfail(reason="need to fix display of units in recipes")
@pytest.mark.sphinx(
    'html', testroot='myst',
    confoverrides={'probs_rdf_system_prefix': str(SYS)})
def test_recipe_output(app, status, warning):
    app.builder.build_all()
    content = (app.outdir / "index.html").read_text()
    print(content)

    assert """

<tr class="row-even"><td><p><a class="reference internal" href="#object-Apples" title="object-Apples"><span>Apples</span></a></p></td>
<td><code class="docutils literal notranslate"><span class="pre">0.7</span> <span class="pre">kg</span></code></td>
</tr>
<tr class="row-odd"><td><p><a class="reference internal" href="#object-Blackberries" title="object-Blackberries"><span>Blackberries</span></a></p></td>
<td><code class="docutils literal notranslate"><span class="pre">0.3</span> <span class="pre">kg</span></code></td>
</tr>""" in content
