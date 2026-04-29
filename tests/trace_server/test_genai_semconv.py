"""Unit tests for GenAI semantic convention definitions."""

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
