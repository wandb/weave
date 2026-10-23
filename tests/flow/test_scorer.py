import asyncio
import json
import math
from fractions import Fraction
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

import weave
from weave.flow.scorer import Scorer, apply_scorer_async, auto_summarize
from weave.trace.box import BoxedFloat, BoxedInt, BoxedStr
from weave.trace.object_record import ObjectRecord, pydantic_object_record
from weave.trace.objectify import maybe_objectify, register_object
from weave.trace.vals import WeaveDict, WeaveObject


@weave.op
def _binary_correct(output):
    return output


def _bayes_scorer(**kwargs):
    return weave.BayesAtNScorer(
        scorer=_binary_correct,
        question_ids=["q0", "q1"],
        trial_ids=[0, 1],
        **kwargs,
    )


def _trial_rows(outcomes):
    return [
        {"question_id": f"q{question}", "trial_id": trial, "correct": value}
        for question, values in enumerate(outcomes)
        for trial, value in enumerate(values)
    ]


@pytest.mark.trace_server
@pytest.mark.parametrize(
    ("outcomes", "variance"),
    [([[0, 0], [1, 1]], Fraction(3, 160)), ([[0, 1], [0, 1]], Fraction(1, 40))],
)
def test_bayes_at_n_preserves_question_posteriors(outcomes, variance):
    scorer = _bayes_scorer()
    expected = {"posterior_mean": 0.5, "posterior_sd": math.sqrt(variance)}
    assert scorer.summarize(_trial_rows(outcomes)) == pytest.approx(expected)
    assert scorer.summarize(list(reversed(_trial_rows(outcomes)))) == pytest.approx(
        expected
    )


@pytest.mark.trace_server
@pytest.mark.parametrize("correct", [False, True])
def test_bayes_at_n_one_trial(correct):
    scorer = weave.BayesAtNScorer(
        scorer=_binary_correct, question_ids=["q0"], trial_ids=[0]
    )
    assert scorer.summarize(_trial_rows([[correct]])) == pytest.approx(
        {
            "posterior_mean": float(Fraction(2 if correct else 1, 3)),
            "posterior_sd": math.sqrt(Fraction(1, 18)),
        }
    )


@pytest.mark.trace_server
def test_bayes_at_n_representative_cohort():
    outcomes = [[0, 1, 1, 0, 1], [1, 1, 1, 1, 1], [0, 0, 0, 0, 0]]
    means = [Fraction(4, 7), Fraction(6, 7), Fraction(1, 7)]
    variances = [Fraction(12, 392), Fraction(6, 392), Fraction(6, 392)]
    scorer = weave.BayesAtNScorer(
        scorer=_binary_correct,
        question_ids=["q0", "q1", "q2"],
        trial_ids=list(range(5)),
    )
    assert scorer.summarize(_trial_rows(outcomes)) == pytest.approx(
        {
            "posterior_mean": float(sum(means) / 3),
            "posterior_sd": math.sqrt(sum(variances)) / 3,
        }
    )


@pytest.mark.trace_server
@pytest.mark.parametrize("bad", [0.0, 0.5, 1.0, float("nan"), "C", None, {}, []])
@pytest.mark.asyncio
async def test_bayes_at_n_rejects_nonbinary_grades(bad):
    with pytest.raises(ValueError, match="bool or integer 0/1"):
        await _bayes_scorer().score(
            output=bad, question_id="q0", trial_id=0, scorer_inputs={}
        )


@pytest.mark.trace_server
@pytest.mark.parametrize(
    "rows",
    [
        [],
        _trial_rows([[0, 0]]),
        _trial_rows([[0], [1, 1]]),
        _trial_rows([[0, 0], [1, 1]]) + _trial_rows([[0]]),
        _trial_rows([[0, 0], [1, 1]])[:-1] + [{}],
        _trial_rows([[0, 0], [1, 1]])[:-1] + _trial_rows([[0]]),
        _trial_rows([[0, 0], [1, 1]])[:-1]
        + [{"question_id": "other", "trial_id": 1, "correct": 1}],
        _trial_rows([[0, 0], [1, 1]])[:-1]
        + [{"question_id": "q1", "trial_id": 2, "correct": 1}],
        _trial_rows([[0, 0], [1, 1]])[:-1]
        + [{"question_id": "q1", "trial_id": 1, "correct": 0.5}],
    ],
)
def test_bayes_at_n_rejects_incomplete_or_invalid_cohorts(rows):
    with pytest.raises(ValueError, match="Bayes|Score|bool"):
        _bayes_scorer().summarize(rows)


@pytest.mark.trace_server
@pytest.mark.parametrize("ids", [[], [1, 1], [True], [1.5], [None]])
@pytest.mark.parametrize("field", ["question_ids", "trial_ids"])
def test_bayes_at_n_validates_declared_ids(ids, field):
    kwargs = {"question_ids": [1], "trial_ids": [0], field: ids}
    with pytest.raises(ValueError, match="validation error"):
        weave.BayesAtNScorer(scorer=_binary_correct, **kwargs)


@pytest.mark.trace_server
@pytest.mark.asyncio
async def test_bayes_at_n_preserves_typed_ids_and_json_results():
    scorer = weave.BayesAtNScorer(
        scorer=_binary_correct, question_ids=[1, "1"], trial_ids=[1, "1"]
    )
    rows = [
        await scorer.score(output=q == t, question_id=q, trial_id=t, scorer_inputs={})
        for q in [1, "1"]
        for t in [1, "1"]
    ]
    loaded = json.loads(json.dumps(rows))
    assert loaded == [
        {"question_id": 1, "trial_id": 1, "correct": True},
        {"question_id": 1, "trial_id": "1", "correct": False},
        {"question_id": "1", "trial_id": 1, "correct": False},
        {"question_id": "1", "trial_id": "1", "correct": True},
    ]
    assert scorer.summarize(loaded) == pytest.approx(
        {"posterior_mean": 0.5, "posterior_sd": math.sqrt(Fraction(1, 40))}
    )
    restored = weave.BayesAtNScorer.model_validate(scorer.model_dump())
    assert restored.summarize(loaded) == scorer.summarize(loaded)


@register_object
class _MappedBinaryScorer(weave.Scorer):
    @weave.op
    async def score(self, *, output, expected):
        await asyncio.sleep(0)
        return {"passed": output == expected}


@pytest.mark.trace_server
@pytest.mark.asyncio
async def test_bayes_at_n_preserves_wrapped_scorer_mapping_and_async():
    wrapped = _MappedBinaryScorer(column_map={"expected": "answer"})
    scorer = weave.BayesAtNScorer(
        scorer=wrapped,
        question_ids=["q"],
        trial_ids=[0],
        column_map={
            "question_id": "qid",
            "trial_id": "tid",
            "scorer_inputs": "grading",
        },
        score_key="passed",
    )
    result = await apply_scorer_async(
        scorer, {"qid": "q", "tid": 0, "grading": {"answer": "yes"}}, "yes"
    )
    assert result.result == {"question_id": "q", "trial_id": 0, "correct": True}


@pytest.mark.trace_server
@pytest.mark.parametrize("output", [{}, {"passed": 0.5}, True])
@pytest.mark.asyncio
async def test_bayes_at_n_validates_selected_score_key(output):
    with pytest.raises(ValueError, match="score_key|bool or integer"):
        await _bayes_scorer(score_key="passed").score(
            output=output, question_id="q0", trial_id=0, scorer_inputs={}
        )


@pytest.mark.trace_server
@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [None, [], 1])
async def test_bayes_at_n_requires_explicit_scorer_inputs(bad):
    with pytest.raises(TypeError, match="scorer_inputs must be a dictionary"):
        await _bayes_scorer().score(
            output=True, question_id="q0", trial_id=0, scorer_inputs=bad
        )


class _InputsMappedBinaryScorer(weave.Scorer):
    @weave.op
    def score(self, *, output, inputs):
        return output == inputs


@pytest.mark.trace_server
@pytest.mark.asyncio
async def test_bayes_at_n_preserves_reserved_grader_names():
    cases = [
        (
            _InputsMappedBinaryScorer(column_map={"inputs": "answer"}),
            {"answer": "yes"},
            None,
        ),
        (
            _MappedBinaryScorer(column_map={"expected": "output"}),
            {"output": "yes"},
            "passed",
        ),
    ]
    for wrapped, payload, key in cases:
        scorer = weave.BayesAtNScorer(
            scorer=wrapped, question_ids=["q"], trial_ids=[0], score_key=key
        )
        row = {"question_id": "q", "trial_id": 0, "scorer_inputs": payload}
        result = await apply_scorer_async(scorer, row, "yes")
        assert result.result == {"question_id": "q", "trial_id": 0, "correct": True}
        assert row == {"question_id": "q", "trial_id": 0, "scorer_inputs": payload}


@weave.op
async def _async_correct(output, expected):
    await asyncio.sleep(0)
    return output == expected


@pytest.mark.trace_server
@pytest.mark.asyncio
async def test_bayes_at_n_wraps_async_function_scorer():
    scorer = weave.BayesAtNScorer(
        scorer=_async_correct, question_ids=["q"], trial_ids=[0]
    )
    result = await apply_scorer_async(
        scorer,
        {"question_id": "q", "trial_id": 0, "scorer_inputs": {"expected": "yes"}},
        "yes",
    )
    assert result.result == {"question_id": "q", "trial_id": 0, "correct": True}


@weave.op
async def _trial_model(question_id, trial_id):
    await asyncio.sleep(0.001 if trial_id == 0 else 0)
    return question_id == "q1"


@pytest.mark.trace_server
@pytest.mark.asyncio
async def test_bayes_at_n_public_evaluation_and_repeat_run():
    scorer = _bayes_scorer()
    evaluation = weave.Evaluation(
        dataset=[
            {"question_id": q, "trial_id": t, "scorer_inputs": {}}
            for q in ["q0", "q1"]
            for t in [0, 1]
        ],
        scorers=[scorer],
        trials=1,
    )
    for _ in range(2):
        summary = await evaluation.evaluate(_trial_model)
        assert summary["BayesAtNScorer"] == pytest.approx(
            {"posterior_mean": 0.5, "posterior_sd": math.sqrt(Fraction(3, 160))}
        )


@pytest.mark.trace_server
@pytest.mark.asyncio
async def test_bayes_at_n_empty_evaluation_has_no_posterior_result():
    evaluation = weave.Evaluation(
        dataset=[{"question_id": "q0", "trial_id": 0}],
        scorers=[_bayes_scorer()],
        trials=0,
    )
    assert await evaluation.evaluate(_trial_model) == {}


@pytest.mark.trace_server
@pytest.mark.asyncio
async def test_bayes_at_n_accepts_native_boxed_scalars():
    scorer = weave.BayesAtNScorer(
        scorer=_binary_correct, question_ids=["q0"], trial_ids=[0]
    )
    row = await scorer.score(
        output=BoxedInt(1),
        question_id=BoxedStr("q0"),
        trial_id=BoxedInt(0),
        scorer_inputs={},
    )
    assert row == {"question_id": "q0", "trial_id": 0, "correct": True}
    assert type(row["question_id"]) is str
    assert type(row["trial_id"]) is int
    boxed_row = {
        "question_id": BoxedStr("q0"),
        "trial_id": BoxedInt(0),
        "correct": BoxedInt(1),
    }
    assert scorer.summarize([boxed_row]) == pytest.approx(
        {"posterior_mean": 2 / 3, "posterior_sd": math.sqrt(Fraction(1, 18))}
    )
    with pytest.raises(ValueError, match="bool or integer 0/1"):
        await scorer.score(
            output=BoxedFloat(1.0),
            question_id=BoxedStr("q0"),
            trial_id=BoxedInt(0),
            scorer_inputs={},
        )


@pytest.mark.trace_server
@pytest.mark.asyncio
async def test_bayes_at_n_native_object_record_round_trip():
    wrapped = _MappedBinaryScorer(column_map={"expected": "answer"})
    scorer = weave.BayesAtNScorer(
        scorer=wrapped, question_ids=["q0"], trial_ids=[0], score_key="passed"
    )
    attributes = pydantic_object_record(scorer).__dict__.copy()
    attributes["scorer"] = _make_weave_object(
        pydantic_object_record(wrapped).__dict__.copy()
    )
    restored = maybe_objectify(_make_weave_object(attributes))
    assert isinstance(restored, weave.BayesAtNScorer)
    result = await apply_scorer_async(
        restored,
        {"question_id": "q0", "trial_id": 0, "scorer_inputs": {"answer": "yes"}},
        "yes",
    )
    assert result.result == {"question_id": "q0", "trial_id": 0, "correct": True}
    assert restored.summarize([result.result]) == pytest.approx(
        {"posterior_mean": 2 / 3, "posterior_sd": math.sqrt(Fraction(1, 18))}
    )


@pytest.mark.trace_server
@pytest.mark.parametrize(
    "failure", ["model", "scorer", "duplicate", "missing", "trials"]
)
@pytest.mark.asyncio
async def test_bayes_at_n_public_evaluation_rejects_invalid_runs(failure):
    @weave.op
    async def model(question_id, trial_id):
        if failure == "model" and question_id == "q1":
            raise RuntimeError("failed generation")
        return None if failure == "scorer" and question_id == "q1" else True

    dataset = [
        {"question_id": q, "trial_id": t, "scorer_inputs": {}}
        for q in ["q0", "q1"]
        for t in [0, 1]
    ]
    if failure == "duplicate":
        dataset[-1] = dataset[0].copy()
    elif failure == "missing":
        dataset = dataset[:2]
    evaluation = weave.Evaluation(
        dataset=dataset,
        scorers=[_bayes_scorer()],
        trials=2 if failure == "trials" else 1,
    )
    with pytest.raises(ValueError, match="cohort|pair|scored result"):
        await evaluation.evaluate(model)


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


# A row whose model or scorer raised is recorded as an empty dict.


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
    ],
    ids=[
        "dict",
        "basemodel-last",
        "basemodel-first",
        "bool-last",
        "bool-first",
        "nested",
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
        ([{"distance": 1.0}, {"distance": None}, {}, {}], {"distance": {"mean": 1.0}}),
    ],
    ids=["bare-last", "bare-first", "nested", "nested-none-leaf"],
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
def test_auto_summarize_separates_unscored_rows_from_nested_empty_dicts():
    """One column, both kinds of empty dict: only the top-level one moves a denominator."""
    data = [
        {"usage": {}, "ok": True},
        {"usage": {"tokens": 10}, "ok": True},
        {},
    ]
    assert auto_summarize(data) == {
        "usage": {"tokens": {"mean": 10.0}},
        "ok": {"true_count": 2, "true_fraction": 2 / 3},
    }


@pytest.mark.trace_server
@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ([0.0, 1.0], {"mean": 0.5}),
        (
            [{"correct": True}, {"correct": None}],
            {"correct": {"true_count": 1, "true_fraction": 1.0}},
        ),
        ([{}, {}], None),
        ([None, None], None),
        ([], {}),
    ],
    ids=["falsy-number", "none-leaf", "all-unscored", "all-none", "empty"],
)
def test_auto_summarize_results_unchanged(data, expected):
    """Values the current implementation already returns; the unscored count must not move them.

    A falsy number and a None leaf are real values, not unscored rows.
    """
    assert auto_summarize(data) == expected
