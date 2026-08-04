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

# Recycling system definitions

Exercises: `---`-delimited YAML option blocks, multi-line recipe items, an empty
`consumes: |` block, and objects that are never referenced by a recipe.

## EoL technology

```{system:process} EoLProcessing
---
consumes: |
produces: |
  EoLTechnology                            = 1 kg
---
```

```{system:object} EoLTechnology
```

```{system:process} Disassembly
---
consumes: |
  EoLTechnology                            = 1 kg
produces: |
  PCBs                                     = 0.2 kg
  OtherParts                               = 0.8 kg
---

```

```{system:object} PCBs
```

```{system:object} OtherParts
```

## PCB recycling

```{system:process} PCBProcess1
---
consumes: |
  PCBs                                     = 1 kg
produces: |
  PureGold                                 = 0.1 kg
  MixedPCBWaste                            = 0.9 kg
---
```

```{system:process} PCBProcess2
---
consumes: |
  PCBs                                     = 1 kg
produces: |
  GoldAndPlastic                           = 0.3 kg
  MixedPCBWaste                            = 0.7 kg
---
```

```{system:process} GoldAndPlasticProcessing
---
consumes: |
  GoldAndPlastic                           = 1 kg
produces: |
  PureGold                                 = 0.2 kg
  MixedPCBWaste                            = 0.8 kg
---
```

```{system:object} PureGold
```

```{system:object} GoldAndPlastic
```

```{system:object} MixedPCBWaste
You can explain more about the objects too here.
```
