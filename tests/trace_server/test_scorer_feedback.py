from __future__ import annotations

import pytest
from pydantic import ValidationError

from weave.trace_server.scorer_feedback import (
    _SCORER_RATING_MAP_KEY,
    ScorerColumns,
    ScorerLlmOutputGroup,
    ScorerLlmOutputSchema,
)


@pytest.mark.parametrize(
    ("raw", "exc"),
    [
        # Happy path: a tag, a rating, with optional reason/confidence.
        ({"value": "good"}, None),
        ({"value": 0.5}, None),
        ({"value": "good", "reason": "ok", "confidence": 0.9}, None),
        # `value` is required.
        ({}, ValidationError),
        # Multi-tag/rating is a list of separate outputs, not a list value.
        ({"value": ["a", "b"]}, ValidationError),
        # Length caps (tag <= 36 chars, reason <= 256 chars).
        ({"value": "a" * 37}, ValidationError),
        ({"value": "ok", "reason": "x" * 257}, ValidationError),
        # Rating must be in [0, 1].
        ({"value": 1.5}, ValidationError),
        # Booleans should not be coerced into numeric ratings/confidences.
        ({"value": True}, ValidationError),
        ({"value": "ok", "confidence": False}, ValidationError),
        # JSON int coerces to float and is routed as a rating.
        ({"value": 1}, None),
        # Stringified number stays a string and is routed as a tag.
        ({"value": "0.5"}, None),
    ],
)
def test_scorer_llm_output_schema_validation(
    raw: dict, exc: type[Exception] | None
) -> None:
    if exc is None:
        out = ScorerLlmOutputSchema.model_validate(raw)
        for field, value in raw.items():
            assert getattr(out, field) == value
    else:
        with pytest.raises(exc):
            ScorerLlmOutputSchema.model_validate(raw)


def test_union_discrimination_routes_to_correct_column() -> None:
    int_group = ScorerLlmOutputGroup.from_raw_output({"value": 1})
    int_cols = ScorerColumns.from_scorer_llm_output_group(int_group)
    assert int_cols.tags == []
    assert int_cols.ratings == {_SCORER_RATING_MAP_KEY: 1.0}

    str_group = ScorerLlmOutputGroup.from_raw_output({"value": "0.5"})
    str_cols = ScorerColumns.from_scorer_llm_output_group(str_group)
    assert str_cols.tags == ["0.5"]
    assert str_cols.ratings == {}


@pytest.mark.parametrize(
    ("raw", "expected_scores"),
    [
        ({"value": "ok"}, [{"value": "ok"}]),
        ([{"value": "ok"}, {"value": 0.5}], [{"value": "ok"}, {"value": 0.5}]),
        (
            {"scores": [{"value": 0.9}, {"value": "tag"}]},
            [{"value": 0.9}, {"value": "tag"}],
        ),
        ([], []),
    ],
)
def test_group_from_raw_output_formats(
    raw: object, expected_scores: list[dict]
) -> None:
    group = ScorerLlmOutputGroup.from_raw_output(raw)
    assert len(group.scores) == len(expected_scores)
    for got, want in zip(group.scores, expected_scores, strict=True):
        for field, value in want.items():
            assert getattr(got, field) == value


@pytest.mark.parametrize(
    ("raw", "exc"),
    [
        ("not a payload", TypeError),
        (42, TypeError),
        (None, TypeError),
        ({"scores": "not a list"}, ValidationError),
        ([{"value": "ok"}, {"value": 1.5}], ValidationError),
    ],
)
def test_group_from_raw_output_rejects(raw: object, exc: type[Exception]) -> None:
    with pytest.raises(exc):
        ScorerLlmOutputGroup.from_raw_output(raw)


@pytest.mark.parametrize(
    ("outputs", "expected", "exc"),
    [
        ([{"value": "High Quality"}], {"tags": ["high-quality"]}, None),
        (
            [{"value": "good", "reason": "nice", "confidence": 0.7}],
            {
                "tags": ["good"],
                "tag_reasons": {"good": "nice"},
                "tag_confidences": {"good": 0.7},
            },
            None,
        ),
        (
            [{"value": 1.0, "reason": "perfect", "confidence": 0.8}],
            {
                "ratings": {_SCORER_RATING_MAP_KEY: 1.0},
                "rating_reasons": {_SCORER_RATING_MAP_KEY: "perfect"},
                "rating_confidences": {_SCORER_RATING_MAP_KEY: 0.8},
            },
            None,
        ),
        ([{"value": "a"}, {"value": "b"}], {"tags": ["a", "b"]}, None),
        ([{"value": 0.2}, {"value": 0.4}], None, ValueError),
        ([], {"tags": [], "ratings": {}}, None),
    ],
)
def test_columns_from_scorer_llm_output_group(
    outputs: list[dict], expected: dict | None, exc: type[Exception] | None
) -> None:
    group = ScorerLlmOutputGroup.from_raw_output(outputs)
    if exc is None:
        cols = ScorerColumns.from_scorer_llm_output_group(group)
        assert expected is not None
        for field, value in expected.items():
            assert getattr(cols, field) == value
    else:
        with pytest.raises(exc):
            ScorerColumns.from_scorer_llm_output_group(group)


def test_columns_to_feedback_fields() -> None:
    cols = ScorerColumns.from_raw_output(
        [{"value": "Safety Risk", "reason": "blocked", "confidence": 0.7}]
    )

    assert cols.to_feedback_fields() == {
        "scorer_tags": ["safety-risk"],
        "scorer_tag_reasons": {"safety-risk": "blocked"},
        "scorer_tag_confidences": {"safety-risk": 0.7},
        "scorer_ratings": {},
        "scorer_rating_reasons": {},
        "scorer_rating_confidences": {},
    }
