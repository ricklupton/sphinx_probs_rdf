"""Unit tests for the standalone loader, using inline markdown only.

Repo-level regression tests that check the loader against the real
``tests/fixtures/*.md`` files (and the RDF-derived equivalence test) live in
``test_loader_fixtures.py``/``test_loader_equivalence.py``.
"""

import pytest

from sphinx_probs_rdf.loader import parse_markdown
from sphinx_probs_rdf.units import DEFAULT_UNITS, Unit, UnitTable
from sphinx_probs_rdf.validate import validate

#: A table using plain basis labels rather than : DEFAULT_UNITS' QUDT URIs --
#used by tests that write a `:basis:` value and check : it against a recipe
#item, so the basis id in the test reads naturally.
LAYER_UNITS = UnitTable({
    "kg": Unit(1.0, "mass"),
    "m2": Unit(1.0, "area"),
    "m3": Unit(1.0, "volume"),
    "-": Unit(1.0, "items"),
})


def test_become_parent_and_end_marker():
    system = parse_markdown(
        """
```{system:object} Sawnwood
:become_parent: true
```

```{system:object} SoftwoodSawnwood
```

```{system:object} HardwoodSawnwood
```

```{end-sub-objects}
```

```{system:object} Elsewhere
```
"""
    )
    assert system.objects["SoftwoodSawnwood"].parent == "Sawnwood"
    assert system.objects["HardwoodSawnwood"].parent == "Sawnwood"
    assert system.objects["Elsewhere"].parent is None
    assert system.children_of_object("Sawnwood") == ["HardwoodSawnwood", "SoftwoodSawnwood"]


def test_directive_nested_in_body():
    """A directive inside another's body takes it as parent.

    A closing fence carries no info string, so an opening fence that is never
    explicitly closed swallows everything up to the *next* closing fence into its own
    body -- including a whole nested directive. MyST parses a directive body as
    markdown, which is why Sphinx picks it up, and why this parser recurses.
    """
    system = parse_markdown(
        """
```{system:object} Joinery
:become_parent: true
:label: Joinery

Prose about joinery.

```{system:object} Windows
:label: Windows
```
"""
    )
    assert set(system.objects) == {"Joinery", "Windows"}
    assert system.objects["Windows"].parent == "Joinery"


def test_unrecognised_system_directive_warns_not_skips(caplog):
    system = parse_markdown(
        """
```{system:something-else} Foo
content
```
"""
    )
    assert system.objects == {}
    assert system.processes == {}
    assert "unrecognised directive" in caplog.text
    assert "system:something-else" in caplog.text


# ---------------------------------------------------------------------------------
# What the RDF builder discards and this parser keeps
# ---------------------------------------------------------------------------------


def test_recipe_item_extras_are_kept():
    system = parse_markdown(
        """
```{system:process} SawmillsSoftwood
---
label: Sawmills
consumes: |
    SoftwoodRoundwood = 1 kg
produces: |
    SoftwoodSawnwood = 0.53 kg {range: [0.45, 0.62], source: "SI Table S3"}
    ByProducts       = 0.47 kg
---
```
"""
    )
    produces = {i.object_name: i for i in system.processes["SawmillsSoftwood"].produces}
    assert produces["SoftwoodSawnwood"].extra == {
        "range": [0.45, 0.62],
        "source": "SI Table S3",
    }
    assert produces["ByProducts"].extra == {}
    assert produces["SoftwoodSawnwood"].quantity(DEFAULT_UNITS) == 0.53
    assert produces["SoftwoodSawnwood"].basis(DEFAULT_UNITS) == (
        "http://qudt.org/vocab/quantitykind/Mass"
    )


def test_traded_keeps_the_import_export_pair():
    system = parse_markdown(
        """
```{system:object} Pulp
:traded: both
```

```{system:object} ImportedOnly
:traded: imports
```

```{system:object} Untraded
```
"""
    )
    assert system.objects["Pulp"].traded == (True, True)
    assert system.objects["ImportedOnly"].traded == (True, False)
    assert system.objects["Untraded"].traded is None


# ---------------------------------------------------------------------------------
# Validation the RDF/SPARQL path could not do
# ---------------------------------------------------------------------------------


def test_validate_catches_undeclared_object():
    system = parse_markdown(
        """
```{system:process} Sawmills
---
consumes: |
    Roundwood = 1 kg
produces: |
    Sawnwood = 1 kg
---
```
"""
    )
    problems = validate(system)
    assert len(problems) == 2
    assert any("Roundwood" in p for p in problems)
    assert any("Sawnwood" in p for p in problems)


def test_unsupported_unit_raises():
    with pytest.raises(ValueError, match="unsupported unit"):
        parse_markdown(
            """
```{system:process} Weird
---
produces: |
    Thing = 1 furlong
---
```
"""
        )


# ---------------------------------------------------------------------------------
# :basis: and the recipe-item basis check
# ---------------------------------------------------------------------------------


def test_basis_defaults_to_none():
    system = parse_markdown(
        """
```{system:object} Default
```

```{system:object} Board
:basis: area
```
"""
    )
    assert system.objects["Default"].basis is None
    assert system.objects["Board"].basis == "area"


def test_validate_catches_recipe_item_in_wrong_layer():
    """A `kg` item for an `items`-basis object is a warning."""
    system = parse_markdown(
        """
```{system:object} Chairs
:basis: items
```

```{system:process} ChairMaking
---
produces: |
    Chairs = 450 kg
---
```
""",
        units=LAYER_UNITS,
    )
    problems = validate(system)
    assert len(problems) == 1
    assert "basis 'mass'" in problems[0]
    assert "Chairs" in problems[0]


def test_validate_is_a_no_op_when_item_matches_basis():
    system = parse_markdown(
        """
```{system:object} Board
:basis: area
```

```{system:process} BoardMaking
---
produces: |
    Board = 1 m2
---
```
""",
        units=LAYER_UNITS,
    )
    assert validate(system) == []


def test_basis_derived_from_recipe_items_when_none_declared():
    """With no explicit `:basis:`, a consistent object's basis is inferred from its
    own recipe items."""
    system = parse_markdown(
        """
```{system:object} Board
```

```{system:process} BoardMaking
---
produces: |
    Board = 1 m2
---
```

```{system:process} BoardUse
---
consumes: |
    Board = 1 m2
---
```
"""
    )
    assert system.objects["Board"].basis == "http://qudt.org/vocab/quantitykind/Area"
    assert validate(system) == []


def test_basis_disagreement_across_items_raises():
    """Unlike an object simply never stating a basis (left None, not an error), its
    own recipe items disagreeing on one is a contradiction in explicitly-written
    data."""
    with pytest.raises(ValueError, match="disagree on basis"):
        parse_markdown(
            """
```{system:object} Confused
```

```{system:process} MakesIt
---
produces: |
    Confused = 1 m2
---
```

```{system:process} UsesIt
---
consumes: |
    Confused = 1 kg
---
```
"""
        )


def test_basis_disagreements_across_multiple_objects_all_reported_together():
    """Every disagreement in the document is collected into one raised error, not
    just the first."""
    with pytest.raises(ValueError) as excinfo:
        parse_markdown(
            """
```{system:object} ConfusedA
```

```{system:object} ConfusedB
```

```{system:process} MakesThem
---
produces: |
    ConfusedA = 1 m2
    ConfusedB = 1 m2
---
```

```{system:process} UsesThem
---
consumes: |
    ConfusedA = 1 kg
    ConfusedB = 1 kg
---
```
"""
        )
    assert "ConfusedA" in str(excinfo.value)
    assert "ConfusedB" in str(excinfo.value)


# ---------------------------------------------------------------------------------
# :factors: and system:parameter
# ---------------------------------------------------------------------------------


def test_factors_parsed_per_basis():
    system = parse_markdown(
        """
```{system:object} Particleboard
:label: Particleboard
:basis: mass
:factors: {volume: {value: 1.61, unit: t/m3, range: [1.54, 1.68], source: "SI Table S5"}}
```
"""
    )
    factors = system.objects["Particleboard"].factors
    assert set(factors) == {"volume"}
    assert factors["volume"].value == 1.61
    assert factors["volume"].unit == "t/m3"
    assert factors["volume"].range == (1.54, 1.68)
    assert factors["volume"].source == "SI Table S5"
    assert factors["volume"].derived is False


def test_factors_expression_kept_raw_for_a_consumer_to_evaluate():
    system = parse_markdown(
        """
```{system:object} Doors
:factors: {product_mass: {value: "(1 - 0.09) / wood_dry_density", unit: t/t, source: "SI Table S6"}}
```
"""
    )
    factor = system.objects["Doors"].factors["product_mass"]
    assert factor.value == "(1 - 0.09) / wood_dry_density"


def test_factors_derived():
    system = parse_markdown(
        """
```{system:object} Board
:basis: area
:factors: {mass: {derived: true}}
```
"""
    )
    factor = system.objects["Board"].factors["mass"]
    assert factor.derived is True
    assert factor.value is None


def test_system_parameter():
    system = parse_markdown(
        """
```{system:parameter} wood_dry_density
:label: Oven-dry density of wood
:value: 0.467 t/m3
:range: [0.449, 0.495]
:source: "SI Table S7"
```
"""
    )
    p = system.parameters["wood_dry_density"]
    assert p.label == "Oven-dry density of wood"
    assert p.value == 0.467
    assert p.unit == "t/m3"
    assert p.range == (0.449, 0.495)
    assert p.source == "SI Table S7"


def test_system_parameter_value_without_unit():
    system = parse_markdown(
        """
```{system:parameter} moisture_multiplier
:value: 1.19
```
"""
    )
    p = system.parameters["moisture_multiplier"]
    assert p.value == 1.19
    assert p.unit is None


# ---------------------------------------------------------------------------------
# `%`, `per:`, `balance:` -- is a side a simplex?
# ---------------------------------------------------------------------------------


def test_percent_item_is_a_share_not_an_amount():
    system = parse_markdown(
        """
```{system:process} SawmillsSoftwood
---
label: Sawmills (softwood)
consumes: |
    SoftwoodRoundwood = 100 %
produces: |
    SoftwoodSawnwood = 53 % {range: [45, 62], source: "UNECE"}
    ByProducts       = 47 %
---
```
"""
    )
    sawnwood = {
        i.object_name: i for i in system.processes["SawmillsSoftwood"].produces
    }["SoftwoodSawnwood"]
    assert sawnwood.is_share is True
    assert sawnwood.share_layer is None
    assert sawnwood.amount == 53
    assert sawnwood.quantity(DEFAULT_UNITS) == 53
    assert sawnwood.extra == {"range": [45, 62], "source": "UNECE"}


def test_percent_layer_splits_off_the_layer_name():
    system = parse_markdown(
        """
```{system:process} Mixed
---
produces: |
    chips = 70 %mass
---
```
"""
    )
    item = system.processes["Mixed"].produces[0]
    assert item.unit == "%mass"
    assert item.is_share is True
    assert item.share_layer == "mass"


def test_per_and_balance_parsed_as_yaml():
    system = parse_markdown(
        """
```{system:process} WoodFramesForNewStructuresManufacturing
---
label: Wood frames for new structures manufacturing
per: {object: WoodFramesForNewStructures, direction: output}
consumes: |
    SoftwoodSawnwood           = 14.6 kg {sd: 5.0, source: "SI Table S4"}
produces: |
    WoodFramesForNewStructures = 1    m2
    PreConsumerWasteProducts   = 1.46 kg
balance: [mass]
---
```
"""
    )
    proc = system.processes["WoodFramesForNewStructuresManufacturing"]
    assert proc.per == {"object": "WoodFramesForNewStructures", "direction": "output"}
    assert proc.balance == ["mass"]


def test_per_absent_by_default():
    system = parse_markdown(
        """
```{system:process} Sawmills
---
consumes: |
    Roundwood = 100 %
produces: |
    Sawnwood = 100 %
---
```
"""
    )
    proc = system.processes["Sawmills"]
    assert proc.per is None
    assert proc.balance is None


def test_validate_no_inlayer_finding_for_a_percent_item():
    system = parse_markdown(
        """
```{system:object} Chairs
:basis: items
```

```{system:object} Wood
```

```{system:process} ChairMaking
---
consumes: |
    Wood = 100 %
produces: |
    Chairs = 100 %
---
```
"""
    )
    assert validate(system) == []


def test_validate_catches_shares_not_summing_to_100():
    system = parse_markdown(
        """
```{system:object} A
```

```{system:object} B
```

```{system:process} Split
---
produces: |
    A = 60 %
    B = 30 %
---
```
"""
    )
    problems = validate(system)
    assert len(problems) == 1
    assert "Sum" in problems[0]
    assert "90%" in problems[0]


def test_validate_catches_mixed_percent_and_non_percent_side():
    system = parse_markdown(
        """
```{system:object} A
```

```{system:object} B
```

```{system:process} Mixed
---
produces: |
    A = 60 %
    B = 1   kg
---
```
"""
    )
    problems = validate(system)
    assert len(problems) == 1
    assert "mixes % and non-% items" in problems[0]


def test_validate_catches_bare_percent_across_differing_bases():
    system = parse_markdown(
        """
```{system:object} A
:basis: mass
```

```{system:object} B
:basis: volume
```

```{system:process} Mixed
---
produces: |
    A = 60 %
    B = 40 %
---
```
"""
    )
    problems = validate(system)
    assert len(problems) == 1
    assert "bare '%' shares" in problems[0]


def test_validate_allows_percent_layer_across_differing_bases():
    """An explicit `%layer` names its own basis, so it carries no common-basis
    requirement -- unlike a bare `%` (see the test above)."""
    system = parse_markdown(
        """
```{system:object} A
:basis: mass
```

```{system:object} B
:basis: volume
```

```{system:process} Mixed
---
produces: |
    A = 60 %mass
    B = 40 %mass
---
```
"""
    )
    assert validate(system) == []


def test_validate_is_a_no_op_for_an_absent_side():
    system = parse_markdown(
        """
```{system:object} SoftwoodRoundwood
```

```{system:process} SoftwoodRoundwoodDelivery
---
consumes: |
produces: |
    SoftwoodRoundwood = 100 %
---
```
"""
    )
    assert validate(system) == []


# ---------------------------------------------------------------------------------
# composed_of vs the "*Name" (children-of) form
# ---------------------------------------------------------------------------------


def test_composed_of_children_of_form_is_split_off():
    system = parse_markdown(
        """
```{system:object} A
```

```{system:object} B
:composed_of: A *Elsewhere
```
"""
    )
    assert system.objects["B"].composed_of == ["A"]
    assert system.objects["B"].composed_of_children_of == ["Elsewhere"]
    # Not expanded here -- a consumer resolves it, same as the RDF postprocessing step.
    assert system.children_of_object("B") == ["A"]


# ---------------------------------------------------------------------------------
# :extra: -- a downstream project's own vocabulary, with no option registration
# ---------------------------------------------------------------------------------


def test_extra_option_lands_in_process_extra():
    system = parse_markdown(
        """
```{system:process} Weird
---
extra:
  consumes_concentration: 42
produces: |
    Thing = 1 kg
---
```

```{system:object} Thing
```
"""
    )
    assert system.processes["Weird"].extra == {"consumes_concentration": 42}


def test_no_extra_option_gives_empty_dict():
    system = parse_markdown(
        """
```{system:process} Plain
produces: |
    Thing = 1 kg
```

```{system:object} Thing
```
"""
    )
    assert system.processes["Plain"].extra == {}


def test_extra_option_lands_in_object_extra():
    system = parse_markdown(
        """
```{system:object} Thing
:extra: {some_key: some_value}
```
"""
    )
    assert system.objects["Thing"].extra == {"some_key": "some_value"}


# ---------------------------------------------------------------------------------
# Units: an injected table changes what is accepted
# ---------------------------------------------------------------------------------


def test_injected_unit_table_accepts_its_own_units():
    units = UnitTable({"kWh": Unit(1.0, "Energy")})
    system = parse_markdown(
        """
```{system:object} Electricity
```

```{system:process} Generate
---
produces: |
    Electricity = 1 kWh
---
```
""",
        units=units,
    )
    item = system.processes["Generate"].produces[0]
    assert item.basis(units) == "Energy"
    assert item.quantity(units) == 1.0
