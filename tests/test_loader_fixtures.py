"""Regression tests against the repo-level fixtures in ``tests/fixtures/`` -- see
``tests/fixtures/README.md`` for the full expected values these assert against.
"""

from pathlib import Path

import pytest

from sphinx_probs_rdf.loader import parse_system_definitions
from sphinx_probs_rdf.units import DEFAULT_UNITS, Unit, UnitTable
from sphinx_probs_rdf.validate import validate

FIXTURES = Path(__file__).parent / "fixtures"

#: The unit table `tests/fixtures/README.md` documents as required by the energy and
#: structural-edge-cases fixtures -- kg/m2/m3/- plus two additional units.
FLOWPROG_UNITS = UnitTable(
    units={
        "kg": Unit(1.0, "http://qudt.org/vocab/quantitykind/Mass"),
        "m2": Unit(1.0, "http://qudt.org/vocab/quantitykind/Area"),
        "m3": Unit(1.0, "http://qudt.org/vocab/quantitykind/Volume"),
        "-": Unit(1.0, "http://qudt.org/vocab/quantitykind/Dimensionless"),
        "kWh": Unit(1.0, "http://qudt.org/vocab/quantitykind/Energy"),
        "pkm": Unit(1.0, "http://probs-lab.github.io/flowprog/metrics/PassengerKM"),
    },
)


def test_recycling_fixture():
    system = parse_system_definitions(
        [FIXTURES / "recycling" / "system-definitions.md"],
        units=DEFAULT_UNITS,
        validate=False,
    )

    assert set(system.objects) == {
        "EoLTechnology", "GoldAndPlastic", "MixedPCBWaste", "OtherParts", "PCBs", "PureGold",
    }
    assert set(system.processes) == {
        "Disassembly", "EoLProcessing", "GoldAndPlasticProcessing", "PCBProcess1", "PCBProcess2",
    }
    assert set(system.processes_with_recipes()) == set(system.processes)
    assert validate(system) == []

    expected_recipe = {
        "EoLProcessing": ({}, {"EoLTechnology": 1.0}),
        "Disassembly": ({"EoLTechnology": 1.0}, {"PCBs": 0.2, "OtherParts": 0.8}),
        "PCBProcess1": ({"PCBs": 1.0}, {"PureGold": 0.1, "MixedPCBWaste": 0.9}),
        "PCBProcess2": ({"PCBs": 1.0}, {"GoldAndPlastic": 0.3, "MixedPCBWaste": 0.7}),
        "GoldAndPlasticProcessing": ({"GoldAndPlastic": 1.0}, {"PureGold": 0.2, "MixedPCBWaste": 0.8}),
    }
    for name, (consumes, produces) in expected_recipe.items():
        proc = system.processes[name]
        assert {i.object_name: i.quantity(DEFAULT_UNITS) for i in proc.consumes} == consumes
        assert {i.object_name: i.quantity(DEFAULT_UNITS) for i in proc.produces} == produces


def test_energy_fixture():
    system = parse_system_definitions(
        [FIXTURES / "energy" / "system-definitions.md"],
        units=FLOWPROG_UNITS,
        validate=False,
    )

    assert set(system.objects) == {
        "Electricity", "Hydrogen", "NaturalGas", "Steel", "TransportService",
    }
    assert set(system.processes) == {
        "CCGT", "ElectricCarUse", "ElectricityGeneration", "ElectricityUse",
        "HydrogenElectrolysis", "SteelProductionEAF", "SteelProductionH2DRI", "WindTurbine",
    }
    assert set(system.processes_with_recipes()) == {
        "CCGT", "ElectricCarUse", "HydrogenElectrolysis",
        "SteelProductionEAF", "SteelProductionH2DRI", "WindTurbine",
    }

    parents = {
        "CCGT": "ElectricityGeneration",
        "WindTurbine": "ElectricityGeneration",
        "ElectricCarUse": "ElectricityUse",
        "SteelProductionEAF": "ElectricityUse",
        "SteelProductionH2DRI": "ElectricityUse",
    }
    for name, parent in parents.items():
        assert system.processes[name].parent == parent

    problems = validate(system)
    assert len(problems) == 1
    assert "Fuels" in problems[0]
    assert "ElectricityGeneration" in problems[0]

    QK = "http://qudt.org/vocab/quantitykind/"
    expected_bases = {
        "Electricity": QK + "Energy",
        "TransportService": "http://probs-lab.github.io/flowprog/metrics/PassengerKM",
        "NaturalGas": QK + "Mass",
        "Hydrogen": QK + "Mass",
        "Steel": QK + "Mass",
    }
    # Resolved by the loader itself (from each object's own recipe items, since none
    # declare :basis: explicitly).
    assert {name: system.objects[name].basis for name in expected_bases} == expected_bases


def test_structural_edge_cases_fixture():
    units = UnitTable({**DEFAULT_UNITS.units, "kWh": Unit(1.0, "Energy")})
    system = parse_system_definitions(
        [FIXTURES / "structural-edge-cases.md"], units=units, validate=False
    )

    assert set(system.objects) == {"Coal", "ColonFenceObject", "Heat", "Widget"}
    assert set(system.processes) == {"HasCodeInBody", "InnerProcess", "OuterProcess"}
    assert set(system.processes_with_recipes()) == {"HasCodeInBody", "InnerProcess"}
    assert system.processes["InnerProcess"].parent == "OuterProcess"

    has_code = system.processes["HasCodeInBody"]
    assert {i.object_name: i.quantity(units) for i in has_code.consumes} == {"Coal": 1.0}
    assert {i.object_name: i.quantity(units) for i in has_code.produces} == {"Heat": 5.0}

    assert validate(system) == []


def test_unrecognised_fence_is_a_warning_not_a_silent_drop(caplog):
    """The safety net the plan calls for: any `system:`-named fence this loader does
    not handle warns rather than silently disappearing."""
    units = UnitTable({**DEFAULT_UNITS.units, "kWh": Unit(1.0, "Energy")})
    parse_system_definitions(
        [FIXTURES / "structural-edge-cases.md"], units=units, validate=False
    )
    # None of the shipped fixtures actually trigger it; exercised directly in
    # test_loader.py instead. This test just pins that the fixture set as a
    # whole produces no such warning.
    assert "unrecognised directive" not in caplog.text


@pytest.mark.parametrize("units", [FLOWPROG_UNITS])
def test_energy_fixture_load_system_auto_validates_and_warns(caplog, units):
    import logging

    with caplog.at_level(logging.WARNING):
        parse_system_definitions(
            [FIXTURES / "energy" / "system-definitions.md"], units=units, validate=True
        )
    assert "Fuels" in caplog.text
