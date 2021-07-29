"""Test different ways of passing options are interpreted correctly."""

import pytest

from sphinx_probs_rdf.directives import (
    parse_composed_of,
    parse_consumes_or_produces,
    eval_amount,
    expand_consumes_produces_amounts,
)


def test_parse_composed_of():
    assert parse_composed_of("Child") == ["Child"]
    assert parse_composed_of("Child1  Child2 ") == ["Child1", "Child2"]


def test_parse_consumes_or_produces_simple():
    assert parse_consumes_or_produces("ObjectA ObjectB") == [
        {"object": "ObjectA"},
        {"object": "ObjectB"},
    ]


def test_parse_directive_options_complex():
    # These should all work in the same way
    consumes = """
        IronOre = 0.2 kg
        IronOre = 0.2 {"unit": "kg"}
        IronOre {"amount": 0.2, "unit": "kg"}
        {"object": "IronOre", "amount": 0.2, "unit": "kg"}
    """
    parsed = parse_consumes_or_produces(consumes)

    for item in parsed:
        assert item == {"object": "IronOre", "amount": 0.2, "unit": "kg"}


def test_parse_directive_options_with_extra():
    consumes = """
    IronOre = 0.2 kg {comment: "hello"}
    """
    parsed = parse_consumes_or_produces(consumes)

    assert parsed == [
        {"object": "IronOre", "amount": 0.2, "unit": "kg", "comment": "hello"}
    ]


def test_eval_amount():
    item = {"object": "IronOre", "amount": 0.2, "unit": "kg"}
    assert eval_amount(item, {})["amount"] == 0.2

    item = {"object": "IronOre", "amount": "2 * 0.1", "unit": "kg"}
    assert eval_amount(item, {})["amount"] == 0.2

    item = {"object": "IronOre", "amount": "k * 0.1", "unit": "kg"}
    assert eval_amount(item, {"k": 2})["amount"] == 0.2


def test_eval_amount_fails():
    item = {"object": "IronOre", "amount": "k * 0.1", "unit": "kg"}
    with pytest.raises(NameError):
        eval_amount(item, {})

    item = {"object": "IronOre", "amount": "k * ", "unit": "kg"}
    with pytest.raises(SyntaxError):
        eval_amount(item, {})


def test_expand_directives_options_literals():
    item = {"object": "IronOre", "amount": "2 * 0.1", "unit": "kg"}
    expanded, = expand_consumes_produces_amounts("", [item])
    assert expanded == [
        {"object": "IronOre", "amount": 0.2, "unit": "kg"},
    ]


def test_expand_directives_options_defs():
    defs = "a = 1\nb = 2\nk = a * b"
    item = {"object": "IronOre", "amount": "k * 0.1", "unit": "kg"}
    expanded, = expand_consumes_produces_amounts(defs, [item])
    assert expanded == [
        {"object": "IronOre", "amount": 0.2, "unit": "kg"},
    ]


def test_expand_directives_options_slightly_safe():
    # NB not fully safe on untrusted input -- there are ways round it
    defs = "del options"
    item = {"object": "IronOre", "amount": "k * 0.1", "unit": "kg"}
    with pytest.raises(NameError):
        expand_consumes_produces_amounts(defs, [item])
