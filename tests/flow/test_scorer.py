from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from weave.flow.scorer import Scorer, _import_numpy, auto_summarize
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


# An evaluation records a row whose model or scorer raised as an empty dict:
# Evaluation.get_eval_results backfills `{}` for every scorer that produced no
# result. auto_summarize used to read that empty dict as "no value here", so the
# row fell out of the boolean denominator, crashed the numeric branch, and chose
# the branch for the whole column when it came first. A nested empty dict is an
# ordinary value and must keep aggregating exactly as before.


class _Passed(BaseModel):
    passed: bool


@pytest.mark.trace_server
def test_auto_summarize_unscored_rows_stay_in_the_denominator():
    """Two of four rows produced no score, so the fraction is 2/4, not 2/2."""
    data = [{"correct": True}, {"correct": True}, {}, {}]
    assert auto_summarize(data) == {"correct": {"true_count": 2, "true_fraction": 0.5}}


@pytest.mark.trace_server
def test_auto_summarize_unscored_rows_with_basemodel_scores():
    """A BaseModel score reaches the dict branch via model_dump and needs the same count."""
    data = [_Passed(passed=True), _Passed(passed=True), {}, {}]
    assert auto_summarize(data) == {"passed": {"true_count": 2, "true_fraction": 0.5}}


@pytest.mark.trace_server
@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ([{}, {"correct": True}], {"correct": {"true_count": 1, "true_fraction": 0.5}}),
        (
            [{}, _Passed(passed=True)],
            {"passed": {"true_count": 1, "true_fraction": 0.5}},
        ),
        ([{}, True], {"true_count": 1, "true_fraction": 0.5}),
        ([{}, 1.0], {"mean": 1.0}),
    ],
)
def test_auto_summarize_unscored_first_row_does_not_choose_the_branch(data, expected):
    """The branch follows the first row that has a score, so the metric survives."""
    assert auto_summarize(data) == expected


@pytest.mark.trace_server
@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ([1.0, 1.0, {}, {}], {"mean": 1.0}),
        ([{"distance": 2.0}, {}, {}], {"distance": {"mean": 2.0}}),
        ([{"distance": 1.0}, {"distance": None}, {}, {}], {"distance": {"mean": 1.0}}),
    ],
)
def test_auto_summarize_numeric_scores_with_unscored_rows(data, expected):
    """A numeric column mixed with unscored rows averages the numbers instead of raising."""
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
)
def test_auto_summarize_results_unchanged(data, expected):
    """Values the current implementation already returns; the unscored count must not move them."""
    assert auto_summarize(data) == expected


@pytest.mark.trace_server
def test_auto_summarize_float_mean_matches_the_numpy_path():
    """Filtering the numeric column must not change which mean is computed: numpy and
    pure Python disagree in the last bit, so both must keep averaging the same values.
    """
    data = [0.1, 0.2, 0.3]
    np = _import_numpy()
    expected = np.mean(data).item() if np else sum(data) / len(data)
    assert auto_summarize(data) == {"mean": expected}
