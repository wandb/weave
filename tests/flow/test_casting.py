from typing import Any

import pytest

import weave
from weave.flow.casting import cast_to_dataset, cast_to_scorer
from weave.trace.op import is_op


@pytest.fixture
def valid_dataset(client, request):
    data = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]

    if request.param == "dataset":
        return weave.Dataset(rows=data)
    if request.param == "list":
        return data
    if request.param == "ref":
        ds = weave.Dataset(rows=data)
        ref = weave.publish(ds)
        return ref
    if request.param == "remote dataset":
        ds = weave.Dataset(rows=data)
        ref = weave.publish(ds)
        return ref.get(objectify=False)


@pytest.fixture
def valid_scorer(client, request):
    if request.param == "scorer":

        class MyScorer(weave.Scorer):
            def score(self, *, output: Any, **kwargs: Any) -> Any:
                return output

        return MyScorer()

    if request.param == "op":

        @weave.op
        def scorer(output: Any, **kwargs: Any) -> Any:
            return output

        return scorer

    if request.param == "ref":

        @weave.op
        def scorer(output: Any, **kwargs: Any) -> Any:
            return output

        ref = weave.publish(scorer)
        return ref


@pytest.mark.parametrize(
    "valid_dataset", ["dataset", "list", "ref", "remote dataset"], indirect=True
)
def test_cast_to_dataset(valid_dataset):
    res = cast_to_dataset(valid_dataset)

    assert isinstance(res, weave.Dataset)


@pytest.mark.parametrize("valid_scorer", ["scorer", "op", "ref"], indirect=True)
def test_cast_to_scorer(valid_scorer):
    res = cast_to_scorer(valid_scorer)

    assert isinstance(res, weave.Scorer) or is_op(res)
