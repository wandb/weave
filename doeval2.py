import weave
from weave import weaveflow

with weave.local_client():
    dataset = weave.publish(
        weaveflow.Dataset(
            [
                {"id": "0", "x": 0, "y": 0, "out": 0},
                {"id": "0", "x": 1, "y": 1, "out": 1},
                {"id": "0", "x": 2, "y": 1, "out": 2},
            ]
        ),
        "datasets",
    )

    @weave.type()
    class AddModel(weaveflow.Model):
        @weave.op()
        def predict(self, ex):
            return ex["x"] + ex["y"]

    @weave.type()
    class MultModel(weaveflow.Model):
        @weave.op()
        def predict(ex):
            return ex["x"]

    @weave.op()
    def extract_output(ex):
        return ex["out"]

    eval = weaveflow.ScoreExactMatch(extract_output)
    add_model = AddModel()
    result = weaveflow.evaluate2(eval, dataset, add_model)
    print("RESULT", weave.obj_ref(result))
