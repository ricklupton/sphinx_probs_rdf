"""The loader with a prefix table: expansion, per-file namespaces, placeholders.

Without a table (``prefixes=None``) identifiers stay exactly as written -- every other
loader test runs that way, and ``test_opaque_mode_keeps_identifiers_as_written`` pins it.
"""

import logging

import pytest

from sphinx_probs_rdf.identifiers import Prefixes
from sphinx_probs_rdf.loader import parse_markdown, parse_system_definitions
from sphinx_probs_rdf.validate import open_references, validate

US = "http://example.org/us/"
FRAG = "http://example.org/us-fragment/"
PREFIXES = {"": US, "us": US, "frag": FRAG}


def test_opaque_mode_keeps_identifiers_as_written():
    system = parse_markdown(
        """
```{system:object} prefix:Crumble
```

```{system:object} :Blackberries
```
"""
    )
    assert set(system.objects) == {"prefix:Crumble", ":Blackberries"}
    assert system.prefixes is None
    assert system.objects["prefix:Crumble"].namespace == ""
    assert system.objects["prefix:Crumble"].local_name == "prefix:Crumble"


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
    assert (crumble.namespace, crumble.local_name, crumble.label) == (
        FRAG, "Crumble", "frag:Crumble"
    )
    custard = system.objects["http://elsewhere.org/Custard"]
    assert (custard.namespace, custard.local_name) == (None, None)


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


def test_front_matter_sets_the_namespace_of_one_file(tmp_path):
    base = tmp_path / "base.md"
    base.write_text(
        """
```{system:object} Steel
```
"""
    )
    fragment = tmp_path / "fragment.md"
    fragment.write_text(
        """---
system_prefix: frag
---

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
"""
    )
    after = tmp_path / "after.md"
    after.write_text(
        """
```{system:object} Rolled
```
"""
    )
    system = parse_system_definitions(
        [base, fragment, after], prefixes=PREFIXES, validate=False
    )
    assert set(system.objects) == {US + "Steel", FRAG + "Slab", US + "Rolled"}
    cast = system.processes[FRAG + "Cast"]
    assert cast.namespace == FRAG
    assert [i.object_name for i in cast.consumes] == [US + "Steel"]
    assert [i.object_name for i in cast.produces] == [FRAG + "Slab"]


@pytest.mark.parametrize("spec", ["frag", "frag:", f"<{FRAG}>"])
def test_front_matter_names_a_namespace_by_prefix_or_iri(spec):
    system = parse_markdown(
        f"""---
system_prefix: "{spec}"
---

```{{system:object}} Slab
```
""",
        prefixes=PREFIXES,
    )
    assert set(system.objects) == {FRAG + "Slab"}


def test_front_matter_needs_a_prefix_table():
    with pytest.raises(ValueError, match="needs a prefix table"):
        parse_markdown("---\nsystem_prefix: frag\n---\n")


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
    assert {p.local_name for p in system.processes.values()} == {"Cast"}


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
    assert open_references(system) == [f"{sale.name}: _:HotBand"]


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


def test_a_namespace_without_a_separator_warns(caplog):
    with caplog.at_level(logging.WARNING):
        Prefixes({"us": "http://example.org/us"})
    assert "ends in neither" in caplog.text


def test_compact_uses_the_longest_matching_prefix():
    prefixes = Prefixes({"": US, "us": US, "deep": US + "deep/"})
    assert prefixes.compact(US + "deep/Thing") == "deep:Thing"
    assert prefixes.compact("http://elsewhere.org/X") == "<http://elsewhere.org/X>"
