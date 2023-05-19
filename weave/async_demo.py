# This demonstrates how to create asynchronous Weave ops.

import time

import weave


@weave.op(
    render_info={"type": "function"},
    name="demo-slowmult",
    input_type={
        "a": weave.types.Int(),
        "b": weave.types.Int(),
        "sleep": weave.types.Float(),
    },
    output_type=weave.types.Function(
        output_type=weave.types.RunType(
            output=weave.types.Int(),
        )
    ),
)
def slowmult(a, b, sleep, _run=None):
    res = b
    for i in range(a - 1):
        res += b
        _run.print_("Current result %s" % res)
        time.sleep(sleep)
    _run.set_output(res)


class AsyncDemoModelType(weave.types.ObjectType):
    name = "asyncdemo_model"

    def __init__(self):
        pass

    def property_types(self):
        return {"id": weave.types.String()}


@weave.weave_class(weave_type=AsyncDemoModelType)
class AsyncDemoModel:
    def __init__(self, id):
        self.id = id

    @weave.op(
        name="asyncdemo_model-infer",
        input_type={"self": AsyncDemoModelType(), "x": weave.types.String()},
        output_type=weave.types.String(),
    )
    def infer(self, x):
        return x + "-abcd"


AsyncDemoModelType.instance_classes = AsyncDemoModel
AsyncDemoModelType.instance_class = AsyncDemoModel


class AsyncDemoTrainResultType(weave.types.ObjectType):
    name = "asyncdemo_trainresult"

    def __init__(self):
        pass

    def property_types(self):
        return {"id": weave.types.String()}


@weave.weave_class(weave_type=AsyncDemoTrainResultType)
class AsyncDemoTrainResult:
    def __init__(self, id):
        self.id = id

    @weave.op(
        name="asyncdemo_trainresult-model",
        input_type={"self": AsyncDemoTrainResultType()},
        output_type=AsyncDemoModelType(),
    )
    def model(self):
        return AsyncDemoModel(self.id)


AsyncDemoTrainResultType.instance_classes = AsyncDemoTrainResult
AsyncDemoTrainResultType.instance_class = AsyncDemoTrainResult


@weave.op(
    render_info={"type": "function"},
    name="demo-train",
    input_type={
        "dataset": weave.types.List(
            weave.types.TypedDict(
                {"prompt": weave.types.String(), "completion": weave.types.String()}
            )
        ),
    },
    output_type=weave.types.Function(
        output_type=weave.types.RunType(
            output=AsyncDemoTrainResultType(),
        )
    ),
)
def train(dataset, _run=None):
    _run.print_("starting")
    _run.set_output(AsyncDemoTrainResult(dataset[0]["prompt"]))
    _run.print_("done")
