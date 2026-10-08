# test-namespaces

```{system:object} Steel
---
basis: mass
---
```

```{system:object} Sheet
---
basis: mass
---
```

```{system:process} Sale
---
consumes: |
  _:HotBand = 1 kg
produces: |
  Sheet = 1 kg
---
The hot band this sale takes is wired when a model is linked.
```

```{system:process} Cast
---
consumes: |
  Steel = 1 kg
produces: |
  Sheet = 1 kg
---
A process with the same local name as the fragment's.
```

```{include} _fragments/casting.md
```

```{system:object} AfterTheInclude
---
basis: mass
---
```

See {system:ref}`frag:Cast` and {system:ref}`base:Cast`.
