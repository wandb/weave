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
    @weave.op
    def valid_sync_scorer(output: int) -> bool:
        return output > 5

    @weave.op
    def invalid_sync_scorer(output: str) -> bool:
        return "substring" in output

    @weave.op
    async def valid_async_scorer(output: int) -> bool:
        return output > 8

    @weave.op
    async def invalid_async_scorer(output: str) -> bool:
        return output + "text" == f"{output}text"

    sync_scorers = [valid_sync_scorer, invalid_sync_scorer]
    async_scorers = [valid_async_scorer, invalid_async_scorer]

    if request.param == "sync":
        return sync_scorers
    elif request.param == "async":
        return async_scorers
    elif request.param == "combo":
        return sync_scorers + async_scorers
    raise ValueError(f"Invalid scorers type: {request.param}")


@pytest.mark.parametrize("model", ["op"], indirect=True)
@pytest.mark.parametrize("dataset", ["list", "dataset"], indirect=True)
@pytest.mark.parametrize(
    "scorers",
    [
        "sync",
        "async",
        "combo",
    ],
    indirect=True,
)
@pytest.mark.asyncio
async def test_evaluation_starting_with_model(client, model, dataset, scorers):
    ev = Evaluation2(dataset=dataset, scorers=scorers)

    predictions = await ev.predict(model=model)
    assert len(predictions) == 3
    assert predictions[0]["output"] == 3
    assert predictions[1]["output"] == 7
    assert predictions[2]["output"] == 11

    scores = await ev.score(predictions=predictions)
    assert len(scores) == len(scorers)
    print(f"{scores=}")
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

    # summary = ev.summarize(scores)
    # assert summary["valid_sync_scorer"] == [True, True, True]
    # assert summary["invalid_sync_scorer"] == [False, False, False]
    # assert summary["valid_async_scorer"] == [True, True, True]
    # assert summary["invalid_async_scorer"] == [False, False, False]

    ...
    # ev = Evaluation2(dataset=[{"a": 1, "b": 2}, {"a": 3, "b": 4}], scorers=[model])


# def test_evaluation_starting_with_predictions(client): ...


# def test_evaluation_starting_with_scores(client): ...


# def test_evaluation_end_to_end(client): ...
