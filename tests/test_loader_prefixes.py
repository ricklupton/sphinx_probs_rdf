"""The loader with a prefix table: expansion, ``system:prefix``, placeholders.

Without a table (``prefixes=None``) the default namespace is ``""``, so a bare name is
its own identifier -- every other loader test runs that way.
"""

import pytest

from sphinx_probs_rdf.identifiers import Prefixes
from sphinx_probs_rdf.loader import parse_markdown, parse_system_definitions
from sphinx_probs_rdf.validate import validate

US = "http://example.org/us/"
FRAG = "http://example.org/us-fragment/"
PREFIXES = {"": US, "us": US, "frag": FRAG}


def test_without_a_table_a_bare_name_is_its_own_identifier():
    system = parse_markdown(
        """
```{system:object} Crumble
```

```{system:object} :Blackberries
```
"""
    )
    assert set(system.objects) == {"Crumble", "Blackberries"}
    assert system.prefixes == {"": ""}
    assert system.objects["Crumble"].namespace == ""


def test_without_a_table_a_prefixed_name_is_an_error():
    with pytest.raises(ValueError, match="unknown prefix 'prefix'"):
        parse_markdown("```{system:object} prefix:Crumble\n```\n")


def test_bare_and_prefixed_names_expand():
    system = parse_markdown(
        """
```{system:object} Apples
```

```{system:object} :Blackberries
```

```{system:object} frag:Crumble
```

```{system:object} <http://elsewhere.org/Custard>
```
""",
        prefixes=PREFIXES,
    )
    assert set(system.objects) == {
        US + "Apples",
        US + "Blackberries",
        FRAG + "Crumble",
        "http://elsewhere.org/Custard",
    }
    crumble = system.objects[FRAG + "Crumble"]
    assert (crumble.namespace, crumble.label) == (FRAG, "frag:Crumble")
    assert system.objects["http://elsewhere.org/Custard"].namespace is None


def test_every_reference_is_expanded():
    system = parse_markdown(
        """
```{system:object} Fruit
```

```{system:object} Apples
---
parent_object: Fruit
equivalent: frag:
---
```

```{system:object} Basket
---
composed_of: Apples *frag:Other
---
```

```{system:process} Bake
---
consumes: |
  Apples = 0.7 kg
  frag:Sugar = 0.3 kg
produces: |
  frag:Crumble = 1 kg
per: {object: frag:Crumble, direction: output}
---
```
""",
        prefixes=PREFIXES,
    )
    apples = system.objects[US + "Apples"]
    assert apples.parent == US + "Fruit"
    assert apples.equivalent_to == [FRAG + "Apples"]
    basket = system.objects[US + "Basket"]
    assert basket.composed_of == [US + "Apples"]
    assert basket.composed_of_children_of == [FRAG + "Other"]
    bake = system.processes[US + "Bake"]
    assert [i.object_name for i in bake.consumes] == [US + "Apples", FRAG + "Sugar"]
    assert [i.object_name for i in bake.produces] == [FRAG + "Crumble"]
    assert bake.per == {"object": FRAG + "Crumble", "direction": "output"}


def test_basis_names_are_never_expanded():
    system = parse_markdown(
        """
```{system:object} Apples
---
basis: mass
factors:
  volume: {value: 2}
---
```

```{system:process} Bake
---
consumes: |
  Apples = 100 %mass
produces: |
  frag:Crumble = 100 %
balance: [mass]
---
```
""",
        prefixes=PREFIXES,
    )
    assert system.objects[US + "Apples"].basis == "mass"
    assert list(system.objects[US + "Apples"].factors) == ["volume"]
    bake = system.processes[US + "Bake"]
    assert bake.consumes[0].unit == "%mass"
    assert bake.balance == ["mass"]


def test_system_prefix_sets_the_namespace_of_the_rest_of_one_file(tmp_path):
    base = tmp_path / "base.md"
    base.write_text(
        """
```{system:object} Steel
```
"""
    )
    fragment = tmp_path / "fragment.md"
    fragment.write_text(
        """
```{system:object} Ore
```

```{system:prefix} frag
```

```{system:process} Cast
---
consumes: |
  us:Steel = 100 %
produces: |
  Slab = 100 %
---
```

```{system:object} Slab
```

```{system:prefix} :
```

```{system:object} Billet
```
"""
    )
    after = tmp_path / "after.md"
    after.write_text(
        """
```{system:prefix} frag
```

```{system:object} Rolled
```
"""
    )
    system = parse_system_definitions(
        [base, fragment, after], prefixes=PREFIXES, validate=False
    )
    assert set(system.objects) == {
        US + "Steel", US + "Ore", FRAG + "Slab", US + "Billet", FRAG + "Rolled"
    }
    cast = system.processes[FRAG + "Cast"]
    assert cast.namespace == FRAG
    assert [i.object_name for i in cast.consumes] == [US + "Steel"]
    assert [i.object_name for i in cast.produces] == [FRAG + "Slab"]


def test_system_prefix_does_not_carry_over_to_the_next_file(tmp_path):
    first = tmp_path / "first.md"
    first.write_text("```{system:prefix} frag\n```\n")
    second = tmp_path / "second.md"
    second.write_text("```{system:object} Steel\n```\n")
    system = parse_system_definitions([first, second], prefixes=PREFIXES)
    assert set(system.objects) == {US + "Steel"}


@pytest.mark.parametrize("spec", ["frag", "frag:", f"<{FRAG}>"])
def test_system_prefix_names_a_namespace_by_prefix_or_iri(spec):
    system = parse_markdown(
        f"""
```{{system:prefix}} {spec}
```

```{{system:object}} Slab
```
""",
        prefixes=PREFIXES,
    )
    assert set(system.objects) == {FRAG + "Slab"}


def test_system_prefix_must_name_a_declared_prefix():
    with pytest.raises(ValueError, match="unknown prefix 'frag'"):
        parse_markdown("```{system:prefix} frag\n```\n")


def test_an_unknown_prefix_is_an_error():
    with pytest.raises(ValueError, match="unknown prefix 'nope'"):
        parse_markdown(
            """
```{system:object} nope:Apples
```
""",
            prefixes=PREFIXES,
        )


def test_one_identifier_defined_twice_is_an_error_however_it_is_spelled():
    with pytest.raises(ValueError, match="already defined"):
        parse_markdown(
            """
```{system:object} Apples
```

```{system:object} us:Apples
```
""",
            prefixes=PREFIXES,
        )


def test_redefinition_is_an_error_without_prefixes_too():
    with pytest.raises(ValueError, match="already defined"):
        parse_markdown(
            """
```{system:object} Apples
```

```{system:object} Apples
```
"""
        )


def test_the_same_local_name_in_two_namespaces_is_two_definitions():
    system = parse_markdown(
        """
```{system:process} Cast
```

```{system:process} frag:Cast
```
""",
        prefixes=PREFIXES,
    )
    assert set(system.processes) == {US + "Cast", FRAG + "Cast"}
    assert {p.namespace for p in system.processes.values()} == {US, FRAG}


def test_nesting_stacks_hold_expanded_identifiers():
    system = parse_markdown(
        """
```{system:object} frag:Fruit
:become_parent: true
```

```{system:object} Apples
```

```{end-sub-objects}
```
""",
        prefixes=PREFIXES,
    )
    assert system.objects[US + "Apples"].parent == FRAG + "Fruit"


# -- placeholders ---------------------------------------------------------------------


PLACEHOLDER_DOC = """
```{system:object} Steel
```

```{system:process} Sale
---
consumes: |
  _:HotBand = 100 %
produces: |
  Steel = 100 %
per: {object: _:HotBand, direction: input}
---
```
"""


@pytest.mark.parametrize("prefixes", [None, PREFIXES])
def test_a_placeholder_is_an_open_reference_not_an_undeclared_object(prefixes):
    system = parse_markdown(PLACEHOLDER_DOC, prefixes=prefixes)
    sale = next(iter(system.processes.values()))
    assert [i.object_name for i in sale.consumes] == ["_:HotBand"]
    assert sale.per["object"] == "_:HotBand"
    assert sale.placeholders() == ["_:HotBand"]
    assert validate(system) == []


@pytest.mark.parametrize(
    "doc",
    [
        "```{system:object} _:Thing\n```\n",
        "```{system:object} Thing\n---\nparent_object: _:Group\n---\n```\n",
        "```{system:object} Thing\n---\ncomposed_of: _:Part\n---\n```\n",
    ],
)
def test_a_placeholder_can_only_stand_for_a_recipe_object(doc):
    with pytest.raises(ValueError, match="placeholder"):
        parse_markdown(doc, prefixes=PREFIXES)


# -- the prefix table -----------------------------------------------------------------


def test_the_placeholder_prefix_is_reserved():
    with pytest.raises(ValueError, match="reserved"):
        Prefixes({"_": "http://example.org/"})


def test_compact_uses_the_longest_matching_prefix():
    prefixes = Prefixes({"": US, "us": US, "deep": US + "deep/"})
    assert prefixes.compact(US + "deep/Thing") == "deep:Thing"
    assert prefixes.compact(US + "Thing") == "us:Thing"
    assert prefixes.compact("http://elsewhere.org/X") == "<http://elsewhere.org/X>"
    assert Prefixes({"": US}).compact(US + "Thing") == ":Thing"


def test_compact_without_a_default_namespace():
    prefixes = Prefixes()
    assert prefixes.compact("Thing") == "Thing"
    assert prefixes.compact("http://elsewhere.org/X") == "<http://elsewhere.org/X>"
