"""Linking a model out of a library of definitions (``sphinx_probs_rdf.linking``)."""

import pytest

from sphinx_probs_rdf.linking import (
    ALL,
    LinkError,
    ObjectOverride,
    ProcessSelection,
    RecipeSubstitution,
    link_model,
)
from sphinx_probs_rdf.loader import parse_markdown

US = "http://example.org/us/"
RECIPES = "http://example.org/us/mill-feed/recipes/"
ALLOCATED = "http://example.org/us/mill-feed/allocated/"
PREFIXES = {"": US, "us": US, "rec": RECIPES, "alloc": ALLOCATED}

#: A shared core with one hole, and two alternative readings of the mills, in nested
#: namespaces -- nesting is what a namespace selection must not be confused by.
LIBRARY = """
```{system:object} Steel
```

```{system:object} MillProduct
```

```{system:object} Unused
```

```{system:object} Semis
---
parent_object: Steel
---
```

```{system:object} HotBand
---
parent_object: MillProduct
traded: export
---
```

```{system:object} Sheet
```

```{system:object} Scrap
```

```{system:process} SheetSale
---
consumes: |
  _:HotBandForSale = 100 %
produces: |
  Sheet = 100 %
---
```

```{system:process} rec:HotStripMill
---
consumes: |
  us:Semis = 100 %
produces: |
  us:HotBand = 92 %
  us:Scrap = 8 %
---
```

```{system:process} alloc:HotStripMill
---
consumes: |
  us:Semis = 100 %
produces: |
  us:HotBand = 92 %
  us:Scrap = 8 %
---
```

```{system:process} alloc:HotBandDistribution
---
consumes: |
  us:HotBand = 100 %
produces: |
  alloc:HotBandForSale = 50 %
  us:Scrap = 50 %
---
```

```{system:object} alloc:HotBandForSale
---
parent_object: MillProduct
---
```
"""


@pytest.fixture
def library():
    return parse_markdown(LIBRARY, prefixes=PREFIXES)


RECIPES_MODEL = [
    ProcessSelection("us:"),
    ProcessSelection("rec:"),
    RecipeSubstitution(["us:SheetSale"], {"_:HotBandForSale": "us:HotBand"}),
]
ALLOCATED_MODEL = [
    ProcessSelection("us:"),
    ProcessSelection("alloc:"),
    RecipeSubstitution(["us:SheetSale"], {"_:HotBandForSale": "alloc:HotBandForSale"}),
    ObjectOverride("us:HotBand", can_export=False),
]


def test_a_linked_model_is_localised(library):
    model = link_model(library, RECIPES_MODEL)
    assert model.prefixes is None
    assert list(model.processes) == ["SheetSale", "HotStripMill"]
    assert list(model.objects) == [
        "Steel", "MillProduct", "Semis", "HotBand", "Sheet", "Scrap"
    ]
    sale = model.processes["SheetSale"]
    assert [i.object_name for i in sale.consumes] == ["HotBand"]
    mill = model.processes["HotStripMill"]
    assert [i.object_name for i in mill.produces] == ["HotBand", "Scrap"]


def test_declared_parents_come_in_with_their_members(library):
    model = link_model(library, RECIPES_MODEL)
    assert model.objects["Semis"].parent == "Steel"
    assert model.objects["HotBand"].parent == "MillProduct"
    # Declared, but neither referred to nor a parent of anything in the model.
    assert "Unused" not in model.objects


def test_an_undeclared_parent_is_an_error_with_prefixes():
    library = parse_markdown(
        """
```{system:object} Apples
---
parent_object: Fruit
---
```

```{system:process} Eat
---
consumes: |
  Apples = 1 kg
---
```
""",
        prefixes=PREFIXES,
    )
    with pytest.raises(LinkError, match="never declared; declare it"):
        link_model(library, [ProcessSelection("us:")])


def test_an_undeclared_parent_is_kept_when_identifiers_are_opaque():
    library = parse_markdown(
        """
```{system:object} Apples
---
parent_object: Fruit
---
```

```{system:process} Eat
---
consumes: |
  Apples = 1 kg
---
```
"""
    )
    assert link_model(library, [ProcessSelection(ALL)]).objects["Apples"].parent == "Fruit"


def test_the_other_alternative_links_with_its_own_wiring(library):
    model = link_model(library, ALLOCATED_MODEL)
    assert list(model.processes) == ["SheetSale", "HotStripMill", "HotBandDistribution"]
    assert [i.object_name for i in model.processes["SheetSale"].consumes] == [
        "HotBandForSale"
    ]
    assert model.objects["HotBand"].traded == (False, False)
    assert model.objects["HotBandForSale"].namespace == ALLOCATED


def test_a_namespace_selection_is_by_declaration_not_by_iri_prefix(library):
    # US is a string prefix of both alternatives' namespaces; selecting it must not
    # bring either in.
    only_core = [p for p in library.processes.values() if p.namespace == US]
    assert [p.local_name for p in only_core] == ["SheetSale"]
    with pytest.raises(LinkError, match="placeholders left open"):
        link_model(library, [ProcessSelection("us:")])


def test_selecting_both_alternatives_is_a_name_clash(library):
    with pytest.raises(LinkError, match="'HotStripMill'"):
        link_model(
            library,
            [ProcessSelection(ALL), RecipeSubstitution(
                ["us:SheetSale"], {"_:HotBandForSale": "us:HotBand"}
            )],
        )


def test_a_namespace_scope_must_be_written_as_one(library):
    with pytest.raises(LinkError, match="pass a list"):
        link_model(library, [ProcessSelection("us")])


def test_an_empty_namespace_hints_at_the_trailing_separator():
    library = parse_markdown(
        "```{system:process} ns:P\n```\n", prefixes={"ns": "http://example.org/ns/"}
    )
    with pytest.raises(LinkError, match="did you mean <http://example.org/ns/>"):
        link_model(library, [ProcessSelection("<http://example.org/ns>")])


def test_an_open_placeholder_is_an_error(library):
    with pytest.raises(LinkError, match="us/SheetSale: _:HotBandForSale|SheetSale"):
        link_model(library, [ProcessSelection("us:"), ProcessSelection("rec:")])


def test_a_substitution_can_cover_a_namespace(library):
    model = link_model(
        library,
        [
            ProcessSelection("us:"),
            ProcessSelection("alloc:"),
            RecipeSubstitution("alloc:", {"us:Scrap": "us:Sheet"}),
            RecipeSubstitution(["us:SheetSale"], {"_:HotBandForSale": "us:HotBand"}),
        ],
    )
    for name in ("HotStripMill", "HotBandDistribution"):
        assert "Scrap" not in {i.object_name for i in model.processes[name].produces}
    # Scrap is no longer referred to, so it is not part of the model.
    assert "Scrap" not in model.objects


def test_a_substitution_that_matches_nothing_is_an_error(library):
    with pytest.raises(LinkError, match="refers to '_:Nothing'"):
        link_model(
            library,
            RECIPES_MODEL + [RecipeSubstitution(ALL, {"_:Nothing": "us:HotBand"})],
        )


def test_overlapping_substitutions_are_an_error(library):
    with pytest.raises(LinkError, match="give their scopes no overlap"):
        link_model(
            library,
            RECIPES_MODEL
            + [RecipeSubstitution(ALL, {"_:HotBandForSale": "us:Sheet"})],
        )


def test_a_listed_scope_must_be_selected(library):
    with pytest.raises(LinkError, match="does not select"):
        link_model(
            library,
            RECIPES_MODEL
            + [RecipeSubstitution(["alloc:HotBandDistribution"], {"us:Scrap": "us:Sheet"})],
        )


def test_an_override_must_name_an_object_of_the_model(library):
    with pytest.raises(LinkError, match="not an object of this model"):
        link_model(
            library,
            RECIPES_MODEL + [ObjectOverride("alloc:HotBandForSale", can_export=True)],
        )


def test_a_reference_to_an_undefined_object_is_an_error(library):
    with pytest.raises(LinkError, match="never defined"):
        link_model(
            library,
            [
                ProcessSelection("us:"),
                RecipeSubstitution(["us:SheetSale"], {"_:HotBandForSale": "us:Nowhere"}),
            ],
        )


def test_a_full_iri_definition_has_no_local_name_to_link_under():
    library = parse_markdown(
        "```{system:process} <http://example.org/P>\n```\n", prefixes=PREFIXES
    )
    with pytest.raises(LinkError, match="full IRI"):
        link_model(library, [ProcessSelection(["<http://example.org/P>"])])


def test_opaque_definitions_link_to_themselves():
    library = parse_markdown(
        """
```{system:object} Apples
```

```{system:process} Eat
---
consumes: |
  Apples = 1 kg
---
```
"""
    )
    model = link_model(library, [ProcessSelection(ALL)])
    assert list(model.processes) == ["Eat"]
    assert list(model.objects) == ["Apples"]
    assert link_model(library, [ProcessSelection(":")]).processes.keys() == {"Eat"}
