import asyncio

import pytest

import weave
from weave import Evaluation
from weave.flow.eval import EvaluationResults2, is_async_callable


@pytest.fixture
def model(request):
    if request.param == "op":

        @weave.op
        def add(a: int, b: int) -> int:
            return a + b

        return add

    elif request.param == "function":

        def add(a: int, b: int) -> int:
            return a + b

        return add

    elif request.param == "callable_class":

        class Add:
            def __call__(self, a: int, b: int) -> int:
                return a + b

        return Add()

    raise ValueError("Invalid model type requested")


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
    raise ValueError("Invalid dataset type requested")


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

    sync_scorers = [valid_sync_scorer_op, invalid_sync_scorer_op]
    async_scorers = [valid_async_scorer_op, invalid_async_scorer_op]
    sync_scorer_ops = [valid_sync_scorer_op, invalid_sync_scorer_op]
    async_scorer_ops = [valid_async_scorer_op, invalid_async_scorer_op]

    if request.param == "sync":
        return sync_scorers
    elif request.param == "async":
        return async_scorers
    elif request.param == "sync+async":
        return sync_scorers + async_scorers
    elif request.param == "sync+async op":
        return sync_scorer_ops + async_scorer_ops
    raise ValueError("Invalid scorer type requested")


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


#######################


@pytest.mark.parametrize("dataset", ["dataset"], indirect=True)
@pytest.mark.parametrize("model", ["op", "function"], indirect=True)
@pytest.mark.asyncio
async def test_predict(client, model, dataset):
    ev = Evaluation(dataset=dataset)

    eval_results = await ev.predict(model=model)
    assert eval_results.dataset == dataset
    assert eval_results.predictions == [3, 7, 11]
    assert eval_results.scores is None


@pytest.mark.parametrize("dataset", ["dataset"], indirect=True)
@pytest.mark.parametrize("model", ["op"], indirect=True)
@pytest.mark.parametrize(
    "scorers", ["sync", "async", "sync+async", "sync+async op"], indirect=True
)
@pytest.mark.asyncio
async def test_score(client, model_calls, scorers, request):
    # The use of this pattern is unfortunate.  I wish users could just declare Evaluation
    # and maybe get back the EvaluationResults2 on the object itself?  Hmm, maybe
    # an alternate constructor could work?
    eval_results = EvaluationResults2.from_calls(model_calls)
    ev = Evaluation(dataset=eval_results.dataset, scorers=scorers)

    updated_eval_results = await ev.score(eval_results=eval_results)

    expected = {
        "valid_sync_scorer": [False, True, True],
        "invalid_sync_scorer": [None, None, None],
        "valid_async_scorer": [False, False, True],
        "invalid_async_scorer": [None, None, None],
    }
    for scorer in scorers:
        name = scorer.__name__
        assert updated_eval_results.scores[name] == expected[name]


@pytest.mark.parametrize("dataset", ["dataset"], indirect=True)
@pytest.mark.parametrize("model", ["op"], indirect=True)
@pytest.mark.parametrize("scorers", ["sync"], indirect=True)
@pytest.mark.asyncio
async def test_summarize(client, model_calls, scorers, scorer_calls, request):
    eval_results = EvaluationResults2.from_calls(model_calls, scorer_calls=scorer_calls)
    ev = Evaluation(dataset=eval_results.dataset, scorers=scorers)

    summary = await ev.summarize(eval_results)

    expected = {
        "valid_sync_scorer": {"true_count": 2, "true_fraction": 2 / 3},
        "invalid_sync_scorer": None,
        "a": {"mean": 3},
        "b": {"mean": 4},
    }
    assert summary == expected


@pytest.mark.parametrize("dataset", ["dataset"], indirect=True)
@pytest.mark.parametrize("model", ["op"], indirect=True)
@pytest.mark.parametrize("scorers", ["sync"], indirect=True)
@pytest.mark.asyncio
async def test_evaluate_from_model(client, model, dataset, scorers):
    ev = Evaluation(dataset=dataset, scorers=scorers)

    summary = await ev.evaluate(model=model)

    expected = {
        "valid_sync_scorer": {"true_count": 2, "true_fraction": 2 / 3},
        "invalid_sync_scorer": None,
        "a": {"mean": 3},
        "b": {"mean": 4},
    }
    assert summary == expected
