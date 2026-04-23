"""Contract tests parametrized across EvaluationLogger (V1) and EvaluationLoggerV2.

These tests cover observable, user-facing behavior that both implementations
must support identically. They intentionally avoid peeking at implementation
details (specific op names, call-tree shapes, internal trace structure) so
the same test body can run against V1 and V2.

Anything that checks V1-specific trace structure (op names like
"Evaluation.evaluate", specific parent_id relationships, V1 summary shape)
belongs in ``test_evaluation_imperative.py``. Anything that checks V2-only
behavior (prediction_list, evaluation_run status, deferred output update)
belongs in ``test_evaluation_imperative_v2.py``.
"""

from __future__ import annotations

import pytest

from weave.evaluation._imperative_shared import (
    EvaluationLoggerProtocol,
    ScoreLoggerProtocol,
)
from weave.evaluation.eval_imperative import EvaluationLogger
from weave.evaluation.eval_imperative_v2 import EvaluationLoggerV2


@pytest.fixture(params=[EvaluationLogger, EvaluationLoggerV2], ids=["v1", "v2"])
def logger_cls(request):
    return request.param


def test_logger_and_score_logger_match_protocol_at_runtime(client, logger_cls):
    # Both V1 and V2 should expose the shared `EvaluationLoggerProtocol` and
    # `ScoreLoggerProtocol` public APIs. This is a loose structural check —
    # mypy catches mismatches at type-check time, this catches them at
    # runtime as a safety net against drift.
    ev = logger_cls(model="m", dataset=[{"q": "x"}])
    for member in EvaluationLoggerProtocol.__annotations__.keys() | {
        "log_prediction",
        "log_example",
        "log_summary",
        "set_view",
        "finish",
        "fail",
        "ui_url",
        "attributes",
    }:
        assert hasattr(ev, member), f"{logger_cls.__name__} is missing {member}"

    pred = ev.log_prediction(inputs={"q": "x"}, output="y")
    for member in {"output", "log_score", "alog_score", "finish"}:
        assert hasattr(pred, member), (
            f"{pred.__class__.__name__} is missing {member}"
        )
    pred.finish()
    ev.log_summary()

    # Sanity: the Protocols are importable as public names and annotations
    # referencing them don't explode.
    def _takes_logger(lg: EvaluationLoggerProtocol) -> None:
        _ = lg.ui_url

    def _takes_score_logger(sl: ScoreLoggerProtocol) -> None:
        _ = sl.output

    _takes_logger(ev)
    _takes_score_logger(pred)


def test_log_example_roundtrip(client, logger_cls):
    ev = logger_cls(model="m", dataset=[{"q": "x"}])
    ev.log_example(
        inputs={"q": "x"},
        output="y",
        scores={"correct": 1.0, "fluent": 0.8},
    )
    ev.log_summary()

    pred = ev._accumulated_predictions[0]
    assert pred._captured_scores == {"correct": 1.0, "fluent": 0.8}
    assert pred._has_finished


def test_log_example_multiple_examples(client, logger_cls):
    ev = logger_cls(model="m", dataset=[{"q": "a"}, {"q": "b"}])
    ev.log_example(inputs={"q": "a"}, output="A", scores={"s": 1.0})
    ev.log_example(inputs={"q": "b"}, output="B", scores={"s": 0.5})
    ev.log_summary()

    assert len(ev._accumulated_predictions) == 2
    assert ev._accumulated_predictions[0]._captured_scores == {"s": 1.0}
    assert ev._accumulated_predictions[1]._captured_scores == {"s": 0.5}


def test_log_example_after_finalization_raises(client, logger_cls):
    ev = logger_cls(model="m", dataset=[{"q": "x"}])
    ev.log_example(inputs={"q": "x"}, output="y", scores={"s": 1.0})
    ev.log_summary()
    with pytest.raises(ValueError, match="finalized"):
        ev.log_example(inputs={"q": "z"}, output="w", scores={"s": 0.0})


def test_none_as_valid_score_value(client, logger_cls):
    ev = logger_cls(model="m", dataset=[{"q": "x"}])
    pred = ev.log_prediction(inputs={"q": "x"}, output="y")
    pred.log_score("maybe_scorer", None)
    pred.finish()
    ev.log_summary()
    assert pred._captured_scores == {"maybe_scorer": None}


def test_passing_dict_scorer_without_name_raises(client, logger_cls):
    ev = logger_cls(model="m", dataset=[{"q": "x"}])
    pred = ev.log_prediction(inputs={"q": "x"}, output="y")
    with pytest.raises(ValueError, match="name"):
        pred.log_score({"not_name": "x"}, 1.0)


def test_log_prediction_context_manager_sets_output(client, logger_cls):
    ev = logger_cls(model="m", dataset=[{"q": "x"}])
    with ev.log_prediction(inputs={"q": "x"}) as pred:
        pred.output = "dynamic_output"
        pred.log_score("s", 0.9)
    ev.log_summary()

    assert pred._has_finished
    assert pred._captured_scores == {"s": 0.9}


def test_log_score_context_manager_submits_value(client, logger_cls):
    ev = logger_cls(model="m", dataset=[{"q": "x"}])
    pred = ev.log_prediction(inputs={"q": "x"}, output="y")
    with pred.log_score("reasoning") as score_ctx:
        score_ctx.value = 0.75
    pred.finish()
    ev.log_summary()

    assert pred._captured_scores == {"reasoning": 0.75}


def test_log_score_context_manager_without_value_raises(client, logger_cls):
    ev = logger_cls(model="m", dataset=[{"q": "x"}])
    pred = ev.log_prediction(inputs={"q": "x"}, output="y")
    with pytest.raises(ValueError, match="Score value was not set"):
        with pred.log_score("reasoning"):
            pass
    pred.finish()
    ev.log_summary()


def test_predefined_scorer_warning_on_ad_hoc_use(client, logger_cls, caplog):
    ev = logger_cls(
        model="m",
        dataset=[{"q": "x"}],
        scorers=["expected_scorer"],
    )
    pred = ev.log_prediction(inputs={"q": "x"}, output="y")
    with caplog.at_level("WARNING"):
        pred.log_score("unexpected_scorer", 0.5)
    pred.finish()
    ev.log_summary()

    # Both V1 and V2 log a WARNING when a scorer outside the predefined list
    # is used.
    assert any(
        "unexpected_scorer" in r.message and "predefined" in r.message
        for r in caplog.records
    )


def test_custom_eval_attributes_accepted(client, logger_cls):
    # Accepting `eval_attributes=` without raising is part of the contract.
    # V1 stores them on the evaluate call's attributes; V2 stores them via
    # EvaluationCreateReq.eval_attributes. The observable contract here is
    # simply that construction + a full flow succeed.
    ev = logger_cls(
        model="m",
        dataset=[{"q": "x"}],
        eval_attributes={"environment": "test", "custom_attribute": "hello"},
    )
    pred = ev.log_prediction(inputs={"q": "x"}, output="y")
    pred.log_score("s", 1.0)
    pred.finish()
    ev.log_summary()
    assert ev.attributes.get("custom_attribute") == "hello"


def test_scorers_accept_string_dict_and_instance(client, logger_cls):
    from weave.flow.scorer import Scorer

    class MyScorer(Scorer):
        name: str = "my_scorer"

    ev = logger_cls(model="m", dataset=[{"q": "x"}])
    pred = ev.log_prediction(inputs={"q": "x"}, output="y")
    pred.log_score("string_scorer", 1.0)
    pred.log_score({"name": "dict_scorer"}, 0.5)
    pred.log_score(MyScorer(), 0.25)
    pred.finish()
    ev.log_summary()

    assert set(pred._captured_scores.keys()) == {
        "string_scorer",
        "dict_scorer",
        "my_scorer",
    }


def test_log_summary_no_auto_summarize(client, logger_cls):
    ev = logger_cls(model="m", dataset=[{"q": "x"}])
    pred = ev.log_prediction(inputs={"q": "x"}, output="y")
    pred.log_score("s", 1.0)
    pred.finish()
    ev.log_summary(summary={"user_key": 42}, auto_summarize=False)

    # Contract: the evaluation is finalized and doesn't raise.
    assert ev._is_finalized


def test_weave_disabled_captures_scores_without_failing(
    client, logger_cls, monkeypatch
):
    monkeypatch.setenv("WEAVE_DISABLED", "true")
    ev = logger_cls(model="m", dataset=[{"q": "x"}])
    pred = ev.log_prediction(inputs={"q": "x"}, output="y")
    pred.log_score("s", 0.5)
    pred.finish()
    ev.log_summary()

    # Contract: the logger tolerates disabled tracing, keeps user-visible
    # state internally, and does not raise.
    assert pred._captured_scores == {"s": 0.5}


def test_fail_finalizes_without_raising(client, logger_cls):
    ev = logger_cls(model="m", dataset=[{"q": "x"}])
    ev.log_prediction(inputs={"q": "x"}, output="y")
    ev.fail(RuntimeError("synthetic failure"))
    assert ev._is_finalized


def test_finish_without_predictions_is_idempotent(client, logger_cls):
    ev = logger_cls(model="m", dataset=[{"q": "x"}])
    ev.finish()
    ev.finish()  # Second finish should no-op, not raise.
    assert ev._is_finalized


def test_async_alog_score(client, logger_cls):
    import asyncio

    async def run() -> None:
        ev = logger_cls(model="m", dataset=[{"q": "x"}])
        pred = ev.log_prediction(inputs={"q": "x"}, output="y")
        await pred.alog_score("async_s", 0.33)
        pred.finish()
        ev.log_summary()
        assert pred._captured_scores == {"async_s": 0.33}

    asyncio.run(run())
