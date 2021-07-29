# test-basic

This tests the YAML input of process recipes.

```{system:process} P1
---
consumes: |
  Apples = 0.7 kg
  Blackberries = 0.3 kg
produces: |
  Crumble = 1.0 kg
label: Making crumble
---

Using simple notation
```

```{system:process} P2
---
consumes: |
  {object: Apples, amount: 0.7, unit: kg}
  {object: Blackberries, amount: 0.3, unit: kg}
produces: |
  {object: Crumble, amount: 1.0, unit: kg}
---

Using explicit dictionary notation
```

```{system:process} P3
---
defs: |
  apple_fraction = 0.7
consumes: |
  {object: Apples, amount: apple_fraction, unit: kg}
  {object: Blackberries, amount: 1 - apple_fraction, unit: kg}
produces: |
  {object: Crumble, amount: 1.0, unit: kg}
---

Using defs and expressions
```
