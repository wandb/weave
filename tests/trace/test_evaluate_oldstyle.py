import threading

import pytest

import weave
from tests.conftest import LATENCY_TOL
from weave import Evaluation, Model
from weave.scorers import MultiTaskBinaryClassificationF1
from weave.trace.ref_util import get_ref, remove_ref
from weave.trace.weave_client import WeaveClient


@pytest.fixture
def dataset_rows():
    return [{"input": "1 + 2", "target": 3}, {"input": "2**4", "target": 15}]


@pytest.fixture
def expanded_dataset_rows(dataset_rows):
    return [dict(row) for _ in range(5) for row in dataset_rows]


expected_eval_result = {
    "model_output": {"mean": 9.5},
    "score_oldstyle": {"true_count": 1, "true_fraction": 0.5},
    "model_latency": {"mean": pytest.approx(0, abs=LATENCY_TOL)},
}


class EvalModel(Model):
    @weave.op
    async def predict(self, input) -> str:
        return eval(input)


@weave.op
def score_oldstyle(model_output, target):
    return model_output == target


@weave.op
def score_newstyle(output, target):
    return output == target


@weave.op
def example_to_model_input(example):
    return {"input": example["input"]}


def _install_concurrent_first_save_tracker(
    client: WeaveClient, monkeypatch: pytest.MonkeyPatch, *tracked_ops
) -> dict[str, int]:
    """Force first-time saves of shared ops to overlap and count real save attempts."""
    save_counts = {op.name: 0 for op in tracked_ops}
    save_counts_lock = threading.Lock()
    first_save_gates = {
        id(op): {"waiting": 0, "release": threading.Event()} for op in tracked_ops
    }
    tracked_ops_by_id = {id(op): op for op in tracked_ops}
    gate_lock = threading.Lock()
    original_save_object_basic = WeaveClient._save_object_basic.__get__(
        client, type(client)
    )

    def tracking_save_object_basic(val, name=None, branch="latest"):
        tracked_op = tracked_ops_by_id.get(id(val))
        if tracked_op is not None:
            # Hold the first unsaved call for each scorer until a second caller arrives.
            if get_ref(val) is None:
                gate_state = first_save_gates[id(val)]
                with gate_lock:
                    gate_state["waiting"] += 1
                    if gate_state["waiting"] == 2:
                        gate_state["release"].set()
                gate_state["release"].wait(timeout=0.5)
            # Count how many real saves reach `_save_object_basic` for each scorer op.
            with save_counts_lock:
                save_counts[tracked_op.name] += 1
        return original_save_object_basic(val, name=name, branch=branch)

    monkeypatch.setattr(client, "_save_object_basic", tracking_save_object_basic)
    return save_counts


@pytest.mark.asyncio
async def test_evaluate_callable_as_model(client, dataset_rows):
    @weave.op
    async def model_predict(input) -> str:
        return eval(input)

    evaluation = Evaluation(
        dataset=dataset_rows,
        scorers=[score_oldstyle],
    )
    result = await evaluation.evaluate(model_predict)
    assert result == expected_eval_result


@pytest.mark.asyncio
async def test_predict_can_receive_other_params(client, dataset_rows):
    @weave.op
    async def model_predict(input, target) -> str:
        return eval(input) + target

    evaluation = Evaluation(
        dataset=dataset_rows,
        scorers=[score_oldstyle],
    )
    result = await evaluation.evaluate(model_predict)
    assert result == {
        "model_output": {"mean": 18.5},
        "score_oldstyle": {"true_count": 0, "true_fraction": 0.0},
        "model_latency": {
            "mean": pytest.approx(0, abs=1),
        },
    }


@pytest.mark.asyncio
async def test_can_preprocess_model_input(client, dataset_rows):
    @weave.op
    async def model_predict(x) -> str:
        return eval(x)

    @weave.op
    def preprocess(example):
        return {"x": example["input"]}

    evaluation = Evaluation(
        dataset=dataset_rows,
        scorers=[score_oldstyle],
        preprocess_model_input=preprocess,
    )
    result = await evaluation.evaluate(model_predict)
    assert result == expected_eval_result


@pytest.mark.asyncio
async def test_evaluate_rows_only(client, dataset_rows):
    evaluation = Evaluation(
        dataset=dataset_rows,
        scorers=[score_oldstyle],
    )
    model = EvalModel()
    result = await evaluation.evaluate(model)
    assert result == expected_eval_result


@pytest.mark.asyncio
async def test_evaluate_both_styles(client, dataset_rows):
    client.set_autoflush(False)
    evaluation = Evaluation(
        dataset=dataset_rows,
        scorers=[score_oldstyle, score_newstyle],
    )
    model = EvalModel()
    try:
        result = await evaluation.evaluate(model)
        # Flush once after the evaluation to avoid per-op autoflush contention
        # in the calls_complete ClickHouse path.
        client.flush()
    finally:
        client.set_autoflush(True)
    assert result == {
        "model_output": {"mean": 9.5},
        "score_oldstyle": {"true_count": 1, "true_fraction": 0.5},
        "score_newstyle": {"true_count": 1, "true_fraction": 0.5},
        "model_latency": {"mean": pytest.approx(0, abs=LATENCY_TOL)},
    }


@pytest.mark.disable_logging_error_check
@pytest.mark.asyncio
async def test_evaluate_both_styles_saves_each_function_scorer_once(
    client, monkeypatch, expanded_dataset_rows
):
    evaluation = Evaluation(
        dataset=expanded_dataset_rows,
        scorers=[score_oldstyle, score_newstyle],
    )
    model = EvalModel()

    # These scorer Ops live at module scope, so clear any ref from earlier tests.
    remove_ref(score_oldstyle)
    remove_ref(score_newstyle)

    save_counts = _install_concurrent_first_save_tracker(
        client, monkeypatch, score_oldstyle, score_newstyle
    )
    # Raise parallelism to make overlapping scorer saves much more likely.
    monkeypatch.setenv("WEAVE_PARALLELISM", "20")

    client.set_autoflush(False)
    try:
        result = await evaluation.evaluate(model)
        client.flush()
    finally:
        client.set_autoflush(True)

    assert result == {
        "model_output": {"mean": 9.5},
        "score_oldstyle": {"true_count": 5, "true_fraction": 0.5},
        "score_newstyle": {"true_count": 5, "true_fraction": 0.5},
        "model_latency": {"mean": pytest.approx(0, abs=LATENCY_TOL)},
    }
    assert save_counts == {
        score_oldstyle.name: 1,
        score_newstyle.name: 1,
    }


@pytest.mark.asyncio
async def test_evaluate_other_model_method_names(dataset_rows):
    class EvalModel(Model):
        @weave.op
        async def infer(self, input) -> str:
            return eval(input)

    evaluation = Evaluation(
        dataset=dataset_rows,
        scorers=[score_oldstyle],
    )
    model = EvalModel()
    result = await evaluation.evaluate(model)
    assert result == expected_eval_result


@pytest.mark.asyncio
async def test_score_as_class(client, dataset_rows):
    class MyScorerOldstyle(weave.Scorer):
        @weave.op
        def score(self, model_output, target):
            return model_output == target

    evaluation = Evaluation(
        dataset=dataset_rows,
        scorers=[MyScorerOldstyle()],
    )
    model = EvalModel()
    result = await evaluation.evaluate(model)
    assert result == {
        "model_output": {"mean": 9.5},
        "MyScorerOldstyle": {"true_count": 1, "true_fraction": 0.5},
        "model_latency": {
            "mean": pytest.approx(0, abs=1),
        },
    }


@pytest.mark.asyncio
async def test_score_with_custom_summarize(client, dataset_rows):
    class MyScorerOldstyle(weave.Scorer):
        @weave.op
        def summarize(self, score_rows):
            assert list(score_rows) == [True, False]
            return {"awesome": 3}

        @weave.op
        def score(self, model_output, target):
            return model_output == target

    evaluation = Evaluation(
        dataset=dataset_rows,
        scorers=[MyScorerOldstyle()],
    )
    model = EvalModel()
    result = await evaluation.evaluate(model)
    assert result == {
        "model_output": {"mean": 9.5},
        "MyScorerOldstyle": {"awesome": 3},
        "model_latency": {
            "mean": pytest.approx(0, abs=1),
        },
    }


@pytest.mark.asyncio
async def test_multiclass_f1_score(client):
    evaluation = Evaluation(
        dataset=[{"target": {"a": False, "b": True}, "pred": {"a": True, "b": False}}],
        scorers=[MultiTaskBinaryClassificationF1(class_names=["a", "b"])],
    )

    @weave.op
    def return_pred(pred):
        return pred

    result = await evaluation.evaluate(return_pred)
    assert result == {
        "model_output": {
            "a": {"true_count": 1, "true_fraction": 1.0},
            "b": {"true_count": 0, "true_fraction": 0.0},
        },
        "MultiTaskBinaryClassificationF1": {
            "a": {"f1": 0, "precision": 0.0, "recall": 0},
            "b": {"f1": 0, "precision": 0, "recall": 0.0},
        },
        "model_latency": {
            "mean": pytest.approx(0, abs=1),
        },
    }
