# test-myst-mixed-units

This tests the YAML input of process recipes with different units

```{system:object} Apples
```

```{system:object} Blackberries
```

```{system:object} Crumble
```

```{system:process} P1
---
consumes: |
  Apples = 1 kg
  Blackberries = 0.3 kg
produces: |
  Crumble = 1 -
label: Making crumble
---

Using simple notation
```

```{system:process} P2
---
consumes: |
  {object: Apples, amount: 1, unit: kg}
  {object: Blackberries, amount: 0.3, unit: kg}
produces: |
  {object: Crumble, amount: 1.0, unit: -}
---

Using explicit dictionary notation
```
