# Parser fixtures and expected results

## Unit table required by these fixtures

The recycling fixture is all `kg` and needs only the default table. The energy
fixture needs two extra units, and the edge-case fixture needs `kWh`:

| Unit | Scale | Basis / metric |
|---|---|---|
| `kg` | 1 | `http://qudt.org/vocab/quantitykind/Mass` |
| `m2` | 1 | `http://qudt.org/vocab/quantitykind/Area` |
| `m3` | 1 | `http://qudt.org/vocab/quantitykind/Volume` |
| `-` | 1 | `http://qudt.org/vocab/quantitykind/Dimensionless` |
| `kWh` | 1 | `http://qudt.org/vocab/quantitykind/Energy` |
| `pkm` | 1 | `http://probs-lab.github.io/flowprog/metrics/PassengerKM` |

Note `pkm` maps to a **non-QUDT, project-specific URI** — the unit table must not
assume the QUDT namespace.

## `recycling/system-definitions.md`

Exercises `---` YAML option blocks, multi-line recipe items, an empty `consumes: |`,
and objects never referenced by any recipe (`OtherParts`, `MixedPCBWaste`, …).

- **6 objects:** `EoLTechnology`, `GoldAndPlastic`, `MixedPCBWaste`, `OtherParts`,
  `PCBs`, `PureGold`
- **5 processes:** `Disassembly`, `EoLProcessing`, `GoldAndPlasticProcessing`,
  `PCBProcess1`, `PCBProcess2`
- **`processes_with_recipes()` = all 5** (no aggregates in this fixture)
- **`validate()` = 0 problems**
- No `become_parent` nesting; no parents.

Full expected recipe (all `kg`, so basis = Mass for every object):

| Process | consumes | produces |
|---|---|---|
| `EoLProcessing` | — | `EoLTechnology` 1.0 |
| `Disassembly` | `EoLTechnology` 1.0 | `PCBs` 0.2, `OtherParts` 0.8 |
| `PCBProcess1` | `PCBs` 1.0 | `PureGold` 0.1, `MixedPCBWaste` 0.9 |
| `PCBProcess2` | `PCBs` 1.0 | `GoldAndPlastic` 0.3, `MixedPCBWaste` 0.7 |
| `GoldAndPlasticProcessing` | `GoldAndPlastic` 1.0 | `PureGold` 0.2, `MixedPCBWaste` 0.8 |

## `energy/system-definitions.md`

This fixture tests both option formats in one file, `become_parent` nesting,
non-mass units, recipe-less aggregates, and a genuine data bug.

- **5 objects:** `Electricity`, `Hydrogen`, `NaturalGas`, `Steel`, `TransportService`
- **8 processes:** `CCGT`, `ElectricCarUse`, `ElectricityGeneration`,
  `ElectricityUse`, `HydrogenElectrolysis`, `SteelProductionEAF`,
  `SteelProductionH2DRI`, `WindTurbine`
- **`processes_with_recipes()` = 6**, excluding the two aggregates
  `ElectricityGeneration` and `ElectricityUse`, which use the rST `:consumes:` form
  and declare connectivity with **no amounts**.
- **Parent relationships** (from `become_parent` + `end-sub-processes`):
  - `CCGT`, `WindTurbine` → `ElectricityGeneration`
  - `ElectricCarUse`, `SteelProductionEAF`, `SteelProductionH2DRI` → `ElectricityUse`
- **`validate()` = exactly 1 problem:** `ElectricityGeneration` references object
  `Fuels`, which is never declared.

Derived bases: `Electricity` → Energy, `TransportService` → PassengerKM, all
others → Mass.

## `structural-edge-cases.md`

Block-structure only; the cases where a regex/line-splitting parser is wrong.

- **4 objects:** `Coal`, `ColonFenceObject`, `Heat`, `Widget`
- **3 processes:** `HasCodeInBody`, `InnerProcess`, `OuterProcess`
- **`processes_with_recipes()` = 2:** `HasCodeInBody`, `InnerProcess`
- **Parent:** `InnerProcess` → `OuterProcess`
- `HasCodeInBody`'s body contains a ```` ```python ```` block containing a literal
  triple-backtick; its recipe must still be `Coal` 1 kg → `Heat` 5 kWh.

