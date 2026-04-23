"""Tests for EvaluationLoggerV2 that assert on the V2 server object model.

These tests are V2-specific: they inspect the V2 endpoints (evaluation_run_read,
prediction_read, score_read) rather than V1's call graph. Cross-logger contract
behavior is exercised in ``test_evaluation_imperative_contract.py``.
"""

from __future__ import annotations

import asyncio

import pytest

import weave
from weave.evaluation.eval_imperative import EvaluationLogger as EvaluationLoggerV1
from weave.evaluation.eval_imperative_v2 import EvaluationLoggerV2
from weave.trace_server import trace_server_interface as tsi


def _predictions_for_run(client, run_id: str) -> list[tsi.PredictionReadRes]:
    return list(
        client.server.prediction_list(
            tsi.PredictionListReq(
                project_id=client.project_id,
                evaluation_run_id=run_id,
            )
        )
    )


def _scores_for_run(client, run_id: str) -> list[tsi.ScoreReadRes]:
    return list(
        client.server.score_list(
            tsi.ScoreListReq(
                project_id=client.project_id,
                evaluation_run_id=run_id,
            )
        )
    )


def test_basic_v2_flow_round_trips_through_server(client):
    ev = EvaluationLoggerV2(
        name="basic_v2",
        model="my_model",
        dataset=[{"q": "hi"}],
        scorers=["correctness"],
    )
    pred = ev.log_prediction(inputs={"q": "hi"}, output="there")
    pred.log_score("correctness", 0.9)
    pred.finish()
    ev.log_summary({"avg": 0.9})

    assert ev._evaluation_run_id is not None

    run_id = ev._evaluation_run_id
    run = client.server.evaluation_run_read(
        tsi.EvaluationRunReadReq(
            project_id=client.project_id,
            evaluation_run_id=run_id,
        )
    )
    assert run.status != "error"
    assert run.summary is not None
    assert run.summary.get("output") == {"avg": 0.9}

    predictions = _predictions_for_run(client, run_id)
    assert len(predictions) == 1
    assert predictions[0].inputs == {"q": "hi"}
    assert predictions[0].output == "there"

    scores = _scores_for_run(client, run_id)
    assert len(scores) == 1
    assert scores[0].value == 0.9


def test_lazy_init_no_predictions_still_produces_run(client):
    ev = EvaluationLoggerV2(model="lazy_model", dataset=[{"x": 1}])
    ev.log_summary()

    assert ev._evaluation_run_id is not None
    run = client.server.evaluation_run_read(
        tsi.EvaluationRunReadReq(
            project_id=client.project_id,
            evaluation_run_id=ev._evaluation_run_id,
        )
    )
    assert run.status != "error"


def test_deferred_output_is_updated_on_finish(client):
    ev = EvaluationLoggerV2(model="m", dataset=[{"q": "hi"}])
    pred = ev.log_prediction(inputs={"q": "hi"})
    pred.output = "first"
    pred.log_score("s", 1.0)  # triggers prediction_create with output="first"
    pred.output = "final"
    pred.finish()
    ev.log_summary()

    predictions = _predictions_for_run(client, ev._evaluation_run_id)
    assert len(predictions) == 1
    assert predictions[0].output == "final"


def test_finish_with_explicit_output_overrides_buffer(client):
    ev = EvaluationLoggerV2(model="m", dataset=[{"q": "hi"}])
    pred = ev.log_prediction(inputs={"q": "hi"}, output="initial")
    pred.log_score("s", 1.0)
    pred.finish(output="from-finish")
    ev.log_summary()

    predictions = _predictions_for_run(client, ev._evaluation_run_id)
    assert predictions[0].output == "from-finish"


def test_fail_marks_run_as_error(client):
    ev = EvaluationLoggerV2(model="m", dataset=[{"q": "hi"}])
    ev.log_prediction(inputs={"q": "hi"}, output="x")
    ev.fail(RuntimeError("boom"))

    run = client.server.evaluation_run_read(
        tsi.EvaluationRunReadReq(
            project_id=client.project_id,
            evaluation_run_id=ev._evaluation_run_id,
        )
    )
    # Server uses "error" or "failed" depending on backend naming — both
    # indicate a failed run.
    assert run.status in {"error", "failed"}


def test_score_value_types_round_trip(client):
    ev = EvaluationLoggerV2(model="m", dataset=[{"q": "x"}])
    pred = ev.log_prediction(inputs={"q": "x"}, output="y")
    pred.log_score("as_float", 0.42)
    pred.log_score("as_bool", True)
    pred.log_score("as_dict", {"value": 1.0, "reason": "ok"})
    pred.log_score("as_none", None)
    pred.finish()
    ev.log_summary()

    scores = _scores_for_run(client, ev._evaluation_run_id)
    by_name = {}
    for s in scores:
        # Scorer ref looks like weave:///entity/project/object/NAME:DIGEST.
        scorer_name = s.scorer.rsplit("/", 1)[-1].split(":")[0]
        by_name[scorer_name] = s.value
    assert by_name == {
        "as_float": 0.42,
        "as_bool": True,
        "as_dict": {"value": 1.0, "reason": "ok"},
        "as_none": None,
    }


def test_ad_hoc_scorer_materializes_on_server(client):
    ev = EvaluationLoggerV2(
        model="m",
        dataset=[{"q": "x"}],
        scorers=["predeclared"],
    )
    pred = ev.log_prediction(inputs={"q": "x"}, output="y")
    pred.log_score("ad_hoc_scorer", 1.0)  # not in `scorers=[...]`
    pred.finish()
    ev.log_summary()

    scorers = list(
        client.server.scorer_list(tsi.ScorerListReq(project_id=client.project_id))
    )
    names = {s.name for s in scorers}
    assert "predeclared" in names
    assert "ad_hoc_scorer" in names


def test_context_manager_finishes_on_exit(client):
    ev = EvaluationLoggerV2(model="m", dataset=[{"q": "x"}])
    with ev.log_prediction(inputs={"q": "x"}) as pred:
        pred.output = "y"
        pred.log_score("s", 1.0)
    ev.log_summary()

    predictions = _predictions_for_run(client, ev._evaluation_run_id)
    assert len(predictions) == 1
    assert predictions[0].output == "y"


def test_context_manager_propagates_exceptions(client):
    ev = EvaluationLoggerV2(model="m", dataset=[{"q": "x"}])

    def _body() -> None:
        with ev.log_prediction(inputs={"q": "x"}) as pred:
            pred.output = "y"
            raise RuntimeError("inside")

    with pytest.raises(RuntimeError, match="inside"):
        _body()

    # Even with the exception, the prediction should have been finalized on exit.
    ev.log_summary()
    predictions = _predictions_for_run(client, ev._evaluation_run_id)
    assert len(predictions) == 1


def test_log_score_context_manager_submits_on_exit(client):
    ev = EvaluationLoggerV2(model="m", dataset=[{"q": "x"}])
    pred = ev.log_prediction(inputs={"q": "x"}, output="y")
    with pred.log_score("quality") as score_ctx:
        score_ctx.value = 0.7
    pred.finish()
    ev.log_summary()

    scores = _scores_for_run(client, ev._evaluation_run_id)
    assert len(scores) == 1
    assert scores[0].value == 0.7


def test_log_score_context_manager_without_value_raises(client):
    ev = EvaluationLoggerV2(model="m", dataset=[{"q": "x"}])
    pred = ev.log_prediction(inputs={"q": "x"}, output="y")
    with pytest.raises(ValueError, match="Score value was not set"):
        with pred.log_score("quality"):
            pass
    pred.finish()
    ev.log_summary()


def test_factory_defaults_to_v1(client):
    # `weave.EvaluationLogger` is the factory; without opting in, it must
    # keep returning V1 so existing users don't see a behavior change.
    ev = weave.EvaluationLogger(model="m", dataset=[{"q": "x"}])
    assert isinstance(ev, EvaluationLoggerV1)
    ev.finish()


def test_factory_dispatches_to_v2_via_env(client, monkeypatch):
    monkeypatch.setenv("WEAVE_USE_EVALUATION_LOGGER_V2", "true")
    ev = weave.EvaluationLogger(model="m", dataset=[{"q": "x"}])
    assert isinstance(ev, EvaluationLoggerV2)
    ev.finish()


def test_factory_dispatches_to_v2_via_settings(client):
    from weave.trace.settings import UserSettings, parse_and_apply_settings

    parse_and_apply_settings(UserSettings(use_evaluation_logger_v2=True))
    try:
        ev = weave.EvaluationLogger(model="m", dataset=[{"q": "x"}])
        assert isinstance(ev, EvaluationLoggerV2)
        ev.finish()
    finally:
        parse_and_apply_settings(UserSettings())


def test_ui_url_format(client):
    ev = EvaluationLoggerV2(model="m", dataset=[{"q": "x"}])
    assert ev.ui_url is None  # not initialized yet (lazy init)

    pred = ev.log_prediction(inputs={"q": "x"}, output="y")
    pred.log_score("s", 1.0)  # forces lazy init + evaluation_run_id allocation
    url = ev.ui_url
    assert url is not None
    # Format: <host>/<entity>/<project>/r/call/<evaluation_run_id>
    assert url.endswith(f"/r/call/{ev._evaluation_run_id}")
    assert f"/{ev._entity}/{ev._project}/" in url
    pred.finish()
    ev.log_summary()


def test_ui_url_none_when_disabled(monkeypatch):
    monkeypatch.setenv("WEAVE_DISABLED", "true")
    ev = EvaluationLoggerV2(model="m", dataset=[{"q": "x"}])
    assert ev.ui_url is None
    ev.finish()


def test_set_view_not_implemented():
    ev = EvaluationLoggerV2(model="m", dataset=[{"q": "x"}])
    with pytest.raises(NotImplementedError, match="set_view"):
        ev.set_view("report", "# hi", extension="md")
    ev.finish()


def test_log_example_after_finalization_raises(client):
    ev = EvaluationLoggerV2(model="m", dataset=[{"q": "x"}])
    ev.log_example(inputs={"q": "x"}, output="y", scores={"s": 1.0})
    ev.log_summary()
    with pytest.raises(ValueError, match="finalized"):
        ev.log_example(inputs={"q": "z"}, output="w", scores={"s": 0.0})


def test_bare_string_model_scorer_dataset_round_trip(client):
    ev = EvaluationLoggerV2(
        model="string-named-model",
        dataset="string-named-dataset",
        scorers=["string-named-scorer"],
    )
    pred = ev.log_prediction(inputs={"x": 1}, output=2)
    # `_cast_to_cls(Scorer)` sanitizes scorer names; pass the same string form
    # and rely on the shared coercion so the log_score path resolves the same
    # ref that was created up front.
    pred.log_score("string-named-scorer", 1.0)
    pred.finish()
    ev.log_summary()

    # Model, dataset, and scorer should all be readable by name.
    models = list(
        client.server.model_list(tsi.ModelListReq(project_id=client.project_id))
    )
    assert any(m.name == "stringnamedmodel" for m in models)

    datasets = list(
        client.server.dataset_list(tsi.DatasetListReq(project_id=client.project_id))
    )
    assert any(d.name == "string-named-dataset" for d in datasets)

    scorers = list(
        client.server.scorer_list(tsi.ScorerListReq(project_id=client.project_id))
    )
    # Scorers go through `_cast_to_cls(Scorer)` which sanitizes the name the
    # same way V1 does (strip non-word characters).
    assert any(s.name == "stringnamedscorer" for s in scorers)


def test_weave_disabled_captures_scores_without_server_calls(monkeypatch):
    monkeypatch.setenv("WEAVE_DISABLED", "true")
    ev = EvaluationLoggerV2(model="m", dataset=[{"q": "x"}])
    pred = ev.log_prediction(inputs={"q": "x"}, output="y")
    pred.log_score("s", 0.5)
    pred.finish()
    ev.log_summary()

    assert ev._disabled is True
    assert ev._evaluation_run_id is None
    assert pred._captured_scores == {"s": 0.5}


def test_alog_score_async(client):
    async def run() -> None:
        ev = EvaluationLoggerV2(model="m", dataset=[{"q": "x"}])
        pred = ev.log_prediction(inputs={"q": "x"}, output="y")
        await pred.alog_score("async_scorer", 0.75)
        pred.finish()
        ev.log_summary()
        scores = _scores_for_run(client, ev._evaluation_run_id)
        assert len(scores) == 1
        assert scores[0].value == 0.75

    asyncio.run(run())
