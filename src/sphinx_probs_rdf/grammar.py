"""The directive grammar: pure option parsers and option specs.

``PROCESS_OPTION_SPEC`` / ``OBJECT_OPTION_SPEC`` / ``CORE_PARAMETER_OPTIONS`` are the
option specs for ``system:process`` / ``system:object`` / ``system:parameter``
directives, in the ``{option_name: conversion_function}`` form docutils/MyST expect.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict

import yaml

# Note that these specific functions need to be used (checked by docutils by
# identify)
from docutils.parsers.rst.directives import (
    flag as _flag,
    unchanged as _unchanged,
    unchanged_required as _unchanged_required,
)

# ---------------------------------------------------------------------------------
# Option value parsers
# ---------------------------------------------------------------------------------


def parse_yaml_value(value):
    """Parse an option's raw text as arbitrary YAML (e.g. ``:range: [0.449, 0.495]``)"""
    if value is None:
        return None
    try:
        return yaml.safe_load(value)
    except yaml.YAMLError as err:
        raise ValueError(f"invalid YAML: {err}") from err


def parse_yaml_mapping(value):
    """Parse an option's raw text as a YAML mapping."""
    data = parse_yaml_value(value)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError("expected a YAML mapping")
    return data


def parse_composed_of(value):
    """Parse composed_of option."""
    if value is None:
        return []
    return [x.strip() for x in value.split()]


def parse_consumes_or_produces(value):
    """Parse consumes and products options."""
    if value is None:
        return []

    if "\n" in value or value.strip().startswith("{"):
        # Complex definitions, one per line -- or a single YAML-style definition
        items = [_parse_item(x.strip()) for x in value.strip().split("\n")]
    else:
        # A space-separated list of basic names
        items = [{"object": x.strip()} for x in value.split()]

    return items


ITEM_STRING_REGEX = re.compile(
    r"""
    ^\s*
    ([^= \t]+)               # -> Object type
    \s*
    (?:                      # Optional amount section
        =
        \s*
        ([0-9.eE-]+)         # -> Amount
        (?:                  # Optional unit section
            \s*
            ([^{]+?)         # -> Unit
            \s*
        )?
    )?
    ({.+})?                  # Optional YAML section
    $
""",
    re.VERBOSE,
)


def _parse_item(item):
    if isinstance(item, str):
        match = ITEM_STRING_REGEX.match(item)
        if match:
            extra = {}
            if match.group(4):
                try:
                    extra = yaml.safe_load(match.group(4))
                except yaml.YAMLError:
                    pass
            return {
                "object": match.group(1),
                "amount": float(match.group(2)) if match.group(2) else None,
                "unit": match.group(3),
                **extra,
            }
        else:
            # Try parsing whole thing as yaml dict
            try:
                d = yaml.safe_load(item)
                if not isinstance(d, dict):
                    raise ValueError("YAML data should be dictionary")
                return d
            except yaml.YAMLError:
                pass

            return item
    elif isinstance(item, list):
        return {
            "object": item[0],
            "amount": item[1],
            "unit": item[2],
        }
    elif isinstance(item, dict):
        return item
    else:
        raise ValueError("cannot parse item: %r" % item)


def expand_consumes_produces_amounts(defs, *items):
    """Expand Python expressions in cleaned-up options."""
    defs_ns: Dict[str, Any] = {}
    exec(defs, defs_ns)

    # Expand amounts in produces/consumes lists using the defs
    result = [[eval_amount(x, defs_ns) for x in item_list] for item_list in items]

    return result


def eval_amount(item, namespace):
    """Evaluate expressions within the "amount" field of the item.

    WARNING: not safe for use with untrusted input!
    """
    if isinstance(item, dict) and isinstance(item.get("amount"), str):
        amount = eval(item["amount"], {}, dict(namespace))
        return {**item, "amount": amount}
    return item


def parse_traded(value):
    """Check the value of the :traded: option is valid."""
    if value is None:
        return (False, False)
    value = value.lower()
    imp = value.startswith("import")
    exp = value.startswith("export")
    if value in ("both", "yes", "true") or "import" in value and "export" in value:
        imp = exp = True
    return (imp, exp)


def parse_equivalent(value):
    """Convert list of uris."""
    if value is None:
        value = ""
    items = [x.strip() for x in value.split()]
    return items


# ---------------------------------------------------------------------------------
# Option specs
# ---------------------------------------------------------------------------------

OptionSpec = Dict[str, Callable[[str], Any]]

#: Option spec for ``system:process``.
PROCESS_OPTION_SPEC: OptionSpec = {
    "label": _unchanged_required,
    "become_parent": _flag,
    "consumes": parse_consumes_or_produces,
    "produces": parse_consumes_or_produces,
    "composed_of": parse_composed_of,
    "defs": _unchanged,
    "per": parse_yaml_mapping,
    "balance": parse_yaml_value,
    # Arbitrary YAML mapping, for a downstream project's own use.
    "extra": parse_yaml_mapping,
}

#: Option spec for ``system:object``.
OBJECT_OPTION_SPEC: OptionSpec = {
    "label": _unchanged,
    "become_parent": _flag,
    "parent_object": _unchanged,
    "composed_of": parse_composed_of,
    "traded": parse_traded,
    "equivalent": parse_equivalent,
    "basis": _unchanged,
    "factors": parse_yaml_mapping,
    # See PROCESS_OPTION_SPEC's "extra" above.
    "extra": parse_yaml_mapping,
}

#: Option spec for ``system:parameter``.
CORE_PARAMETER_OPTIONS: OptionSpec = {
    "label": _unchanged,
    "value": _unchanged,
    "range": parse_yaml_value,
    "source": _unchanged,
}
