"""Contract tests parametrized across EvaluationLogger (V1) and EvaluationLoggerV2.

These tests cover observable, user-facing behavior that both implementations
must support identically. They intentionally avoid peeking at implementation
details (specific op names, call-tree shapes, internal trace structure) so
the same test body can run against V1 and V2.

Each test simulates a realistic user flow and bundles related assertions
rather than testing one behavior at a time.

Anything that checks V1-specific trace structure (op names like
"Evaluation.evaluate", specific parent_id relationships, V1 summary shape)
belongs in ``test_evaluation_imperative.py``. Anything that checks V2-only
behavior (prediction_list, evaluation_run status, deferred output update)
belongs in ``test_evaluation_imperative_v2.py``.
"""

from __future__ import annotations

import asyncio

import pytest

from weave.evaluation.eval_imperative import EvaluationLogger
from weave.evaluation.eval_imperative_v2 import EvaluationLoggerV2
from weave.flow.scorer import Scorer


@pytest.fixture(params=[EvaluationLogger, EvaluationLoggerV2], ids=["v1", "v2"])
def logger_cls(request):
    return request.param


def test_full_evaluation_flow_with_log_example(client, logger_cls):
    """End-to-end eval: multiple predictions via log_example, mixed scorer
    forms (string / dict / Scorer subclass), ``None`` score, eval attributes,
    auto-summarize.
    """

    class MyScorer(Scorer):
        name: str = "my_scorer"

    ev = logger_cls(
        model="m",
        dataset=[{"q": "a"}, {"q": "b"}],
        eval_attributes={"environment": "test", "custom_attribute": "hello"},
    )

    # Two log_example calls covering the all-in-one convenience path, mixed
    # scorer types, and a None score ("N/A" in practice).
    ev.log_example(
        inputs={"q": "a"},
        output="A",
        scores={"string_scorer": 1.0, "maybe_scorer": None},
    )
    ev.log_example(
        inputs={"q": "b"},
        output="B",
        scores={"string_scorer": 0.5, "maybe_scorer": 0.8},
    )

    # One prediction constructed imperatively that exercises dict- and
    # class-based scorer inputs, plus the default auto_summarize=True path.
    pred = ev.log_prediction(inputs={"q": "c"}, output="C")
    pred.log_score({"name": "dict_scorer"}, 0.5)
    pred.log_score(MyScorer(), 0.25)
    pred.finish()

    ev.log_summary(summary={"user_key": 42})

    assert ev._is_finalized
    assert ev.attributes.get("custom_attribute") == "hello"

    assert len(ev._accumulated_predictions) == 3
    p1, p2, p3 = ev._accumulated_predictions
    assert p1._captured_scores == {"string_scorer": 1.0, "maybe_scorer": None}
    assert p2._captured_scores == {"string_scorer": 0.5, "maybe_scorer": 0.8}
    assert p3._captured_scores == {"dict_scorer": 0.5, "my_scorer": 0.25}
    assert all(p._has_finished for p in ev._accumulated_predictions)


def test_streaming_prediction_with_context_managers(client, logger_cls):
    """Dynamic user flow: output assigned inside the prediction context,
    scores both direct and deferred (``with pred.log_score(...) as s:``),
    plus an async score.
    """
    ev = logger_cls(model="m", dataset=[{"q": "x"}])

    with ev.log_prediction(inputs={"q": "x"}) as pred:
        pred.output = "dynamic_output"
        pred.log_score("direct", 0.9)
        with pred.log_score("deferred") as score_ctx:
            score_ctx.value = 0.75
        # Mix in an explicitly None score to lock that in end-to-end.
        pred.log_score("na", None)

    # An async score on a fresh prediction — log_prediction's context manager
    # is the "happy" finalize path; this exercises `alog_score` separately.
    async def _async_score() -> None:
        p = ev.log_prediction(inputs={"q": "y"}, output="Y")
        await p.alog_score("async_s", 0.33)
        p.finish()

    asyncio.run(_async_score())
    ev.log_summary()

    first, second = ev._accumulated_predictions
    assert first._has_finished
    assert first._captured_scores == {
        "direct": 0.9,
        "deferred": 0.75,
        "na": None,
    }
    assert second._captured_scores == {"async_s": 0.33}
    assert ev._is_finalized


def test_validation_and_error_paths(client, logger_cls, caplog):
    """Error-path contract: dict-scorer-missing-name raises, unset deferred
    score value raises, log_example-after-finalization raises, and using an
    ad-hoc scorer outside the predefined list logs a warning.
    """
    ev = logger_cls(
        model="m",
        dataset=[{"q": "x"}],
        scorers=["expected_scorer"],
    )
    pred = ev.log_prediction(inputs={"q": "x"}, output="y")

    with pytest.raises(ValueError, match="name"):
        pred.log_score({"not_name": "x"}, 1.0)

    with pytest.raises(ValueError, match="Score value was not set"):
        with pred.log_score("expected_scorer"):
            pass  # user forgot to assign score_ctx.value

    with caplog.at_level("WARNING"):
        pred.log_score("unexpected_scorer", 0.5)
    assert any(
        "unexpected_scorer" in r.message and "predefined" in r.message
        for r in caplog.records
    )

    pred.finish()
    ev.log_summary()

    with pytest.raises(ValueError, match="finalized"):
        ev.log_example(inputs={"q": "z"}, output="w", scores={"s": 0.0})


def test_logger_survives_disabled_failure_and_double_finish(
    client, logger_cls, monkeypatch
):
    """Robustness contract: the logger is a no-op but still captures scores
    locally when ``WEAVE_DISABLED=true``; ``fail(exception)`` finalizes; and
    a second ``finish()`` is a silent no-op (not an error).
    """
    # Disabled-mode logger: scores still captured client-side, no raise.
    monkeypatch.setenv("WEAVE_DISABLED", "true")
    disabled = logger_cls(model="m", dataset=[{"q": "x"}])
    pred = disabled.log_prediction(inputs={"q": "x"}, output="y")
    pred.log_score("s", 0.5)
    pred.finish()
    disabled.log_summary(summary={"k": 1}, auto_summarize=False)
    assert pred._captured_scores == {"s": 0.5}
    assert disabled._is_finalized
    monkeypatch.delenv("WEAVE_DISABLED")

    # fail(exception) finalizes the run without raising.
    failed = logger_cls(model="m", dataset=[{"q": "x"}])
    failed.log_prediction(inputs={"q": "x"}, output="y")
    failed.fail(RuntimeError("synthetic failure"))
    assert failed._is_finalized

    # Calling finish() twice is safe: the second call is a no-op.
    idempotent = logger_cls(model="m", dataset=[{"q": "x"}])
    idempotent.finish()
    idempotent.finish()
    assert idempotent._is_finalized
