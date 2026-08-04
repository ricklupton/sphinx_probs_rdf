---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.13.8
kernelspec:
  display_name: Python 3 (ipykernel)
  language: python
  name: python3
--- 

# Energy system definitions

Exercises: **both option formats in one file** (rST `:consumes:` field lists on the
aggregate processes, `---` YAML blocks elsewhere), `become_parent` nesting closed by
`end-sub-processes`, non-mass units (`kWh`, `pkm`) requiring a custom unit table,
recipe-less aggregate processes, and a recipe referencing an **undeclared** object
(`Fuels`) that `validate()` must report.

## Energy production

```{system:process} ElectricityGeneration
:consumes: Fuels
:produces: Electricity
:become_parent: true
```

```{system:process} CCGT
---
label: CCGT
consumes: |
  NaturalGas                               = 1.0 kg
produces: |
  Electricity                              = 2.3 kWh
---

Explanation of the process goes here.
```

```{system:process} WindTurbine
---
label: Wind turbine
consumes: |
produces: |
  Electricity                              = 1.0 kWh
---

A wind turbine generates electricity.
```

```{end-sub-processes}
```

### Object definitions

```{system:object} NaturalGas
```
```{system:object} Electricity
```

## Hydrogen production

```{system:process} HydrogenElectrolysis
---
label: Hydrogen electrolysis
consumes: |
  Electricity                              = 1.3 kWh
produces: |
  Hydrogen                                 = 1.0 kg
---
```

### Object definitions

```{system:object} Hydrogen
```

## Energy use

```{system:process} ElectricityUse
:consumes: Electricity Hydrogen
:produces: Steel
:become_parent: true
```

```{system:process} SteelProductionEAF
---
label: Steel EAF
consumes: |
  Electricity                              = 5.6 kWh
produces: |
  Steel                                    = 1.0 kg
---
```

```{system:process} SteelProductionH2DRI
---
label: Steel DRI from H2
consumes: |
  Hydrogen                                 = 2.2 kg
produces: |
  Steel                                    = 1.0 kg
---
```

```{system:process} ElectricCarUse
---
label: Electric car use
consumes: |
  Electricity                              = 2.3 kWh
produces: |
  TransportService                         = 1.0 pkm
---
```

```{end-sub-processes}
```


### Object definitions

```{system:object} Steel
```

```{system:object} TransportService
```
