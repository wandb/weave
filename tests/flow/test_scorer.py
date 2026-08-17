from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from weave.flow.scorer import Scorer, auto_summarize
from weave.trace.object_record import ObjectRecord
from weave.trace.vals import WeaveDict, WeaveObject


class NestedParams(BaseModel):
    temperature: float | None = None
    top_p: float | None = None


class ScorerWithNestedModel(Scorer):
    default_params: NestedParams | None = None

    def score(self, *, output, **kwargs):
        return True


def _make_weave_object(attrs: dict) -> WeaveObject:
    record = ObjectRecord(attrs)
    server = MagicMock()
    return WeaveObject(record, ref=None, server=server, root=None)


def test_from_obj_rejects_metadata_keys():
    """_class_name and _bases from ObjectRecord cause extra_forbidden errors."""
    obj = _make_weave_object(
        {
            "name": "s",
            "_class_name": "ScorerWithNestedModel",
            "_bases": ["Scorer", "Object", "BaseModel"],
        }
    )
    scorer = ScorerWithNestedModel.from_obj(obj)
    assert scorer.name == "s"


def test_from_obj_unwraps_nested_weave_dict():
    """A nested WeaveDict with metadata must be unwrapped to a plain dict for Pydantic."""
    server = MagicMock()
    params = WeaveDict(
        {
            "_type": "NestedParams",
            "_class_name": "NestedParams",
            "_bases": ["BaseModel"],
            "temperature": 0.5,
            "top_p": None,
        },
        server=server,
        ref=None,
    )
    obj = _make_weave_object({"name": "s", "default_params": params})
    scorer = ScorerWithNestedModel.from_obj(obj)
    assert scorer.default_params == NestedParams(temperature=0.5, top_p=None)


def test_from_obj_unwraps_nested_weave_object():
    """A nested WeaveObject (e.g. LLMStructuredCompletionModelDefaultParams) must be
    unwrapped to a dict so Pydantic can validate it as a model instance.
    """
    server = MagicMock()
    inner = WeaveObject(
        ObjectRecord(
            {
                "_class_name": "NestedParams",
                "_bases": ["BaseModel"],
                "temperature": 0.9,
                "top_p": 0.8,
            }
        ),
        ref=None,
        server=server,
        root=None,
    )
    obj = _make_weave_object({"name": "s", "default_params": inner})
    scorer = ScorerWithNestedModel.from_obj(obj)
    assert scorer.default_params == NestedParams(temperature=0.9, top_p=0.8)


# auto_summarize picks its branch from the type of data[0]. A list whose first
# row is a pydantic BaseModel but whose later rows are WeaveDicts (dict
# subclasses, e.g. after a trace-server roundtrip) used to crash with
# AttributeError, because model_dump was called on every item. The fix guards
# the conversion per element.


class _Score(BaseModel):
    correct: bool
    confidence: float


def _make_weave_dict(payload: dict) -> WeaveDict:
    return WeaveDict(payload, server=MagicMock(), ref=None)


@pytest.mark.trace_server
def test_auto_summarize_mixed_basemodel_and_weave_dict():
    """First row is a BaseModel, later rows are WeaveDicts: aggregate, don't crash."""
    data = [
        _Score(correct=True, confidence=0.9),
        _make_weave_dict({"correct": False, "confidence": 0.4}),
        _make_weave_dict({"correct": True, "confidence": 0.7}),
    ]
    result = auto_summarize(data)
    assert result["correct"] == {"true_count": 2, "true_fraction": 2 / 3}
    assert abs(result["confidence"]["mean"] - (0.9 + 0.4 + 0.7) / 3) < 1e-9


# A row whose model or scorer raised is recorded as an empty dict, which
# auto_summarize used to read as "no value here" rather than "this row failed".


class _Passed(BaseModel):
    passed: bool


@pytest.mark.trace_server
@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (
            [{"correct": True}, {"correct": True}, {}, {}],
            {"correct": {"true_count": 2, "true_fraction": 0.5}},
        ),
        (
            [{}, {}, {"correct": True}, {"correct": True}],
            {"correct": {"true_count": 2, "true_fraction": 0.5}},
        ),
        (
            [_Passed(passed=True), _Passed(passed=True), {}, {}],
            {"passed": {"true_count": 2, "true_fraction": 0.5}},
        ),
        (
            [{}, {}, _Passed(passed=True), _Passed(passed=True)],
            {"passed": {"true_count": 2, "true_fraction": 0.5}},
        ),
        ([True, True, {}, {}], {"true_count": 2, "true_fraction": 0.5}),
        ([{}, {}, True, True], {"true_count": 2, "true_fraction": 0.5}),
        (
            [{"a": {"b": True}}, {}],
            {"a": {"b": {"true_count": 1, "true_fraction": 0.5}}},
        ),
        (
            [{}, {"a": {"b": True}}],
            {"a": {"b": {"true_count": 1, "true_fraction": 0.5}}},
        ),
    ],
    ids=[
        "dict-last",
        "dict-first",
        "basemodel-last",
        "basemodel-first",
        "bool-last",
        "bool-first",
        "nested-last",
        "nested-first",
    ],
)
def test_auto_summarize_counts_unscored_rows(data, expected):
    """An unscored row stays in the denominator and never picks the branch, at any position."""
    assert auto_summarize(data) == expected


@pytest.mark.trace_server
@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ([1.0, 1.0, {}, {}], {"mean": 1.0}),
        ([{}, {}, 1.0, 1.0], {"mean": 1.0}),
        ([{"distance": 2.0}, {}, {}], {"distance": {"mean": 2.0}}),
    ],
    ids=["bare-last", "bare-first", "nested"],
)
def test_auto_summarize_numeric_scores_with_unscored_rows(data, expected):
    """A numeric column with unscored rows averages the scored values instead of raising."""
    assert auto_summarize(data) == expected


@pytest.mark.trace_server
def test_auto_summarize_keeps_nested_empty_dicts():
    """Only a top-level empty dict is an unscored row; a nested one is a real value."""
    data = [
        {"metadata": {"usage": {}}},
        {"metadata": {"usage": {"input_tokens": 10, "ok": True}}},
    ]
    assert auto_summarize(data) == {
        "metadata": {
            "usage": {
                "input_tokens": {"mean": 10.0},
                "ok": {"true_count": 1, "true_fraction": 1.0},
            }
        }
    }


@pytest.mark.trace_server
@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ([True, False], {"true_count": 1, "true_fraction": 0.5}),
        (
            [{"correct": True}, {"correct": None}],
            {"correct": {"true_count": 1, "true_fraction": 1.0}},
        ),
        ([{}, {}], None),
        ([None, None], None),
        ([], {}),
    ],
    ids=["bool", "none-leaf", "all-unscored", "all-none", "empty"],
)
def test_auto_summarize_results_unchanged(data, expected):
    """Values the current implementation already returns; the unscored count must not move them."""
    assert auto_summarize(data) == expected
