import asyncio
from typing import Callable, TypedDict

import pytest

import weave
from weave.flow.eval_imperative import EvaluationLogger, Model, Scorer
from weave.integrations.integration_utilities import op_name_from_call
from weave.trace.context import call_context
from weave.trace_server.trace_server_interface import ObjectVersionFilter


class ExampleRow(TypedDict):
    a: int
    b: int


@pytest.fixture
def user_dataset() -> list[ExampleRow]:
    return [
        {"a": 1, "b": 2},
        {"a": 2, "b": 3},
        {"a": 3, "b": 4},
    ]


@pytest.fixture
def user_model():
    def func(a: int, b: int) -> int:
        return a + b

    return func


def test_basic_evaluation(
    client, user_dataset: list[ExampleRow], user_model: Callable[[int, int], int]
):
    ev = EvaluationLogger()

    outputs = []
    score1_results = []
    score2_results = []
    for row in user_dataset:
        outputs.append(output := user_model(row["a"], row["b"]))
        pred = ev.log_prediction(inputs=row, output=output)

        score1_results.append(score1_result := output > 2)
        pred.log_score(scorer="greater_than_2_scorer", score=score1_result)

        score2_results.append(score2_result := output > 2)
        pred.log_score(scorer="greater_than_4_scorer", score=score2_result)

        pred.finish()

    ev.log_summary({"avg_score": 1.0, "total_examples": 3})

    client.flush()

    calls = client.get_calls()
    assert len(calls) == 14

    evaluate_call = calls[0]
    assert op_name_from_call(evaluate_call) == "Evaluation.evaluate"
    assert evaluate_call.attributes["_weave_eval_meta"]["imperative"] is True
    assert evaluate_call.inputs["self"]._class_name == "Evaluation"
    assert evaluate_call.inputs["model"]._class_name == "Model"
    assert evaluate_call.output == {
        "avg_score": 1.0,
        "total_examples": 3,
        "greater_than_2_scorer": {"true_count": 3, "true_fraction": 1.0},
        "greater_than_4_scorer": {"true_count": 3, "true_fraction": 1.0},
    }

    for i, (inputs, outputs, score1, score2) in enumerate(
        zip(user_dataset, outputs, score1_results, score2_results)
    ):
        predict_index = 1 + i * 4

        predict_and_score_call = calls[predict_index]
        assert (
            op_name_from_call(predict_and_score_call) == "Evaluation.predict_and_score"
        )
        assert (
            predict_and_score_call.attributes["_weave_eval_meta"]["imperative"] is True
        )
        assert predict_and_score_call.inputs["self"]._class_name == "Evaluation"
        assert predict_and_score_call.inputs["model"]._class_name == "Model"
        assert predict_and_score_call.inputs["example"] == inputs
        assert predict_and_score_call.output["output"] == outputs

        predict_call = calls[predict_index + 1]
        assert op_name_from_call(predict_call) == "Model.predict"
        assert predict_call.attributes["_weave_eval_meta"]["imperative"] is True
        assert predict_call.inputs["self"]._class_name == "Model"
        assert predict_call.inputs["inputs"] == inputs
        assert predict_call.output == outputs

        feedbacks = list(predict_call.feedback)
        assert len(feedbacks) == 2
        assert feedbacks[0].feedback_type == "wandb.runnable.greater_than_2_scorer"
        assert feedbacks[1].feedback_type == "wandb.runnable.greater_than_4_scorer"

        scorer1_call = calls[predict_index + 2]
        assert op_name_from_call(scorer1_call) == "greater_than_2_scorer"
        assert scorer1_call.attributes["_weave_eval_meta"]["imperative"] is True
        assert scorer1_call.inputs["output"] == outputs
        assert scorer1_call.inputs["inputs"] == inputs
        assert scorer1_call.output == score1

        scorer2_call = calls[predict_index + 3]
        assert op_name_from_call(scorer2_call) == "greater_than_4_scorer"
        assert scorer2_call.attributes["_weave_eval_meta"]["imperative"] is True
        assert scorer2_call.inputs["output"] == outputs
        assert scorer2_call.inputs["inputs"] == inputs
        assert scorer2_call.output == score2

    summarize_call = calls[13]
    assert op_name_from_call(summarize_call) == "Evaluation.summarize"
    assert summarize_call.attributes["_weave_eval_meta"]["imperative"] is True
    assert summarize_call.inputs["self"]._class_name == "Evaluation"
    assert summarize_call.output == {
        "avg_score": 1.0,
        "total_examples": 3,
        "greater_than_2_scorer": {"true_count": 3, "true_fraction": 1.0},
        "greater_than_4_scorer": {"true_count": 3, "true_fraction": 1.0},
    }


def test_evaluation_with_custom_models_and_scorers(
    client, user_dataset: list[ExampleRow], user_model: Callable[[int, int], int]
):
    class MyModel(Model):
        a: int
        b: str

    class MyScorer(Scorer):
        c: int

    model1 = MyModel(a=1, b="two")
    model2 = {"name": "dict_model", "a": 2, "b": "three"}
    model3 = "string_model"

    ev1 = EvaluationLogger(model=model1)
    ev2 = EvaluationLogger(model=model2)
    ev3 = EvaluationLogger(model=model3)

    scorer1 = MyScorer(name="gt2_scorer", c=2)
    scorer2 = {"name": "gt4_scorer", "c": 4}
    scorer3 = "gt6_scorer"

    def run_evaluation(ev: EvaluationLogger):
        for row in user_dataset:
            output = user_model(row["a"], row["b"])
            pred = ev.log_prediction(inputs=row, output=output)
            score1_result = output > 2
            pred.log_score(scorer=scorer1, score=score1_result)

            score2_result = output > 4
            pred.log_score(scorer=scorer2, score=score2_result)

            score3_result = output > 6
            pred.log_score(scorer=scorer3, score=score3_result)

            pred.finish()

        ev.log_summary({"avg_score": 1.0, "total_examples": 3})

    def make_assertions():
        client.flush()

        models = client._objects(
            filter=ObjectVersionFilter(base_object_classes=["Model"])
        )
        assert len(models) == 3
        assert models[0].object_id == "MyModel"
        assert models[1].object_id == "dict_model"
        assert models[2].object_id == "string_model"

        scorers = client._objects(
            filter=ObjectVersionFilter(base_object_classes=["Scorer"])
        )
        assert len(scorers) == 3
        assert scorers[0].object_id == "gt2_scorer"
        assert scorers[1].object_id == "gt4_scorer"
        assert scorers[2].object_id == "gt6_scorer"

    # Run each evaluation once.
    # This creates 3 different model versions and 2 different scorer versions
    for ev in [ev1, ev2, ev3]:
        run_evaluation(ev)

    make_assertions()

    # Run the evaluations again.
    # Since the models and scorers already exist, there should be no new versions created
    for ev in [ev1, ev2, ev3]:
        run_evaluation(ev)

    make_assertions()

    # Run a new evaluation using the same scorers, but different models
    model4 = "new_string_model"
    ev4 = EvaluationLogger(model=model4)

    for row in user_dataset:
        output = user_model(row["a"], row["b"])
        pred = ev4.log_prediction(inputs=row, output=output)
        score1_result = output > 2
        pred.log_score(scorer=scorer1, score=score1_result)

        score2_result = output > 4
        pred.log_score(scorer=scorer2, score=score2_result)

        pred.finish()

    ev4.log_summary({"avg_score": 1.0, "total_examples": 3})

    models = client._objects(filter=ObjectVersionFilter(base_object_classes=["Model"]))
    assert len(models) == 4
    assert models[3].object_id == "new_string_model"

    # No change to scorers
    scorers = client._objects(
        filter=ObjectVersionFilter(base_object_classes=["Scorer"])
    )
    assert len(scorers) == 3

    # Run a new evaluation using the same models, but different scorers
    scorer4 = MyScorer(name="gt8_scorer", c=8)
    ev5 = EvaluationLogger(model=model4)

    for row in user_dataset:
        output = user_model(row["a"], row["b"])
        pred = ev5.log_prediction(inputs=row, output=output)
        score3_result = output > 8
        pred.log_score(scorer=scorer4, score=score3_result)

        pred.finish()

    ev5.log_summary({"avg_score": 1.0, "total_examples": 3})

    # No change to models
    models = client._objects(filter=ObjectVersionFilter(base_object_classes=["Model"]))
    assert len(models) == 4

    scorers = client._objects(
        filter=ObjectVersionFilter(base_object_classes=["Scorer"])
    )
    assert len(scorers) == 4
    assert scorers[3].object_id == "gt8_scorer"

    assert call_context.get_call_stack() == []


def test_evaluation_version_reuse(
    client, user_dataset: list[ExampleRow], user_model: Callable[[int, int], int]
):
    """Test that running the same evaluation twice results in only one version."""
    model = {"name": "test_model", "a": 1, "b": "two"}
    dataset_id = "test_dataset_unique_identifier"

    # Run the same evaluation twice
    for _ in range(2):
        ev = EvaluationLogger(model=model, dataset=dataset_id)

        for row in user_dataset:
            output = user_model(row["a"], row["b"])
            # Convert TypedDict to dict to avoid type errors
            inputs_dict = dict(row)
            pred = ev.log_prediction(inputs=inputs_dict, output=output)

            score_result = output > 2
            pred.log_score(scorer="greater_than_2_scorer", score=score_result)
            pred.finish()

        ev.log_summary({"avg_score": 1.0, "total_examples": 3})

        client.flush()

    # Only 1 version of the dataset should exist (it's the same one)
    evaluations = client._objects(
        filter=ObjectVersionFilter(base_object_classes=["Dataset"])
    )
    assert len(evaluations) == 1

    # Check that only one version of the evaluation exists (none of the methods
    # nor any of the attributes should have changed)
    evaluations = client._objects(
        filter=ObjectVersionFilter(base_object_classes=["Evaluation"])
    )
    assert len(evaluations) == 1


def generate_evaluation_logger_kwargs_permutations():
    NOT_SPECIFIED = object()

    class MyModel(weave.Model):
        const_value: int

        @weave.op
        def predict(self):
            return self.const_value

    class MyModelAsync(weave.Model):
        const_value: int

        @weave.op
        async def predict(self):
            await asyncio.sleep(0.001)
            return self.const_value

    models = [
        NOT_SPECIFIED,
        "string_model",
        {"name": "dict_model"},
        MyModel(const_value=42),
        MyModelAsync(const_value=420),
    ]

    datasets = [
        NOT_SPECIFIED,
        "string_dataset",
        [
            {"sample": "a", "exp_output": 1},
            {"sample": "b", "exp_output": 42},
        ],
        weave.Dataset(
            rows=[
                {"sample": "a", "exp_output": 1},
                {"sample": "b", "exp_output": 42},
            ]
        ),
    ]

    for model in models:
        for dataset in datasets:
            kwargs = {}
            if model is not NOT_SPECIFIED:
                kwargs["model"] = model
            if dataset is not NOT_SPECIFIED:
                kwargs["dataset"] = dataset

            yield kwargs


@pytest.fixture
def scorer(request):
    if request.param == "string":
        return "string_scorer"
    elif request.param == "dict":
        return {"name": "dict_scorer"}
    elif request.param == "weave-scorer":

        class MyScorer(weave.Scorer):
            @weave.op()
            def score(self, output: int, exp_output: int):
                return output == exp_output

        return MyScorer()
    elif request.param == "weave-scorer-async":

        class MyScorerAsync(weave.Scorer):
            @weave.op
            async def score(self, output: int, exp_output: int):
                await asyncio.sleep(0.001)
                return output == exp_output

        return MyScorerAsync()


@pytest.mark.parametrize(
    "evaluation_logger_kwargs",
    generate_evaluation_logger_kwargs_permutations(),
)
@pytest.mark.parametrize(
    "scorer",
    [
        "string",
        "dict",
        "weave-scorer",
        "weave-scorer-async",
    ],
    indirect=True,
)
@pytest.mark.parametrize(
    "score",
    [
        0.5,
        {"value": 0.5, "reason": "float"},
        {"value": 1, "reason": "int"},
        {"value": True, "reason": "bool"},
    ],
)
@pytest.mark.asyncio
async def test_various_input_forms(client, evaluation_logger_kwargs, scorer, score):
    your_dataset = [
        {"a": 1, "b": 2},
        {"a": 3, "b": 4},
        {"a": 5, "b": 6},
    ]

    def do_sync_eval():
        ev = weave.EvaluationLogger(**evaluation_logger_kwargs)
        for inputs in your_dataset:
            output = inputs["a"] + inputs["b"]
            pred = ev.log_prediction(inputs=inputs, output=output)
            pred.log_score(scorer=scorer, score=score)
        ev.log_summary({"gpus_melted": 8})

    async def do_async_eval():
        ev = weave.EvaluationLogger(**evaluation_logger_kwargs)
        for inputs in your_dataset:
            output = inputs["a"] + inputs["b"]
            pred = ev.log_prediction(inputs=inputs, output=output)
            await pred.alog_score(scorer=scorer, score=score)
        ev.log_summary({"gpus_melted": 8})

    expected_num_calls = (
        1  # Evaluation.evaluate
        + 3  # (three predictions)
        * (
            1  # Evaluation.predict_and_score
            + 1  # Model.predict
            + 1  # Scorer.score
        )
        + 1  # Evaluation.summarize
    )
    do_sync_eval()
    client.flush()
    calls = client.get_calls()
    assert len(calls) == expected_num_calls

    await do_async_eval()
    client.flush()
    calls = client.get_calls()
    # including the previous set of sync calls
    assert len(calls) == expected_num_calls * 2


def test_passing_dict_requires_name_with_scorer(client):
    ev = weave.EvaluationLogger()
    pred = ev.log_prediction(inputs={}, output=None)
    with pytest.raises(ValueError, match="Your dict must contain a `name` key."):
        pred.log_score(scorer={"something": "else"}, score=0.5)

    pred.log_score(scorer={"name": "my_scorer"}, score=0.5)
    ev.finish()


@pytest.mark.disable_logging_error_check
def test_passing_dict_requires_name_with_model(client):
    with pytest.raises(ValueError, match="Your dict must contain a `name` key."):
        ev = weave.EvaluationLogger(model={"something": "else"})

    ev2 = weave.EvaluationLogger(model={"name": "my_model"})
    ev2.finish()


def test_evaluation_no_auto_summarize(client):
    ev = weave.EvaluationLogger()
    pred = ev.log_prediction(inputs={"a": 1, "b": 2}, output=3)
    pred.log_score(scorer="gt2_scorer", score=True)
    ev.log_summary(auto_summarize=False)
    ev.finish()
    client.flush()

    calls = client.get_calls()
    # assert len(calls) == 1
    summarize_call = calls[4]
    assert summarize_call.output == {}


def test_evaluation_no_auto_summarize_with_custom_dict(client):
    ev = weave.EvaluationLogger()
    pred = ev.log_prediction(inputs={"a": 1, "b": 2}, output=3)
    pred.log_score(scorer="gt2_scorer", score=True)
    ev.log_summary(summary={"something": 1, "else": 2}, auto_summarize=False)
    ev.finish()
    client.flush()

    calls = client.get_calls()
    # assert len(calls) == 1
    summarize_call = calls[4]
    assert summarize_call.output == {"something": 1, "else": 2}
