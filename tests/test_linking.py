"""Linking a model out of a library of definitions (``sphinx_probs_rdf.linking``)."""

import pytest

from sphinx_probs_rdf.linking import ALL, LinkError, ProcessSelection, link_model
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
    ProcessSelection("us:", {"_:HotBandForSale": "us:HotBand"}),
    ProcessSelection("rec:"),
]
ALLOCATED_MODEL = [
    ProcessSelection("us:", {"_:HotBandForSale": "alloc:HotBandForSale"}),
    ProcessSelection("alloc:"),
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


PARENTS = """
```{system:object} Apples
---
parent_object: alloc:Fruit
---
```

```{system:process} alloc:Consumption
:become_parent: true
```

```{system:process} Eat
---
consumes: |
  Apples = 1 kg
---
```

```{end-sub-processes}
```
"""


@pytest.mark.parametrize("prefixes", [None, PREFIXES])
def test_parents_outside_the_model_are_kept_by_their_local_names(prefixes):
    library = parse_markdown(PARENTS.replace("alloc:", ""), prefixes=prefixes)
    model = link_model(library, [ProcessSelection(["Eat"])])
    # Fruit is never declared; Consumption is, but is not selected.
    assert model.objects["Apples"].parent == "Fruit"
    assert model.processes["Eat"].parent == "Consumption"
    assert "Fruit" not in model.objects
    assert "Consumption" not in model.processes


def test_a_parent_outside_the_model_that_clashes_is_kept_by_its_prefixed_name():
    library = parse_markdown(
        PARENTS
        + "```{system:object} Fruit\n```\n"
        + "```{system:process} Consumption\n---\n"
        + "consumes: |\n  Fruit = 1 kg\n---\n```\n",
        prefixes=PREFIXES,
    )
    model = link_model(library, [ProcessSelection("us:")])
    assert model.objects["Apples"].parent == "alloc:Fruit"
    assert model.processes["Eat"].parent == "alloc:Consumption"


def test_the_other_alternative_links_with_its_own_wiring(library):
    model = link_model(
        library,
        ALLOCATED_MODEL,
        object_overrides={"us:HotBand": {"traded": (False, False)}},
    )
    assert list(model.processes) == ["SheetSale", "HotStripMill", "HotBandDistribution"]
    assert [i.object_name for i in model.processes["SheetSale"].consumes] == [
        "HotBandForSale"
    ]
    assert library.objects[US + "HotBand"].traded == (False, True)
    assert model.objects["HotBand"].traded == (False, False)
    assert model.objects["HotBandForSale"].namespace == ALLOCATED


def test_a_namespace_selection_is_by_declaration_not_by_iri_prefix(library):
    # US is a string prefix of both alternatives' namespaces; selecting it must not
    # bring either in.
    model = link_model(library, [RECIPES_MODEL[0]])
    assert list(model.processes) == ["SheetSale"]


def test_clashing_local_names_are_disambiguated_by_prefix(library):
    model = link_model(
        library,
        [ProcessSelection(ALL, {"_:HotBandForSale": "us:HotBand"})],
    )
    assert list(model.processes) == [
        "SheetSale", "rec:HotStripMill", "alloc:HotStripMill", "HotBandDistribution"
    ]


def test_local_names_can_be_given(library):
    model = link_model(
        library,
        RECIPES_MODEL,
        local_names={"rec:HotStripMill": "Mill", "us:HotBand": "Band"},
    )
    assert list(model.processes) == ["SheetSale", "Mill"]
    assert [i.object_name for i in model.processes["Mill"].produces] == [
        "Band", "Scrap"
    ]


def test_a_given_local_name_takes_precedence_over_the_rule(library):
    model = link_model(library, RECIPES_MODEL, local_names={"us:Sheet": "Scrap"})
    assert model.objects["Scrap"].namespace == US
    assert [i.object_name for i in model.processes["SheetSale"].produces] == ["Scrap"]
    assert [i.object_name for i in model.processes["HotStripMill"].produces] == [
        "HotBand", "us:Scrap"
    ]


def test_two_given_local_names_must_differ(library):
    with pytest.raises(LinkError, match="both be called 'Same'"):
        link_model(
            library,
            RECIPES_MODEL,
            local_names={"us:Sheet": "Same", "us:Scrap": "Same"},
        )


def test_a_given_local_name_must_be_in_the_model(library):
    with pytest.raises(LinkError, match="local_names: not in this model"):
        link_model(library, RECIPES_MODEL, local_names={"us:Unused": "U"})


def test_an_open_placeholder_is_an_error(library):
    with pytest.raises(LinkError, match="placeholders left open"):
        link_model(library, [ProcessSelection("us:"), ProcessSelection("rec:")])


def test_a_remap_can_cover_a_namespace(library):
    model = link_model(
        library,
        [ProcessSelection("alloc:", {"us:Scrap": "us:Sheet"}), *ALLOCATED_MODEL],
    )
    for name in ("HotStripMill", "HotBandDistribution"):
        assert "Scrap" not in {i.object_name for i in model.processes[name].produces}
    # Scrap is no longer referred to, so it is not part of the model.
    assert "Scrap" not in model.objects


def test_a_remap_can_be_scoped_to_one_process(library):
    model = link_model(
        library,
        [
            ProcessSelection("alloc:HotStripMill", {"us:Scrap": "us:Sheet"}),
            *ALLOCATED_MODEL,
        ],
    )
    assert [i.object_name for i in model.processes["HotStripMill"].produces] == [
        "HotBand", "Sheet"
    ]
    assert [
        i.object_name for i in model.processes["HotBandDistribution"].produces
    ] == ["HotBandForSale", "Scrap"]


def test_a_remap_that_matches_nothing_is_an_error(library):
    with pytest.raises(LinkError, match="refers to 'us:Nothing'"):
        link_model(
            library,
            RECIPES_MODEL + [ProcessSelection(ALL, {"us:Nothing": "us:HotBand"})],
        )


def test_two_remaps_of_one_reference_in_one_process_are_an_error(library):
    with pytest.raises(LinkError, match="remapped to both"):
        link_model(
            library,
            RECIPES_MODEL
            + [ProcessSelection(["us:SheetSale"], {"_:HotBandForSale": "us:Sheet"})],
        )


def test_the_same_remap_twice_is_not_an_error(library):
    link_model(library, RECIPES_MODEL + [RECIPES_MODEL[0]])


def test_an_override_must_name_an_object_of_the_model(library):
    with pytest.raises(LinkError, match="not an object of this model"):
        link_model(
            library,
            RECIPES_MODEL,
            object_overrides={"alloc:HotBandForSale": {"traded": (False, True)}},
        )


def test_a_reference_to_an_undefined_object_is_an_error(library):
    with pytest.raises(LinkError, match="never defined"):
        link_model(
            library,
            [ProcessSelection("us:", {"_:HotBandForSale": "us:Nowhere"})],
        )


@pytest.mark.parametrize(
    "scope, message",
    [
        ("nope:", "unknown prefix 'nope'"),
        ("us:Nothing", "no process 'us:Nothing'"),
        (["us:SheetSale", "Nothing"], "no process 'Nothing'"),
    ],
)
def test_a_scope_must_name_something(library, scope, message):
    with pytest.raises(LinkError, match=message):
        link_model(library, [ProcessSelection(scope)])


def test_an_empty_namespace_is_an_error():
    library = parse_markdown(
        "```{system:process} ns:P\n```\n",
        prefixes={"ns": "http://example.org/ns/", "other": "http://example.org/o/"},
    )
    with pytest.raises(LinkError, match="no process is declared in namespace"):
        link_model(library, [ProcessSelection("other:")])


def test_a_full_iri_definition_is_named_by_its_iri():
    library = parse_markdown(
        "```{system:process} <http://elsewhere.org/P>\n```\n", prefixes=PREFIXES
    )
    model = link_model(library, [ProcessSelection("<http://elsewhere.org/P>")])
    assert list(model.processes) == ["<http://elsewhere.org/P>"]


def test_a_library_without_prefixes_links_to_its_own_names():
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
    assert link_model(library, [ProcessSelection("Eat")]).processes.keys() == {"Eat"}
