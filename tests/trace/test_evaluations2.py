import asyncio

import pytest

import weave
from weave.flow.eval import Evaluation2, EvaluationResult2, is_async_callable


@pytest.fixture
def model(request):
    if request.param == "op":

        @weave.op
        def _model(a: int, b: int) -> int:
            return a + b

        return _model
    elif request.param == "function":

        def _model(a: int, b: int) -> int:
            return a + b

        return _model
    elif request.param == "callable_class":

        class _Model:
            def __call__(self, a: int, b: int) -> int:
                return a + b

        return _Model()

    raise ValueError(f"Invalid model type: {request.param}")


# @pytest.fixture
# def data(request):
#     if request.param == "empty":
#         return []
#     if request.param == "one":
#         return [{"a": 1, "b": 2}]
#     if request.param == "many":
#         return [{"a": 1, "b": 2}, {"a": 3, "b": 4}, {"a": 5, "b": 6}]
#     raise ValueError(f"Invalid data type: {request.param}")


@pytest.fixture
def dataset(request):
    data = [
        {"a": 1, "b": 2},
        {"a": 3, "b": 4},
        {"a": 5, "b": 6},
    ]
    if request.param == "list":
        return data
    elif request.param == "dataset":
        return weave.Dataset(rows=data)
    raise ValueError(f"Invalid dataset type: {request.param}")


@pytest.fixture
def scorers(request):
    def valid_sync_scorer(output: int) -> bool:
        return output > 5

    def invalid_sync_scorer(output: str) -> bool:
        return "substring" in output

    async def valid_async_scorer(output: int) -> bool:
        return output > 8

    async def invalid_async_scorer(output: str) -> bool:
        return output + "text" == f"{output}text"

    valid_sync_scorer_op = weave.op(valid_sync_scorer)
    invalid_sync_scorer_op = weave.op(invalid_sync_scorer)
    valid_async_scorer_op = weave.op(valid_async_scorer)
    invalid_async_scorer_op = weave.op(invalid_async_scorer)

    sync_scorers = [valid_sync_scorer, invalid_sync_scorer]
    async_scorers = [valid_async_scorer, invalid_async_scorer]
    sync_scorer_ops = [valid_sync_scorer_op, invalid_sync_scorer_op]
    async_scorer_ops = [valid_async_scorer_op, invalid_async_scorer_op]

    if request.param == "sync":
        return sync_scorers
    elif request.param == "async":
        return async_scorers
    elif request.param == "combo":
        return sync_scorers + async_scorers
    elif request.param == "combo_ops":
        return sync_scorer_ops + async_scorer_ops
    raise ValueError(f"Invalid scorers type: {request.param}")


@pytest.fixture
def model_calls(model, dataset):
    calls = []
    for input_ in dataset:
        if is_async_callable(model):
            _, call = asyncio.run(model.call(**input_))
        else:
            _, call = model.call(**input_)
        calls.append(call)
    return calls


@pytest.fixture
def scorer_calls(model_calls, scorers):
    calls = []
    for model_call in model_calls:
        for scorer in scorers:
            if is_async_callable(scorer):
                _, call = asyncio.run(scorer.call(model_call.output))
            else:
                _, call = scorer.call(model_call.output)
            calls.append(call)
    return calls


def check_eval_results(results):
    assert len(results.predictions) == 3
    assert results.predictions[0] == 3
    assert results.predictions[1] == 7
    assert results.predictions[2] == 11


def check_scores(scores, scorers):
    assert len(scores) == len(scorers)
    if valid_async_score := scores.get("valid_async_scorer"):
        assert valid_async_score[0]["score"] == False
        assert valid_async_score[1]["score"] == False
        assert valid_async_score[2]["score"] == True

    if invalid_async_score := scores.get("invalid_async_scorer"):
        assert invalid_async_score[0]["score"] == None
        assert invalid_async_score[1]["score"] == None
        assert invalid_async_score[2]["score"] == None

    if valid_sync_score := scores.get("valid_sync_scorer"):
        assert valid_sync_score[0]["score"] == False
        assert valid_sync_score[1]["score"] == True
        assert valid_sync_score[2]["score"] == True

    if invalid_sync_score := scores.get("invalid_sync_scorer"):
        assert invalid_sync_score[0]["score"] == None
        assert invalid_sync_score[1]["score"] == None
        assert invalid_sync_score[2]["score"] == None


def check_summary(summary, scorers):
    assert len(summary) == len(scorers)
    if valid_async_scorer_summary := summary.get("valid_async_scorer"):
        assert valid_async_scorer_summary["score"]["true_count"] == 1
        assert valid_async_scorer_summary["score"]["true_fraction"] == 1 / 3

    if invalid_async_scorer_summary := summary.get("invalid_async_scorer"):
        assert invalid_async_scorer_summary["score"]["true_count"] == 0
        assert invalid_async_scorer_summary["score"]["true_fraction"] == 0

    if valid_sync_scorer_summary := summary.get("valid_sync_scorer"):
        assert valid_sync_scorer_summary["score"]["true_count"] == 2
        assert valid_sync_scorer_summary["score"]["true_fraction"] == 2 / 3

    if invalid_sync_scorer_summary := summary.get("invalid_sync_scorer"):
        assert invalid_sync_scorer_summary["score"]["true_count"] == 0
        assert invalid_sync_scorer_summary["score"]["true_fraction"] == 0


MODEL_PARAMS = [
    "op",
    # "function",
    # "callable_class",
]
DATASET_PARAMS = [
    "list",
    # "dataset",
]
SCORES_PARAMS = [
    # "sync",
    # "async",
    "combo",
]


def parametrize_evaluation_tests(fn):
    return pytest.mark.parametrize("model", MODEL_PARAMS, indirect=True)(
        pytest.mark.parametrize("dataset", DATASET_PARAMS, indirect=True)(
            pytest.mark.parametrize("scorers", SCORES_PARAMS, indirect=True)(fn)
        )
    )


@pytest.mark.parametrize("dataset", ["list", "dataset"], indirect=True)
@pytest.mark.parametrize("model", ["op", "function"], indirect=True)
@pytest.mark.asyncio
async def test_predict(client, model, dataset):
    ev = Evaluation2(dataset=dataset)

    eval_result = await ev.predict(model=model)
    check_eval_results(eval_result)


@pytest.mark.parametrize("dataset", ["list"], indirect=True)
@pytest.mark.parametrize("model", ["op"], indirect=True)
@pytest.mark.parametrize("scorers", ["combo"], indirect=True)
@pytest.mark.asyncio
async def test_score(client, scorers, model_calls):
    eval_result = EvaluationResult2.from_calls(model_calls)
    # TODO: This is an ugly side effect of being constrained to keep
    # the current shape of Evaluation and Dataset

    # Aside: I think the implementation of Dataset will bite us.  It really should
    # just be a simple interface on top of parquet.  The extra drill-down ref-tracking
    # is marginally more interesting but not worth the performance cost.
    ev = Evaluation2(dataset=eval_result.dataset, scorers=scorers)

    scores = await ev.score(eval_result=eval_result)
    check_scores(scores, scorers)


@pytest.mark.parametrize("dataset", ["list"], indirect=True)
@pytest.mark.parametrize("model", ["op"], indirect=True)
@pytest.mark.parametrize("scorers", ["combo_ops"], indirect=True)
@pytest.mark.asyncio
async def test_summarize(client, model, dataset, scorers, model_calls, scorer_calls):
    eval_result = EvaluationResult2.from_calls(model_calls)

    ev = Evaluation2(dataset=dataset, scorers=scorers)

    summary = await ev.summarize(eval_result)
    check_summary(summary, scorers)


# @parametrize_evaluation_tests
# @pytest.mark.asyncio
# async def test_evaluation_starting_with_model(client, model, dataset, scorers):
#     ev = Evaluation2(dataset=dataset, scorers=scorers)

#     predictions = await ev.predict(model=model)
#     check_predictions(predictions)

#     scores = await ev.score(predictions=predictions)
#     check_scores(scores, scorers)

#     summary = await ev.summarize(scores)
#     check_summary(summary, scorers)


# @parametrize_evaluation_tests
# @pytest.mark.asyncio
# async def test_evaluation_starting_with_predictions(client, model, dataset, scorers):
#     ev = Evaluation2(dataset=dataset, scorers=scorers)

#     inputs = [
#         {"a": 1, "b": 2},
#         {"a": 3, "b": 4},
#         {"a": 5, "b": 6},
#     ]
#     calls = []
#     for input_ in inputs:
#         _, call = model.call(**input_)
#         calls.append(call)

#     predictions = weave.Dataset.from_calls(calls)

#     scores = await ev.score(predictions=predictions)
#     check_scores(scores, scorers)

#     summary = await ev.summarize(scores)
#     check_summary(summary, scorers)


# @parametrize_evaluation_tests
# @pytest.mark.asyncio
# async def test_evaluation_starting_with_scores(client, model, dataset, scorers):
#     ev = Evaluation2(dataset=dataset, scorers=scorers)

#     scores = {
#         "valid_sync_scorer": [
#             {"score": False, "metadata": {}},
#             {"score": True, "metadata": {}},
#             {"score": True, "metadata": {}},
#         ],
#         "invalid_sync_scorer": [
#             {
#                 "score": None,
#                 "metadata": {"error": "argument of type 'BoxedInt' is not iterable"},
#             },
#             {
#                 "score": None,
#                 "metadata": {"error": "argument of type 'BoxedInt' is not iterable"},
#             },
#             {
#                 "score": None,
#                 "metadata": {"error": "argument of type 'BoxedInt' is not iterable"},
#             },
#         ],
#         "valid_async_scorer": [
#             {"score": False, "metadata": {}},
#             {"score": False, "metadata": {}},
#             {"score": True, "metadata": {}},
#         ],
#         "invalid_async_scorer": [
#             {
#                 "score": None,
#                 "metadata": {
#                     "error": "unsupported operand type(s) for +: 'BoxedInt' and 'str'"
#                 },
#             },
#             {
#                 "score": None,
#                 "metadata": {
#                     "error": "unsupported operand type(s) for +: 'BoxedInt' and 'str'"
#                 },
#             },
#             {
#                 "score": None,
#                 "metadata": {
#                     "error": "unsupported operand type(s) for +: 'BoxedInt' and 'str'"
#                 },
#             },
#         ],
#     }

#     summary = await ev.summarize(scores)
#     check_summary(summary, scorers)


# # def test_evaluation_end_to_end(client): ...


# # def test_evaluation_end_to_end_starting_with_model(client): ...


# # def test_evaluation_end_to_end_starting_with_predictions(client): ...


# # def test_evaluation_end_to_end_starting_with_scores(client): ...
