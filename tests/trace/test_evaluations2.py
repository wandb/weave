import pytest

import weave
from weave.flow.eval import Evaluation2


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


def check_predictions(predictions):
    assert len(predictions) == 3
    assert predictions[0]["output"] == 3
    assert predictions[1]["output"] == 7
    assert predictions[2]["output"] == 11


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


@pytest.mark.parametrize(
    "model",
    [
        "op",
        "function",
        "callable_class",
    ],
    indirect=True,
)
@pytest.mark.parametrize("dataset", ["list", "dataset"], indirect=True)
@pytest.mark.parametrize("scorers", ["sync", "async", "combo"], indirect=True)
@pytest.mark.asyncio
async def test_evaluation_starting_with_model(client, model, dataset, scorers):
    ev = Evaluation2(dataset=dataset, scorers=scorers)

    predictions = await ev.predict(model=model)
    check_predictions(predictions)

    scores = await ev.score(predictions=predictions)
    check_scores(scores, scorers)

    summary = await ev.summarize(scores)
    check_summary(summary, scorers)


# def test_evaluation_starting_with_predictions(client): ...


# def test_evaluation_starting_with_scores(client): ...


# def test_evaluation_end_to_end(client): ...
