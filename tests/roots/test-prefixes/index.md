# test-prefixes

```{system:object} Apples
```

```{system:object} :Blackberries
```

```{system:object} prefix:Crumble
```

```{system:process} P1
---
consumes: |
  Apples = 0.7 kg
  :Blackberries = 0.3 kg
produces: |
  prefix:Crumble = 1.0 kg
label: Making crumble
---

Using simple notation
```

```{system:process} prefix:P2
---
consumes: |
  {object: Apples, amount: 0.7, unit: kg}
  {object: ":Blackberries", amount: 0.3, unit: kg}
produces: |
  {object: "prefix:Crumble", amount: 1.0, unit: kg}
---

Using explicit dictionary notation
```
