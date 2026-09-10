"""Unit tests for GenAI semantic convention definitions."""

from weave.shared import otel_span_attrs
from weave.trace_server.agents import semconv


def test_all_attribute_constants_are_registered() -> None:
    defined_attrs = {
        value.key
        for name, value in vars(semconv).items()
        if name.isupper() and isinstance(value, semconv.Attribute)
    }

    registered_attrs = {attr.key for attr in semconv._DEFS}

    assert registered_attrs == defined_attrs
    assert set(semconv.ATTRIBUTES) == defined_attrs


def test_filterable_columns_reference_registered_attributes() -> None:
    assert set(semconv.CANONICAL_KEY_TO_COLUMN).issubset(set(semconv.ATTRIBUTES))


def test_parent_call_keys_match_the_client_side_constants() -> None:
    """The SDK writes these keys from its own copy of the constant, since the
    client cannot import the trace server. If the two spellings drift, the
    attributes land in the custom-attribute overflow map instead of the
    promoted columns, and every query returns zero rows without an error.
    """
    assert semconv.PARENT_CALL_ID.key == otel_span_attrs.PARENT_CALL_ID_SPAN_ATTR
    assert (
        semconv.PARENT_CALL_TRACE_ID.key
        == otel_span_attrs.PARENT_CALL_TRACE_ID_SPAN_ATTR
    )


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
