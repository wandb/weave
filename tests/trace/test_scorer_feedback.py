from __future__ import annotations

import pytest
from pydantic import ValidationError

from weave.trace.scorer_feedback import (
    SCORER_RATING_MAP_KEY,
    ScorerFeedbackColumns,
    ScorerOutputGroup,
    ScorerOutputSchema,
)


@pytest.mark.parametrize(
    ("raw", "exc"),
    [
        ({"value": "good"}, None),
        ({"value": 0.5}, None),
        ({"value": "good", "reason": "ok", "confidence": 0.9}, None),
        ({}, ValidationError),
        ({"value": ["a", "b"]}, ValidationError),
        ({"value": "a" * 37}, ValidationError),
        ({"value": "ok", "reason": "x" * 257}, ValidationError),
        ({"value": 1.5}, ValidationError),
        ({"value": 1}, None),
        ({"value": "0.5"}, None),
    ],
)
def test_scorer_output_schema_validation(
    raw: dict, exc: type[Exception] | None
) -> None:
    if exc is None:
        out = ScorerOutputSchema.model_validate(raw)
        for field, value in raw.items():
            assert getattr(out, field) == value
    else:
        with pytest.raises(exc):
            ScorerOutputSchema.model_validate(raw)


def test_union_discrimination_routes_to_correct_column() -> None:
    int_group = ScorerOutputGroup.from_scorer_output({"value": 1})
    int_cols = ScorerFeedbackColumns.from_scorer_output_group(int_group)
    assert int_cols.tags == []
    assert int_cols.ratings == {SCORER_RATING_MAP_KEY: 1.0}

    str_group = ScorerOutputGroup.from_scorer_output({"value": "0.5"})
    str_cols = ScorerFeedbackColumns.from_scorer_output_group(str_group)
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
def test_scorer_output_group_formats(
    raw: object, expected_scores: list[dict]
) -> None:
    group = ScorerOutputGroup.from_scorer_output(raw)
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
def test_scorer_output_group_rejects(
    raw: object, exc: type[Exception]
) -> None:
    with pytest.raises(exc):
        ScorerOutputGroup.from_scorer_output(raw)


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
                "ratings": {SCORER_RATING_MAP_KEY: 1.0},
                "rating_reasons": {SCORER_RATING_MAP_KEY: "perfect"},
                "rating_confidences": {SCORER_RATING_MAP_KEY: 0.8},
            },
            None,
        ),
        ([{"value": "a"}, {"value": "b"}], {"tags": ["a", "b"]}, None),
        ([{"value": 0.2}, {"value": 0.4}], None, ValueError),
        ([], {"tags": [], "ratings": {}}, None),
    ],
)
def test_columns_from_scorer_output_group(
    outputs: list[dict], expected: dict | None, exc: type[Exception] | None
) -> None:
    group = ScorerOutputGroup.from_scorer_output(outputs)
    if exc is None:
        cols = ScorerFeedbackColumns.from_scorer_output_group(group)
        assert expected is not None
        for field, value in expected.items():
            assert getattr(cols, field) == value
    else:
        with pytest.raises(exc):
            ScorerFeedbackColumns.from_scorer_output_group(group)
