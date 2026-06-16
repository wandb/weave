"""Unit tests for GenAI semantic convention definitions."""

from weave.trace_server.agents import semconv


def test_semconv_registry_invariants() -> None:
    """Every defined Attribute is registered, exposed, and filterable columns
    only reference registered attributes.
    """
    defined_attrs = {
        value.key
        for name, value in vars(semconv).items()
        if name.isupper() and isinstance(value, semconv.Attribute)
    }
    registered_attrs = {attr.key for attr in semconv._DEFS}

    assert registered_attrs == defined_attrs
    assert set(semconv.ATTRIBUTES) == defined_attrs
    assert set(semconv.CANONICAL_KEY_TO_COLUMN).issubset(set(semconv.ATTRIBUTES))


def test_multi_alias_lookup_keys_priority_order() -> None:
    """``lookup_keys`` returns the canonical weave.* key first, then aliases
    in declared order, so extraction probes the canonical name before any
    parallel OTel form.
    """
    attr = semconv.Attribute(
        key="weave.example",
        type="string",
        description="synthetic example with multiple aliases",
        gen_ai_aliases=[
            "gen_ai.example.primary",
            "gen_ai.example.legacy",
            "gen_ai.example.experimental",
        ],
    )

    assert attr.lookup_keys == (
        "weave.example",
        "gen_ai.example.primary",
        "gen_ai.example.legacy",
        "gen_ai.example.experimental",
    )
