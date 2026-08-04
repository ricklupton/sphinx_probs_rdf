---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
---

# Structural edge cases

Parser fixture for block structure only — the cases where a regex/line-splitting
parser gives wrong answers but a CommonMark tokeniser does not.

Exercises: jupytext front matter; a fenced code block *inside* a directive body
containing a literal triple-backtick; `:::` colon fences; nesting with mixed fence
lengths (3/4/5).

## Code block inside a directive body

````{system:process} HasCodeInBody
---
consumes: |
  Coal = 1 kg
produces: |
  Heat = 5 kWh
---
This process has a fenced code block in its docs. A naive ``` splitter would treat
the inner fence as the end of the directive:

```python
x = "```"  # not the end of anything
```

Still inside HasCodeInBody.
````

## Colon fence

:::{system:object} ColonFenceObject
A directive written with colon fences instead of backticks.
:::

## Nesting with mixed fence lengths

`````{system:process} OuterProcess
:become_parent: true

A genuinely nested process definition inside the body:

````{system:process} InnerProcess
---
consumes: |
  Heat = 2 kWh
produces: |
  Widget = 1 -
---
````
`````

```{end-sub-processes}
```

## Object definitions

```{system:object} Coal
```
```{system:object} Heat
```
```{system:object} Widget
```
