from typing import Callable
from weave.flow.obj import Object


class Model(Object):
    """A `Model` is a combination of data (which can include configuration, trained model weights, or other information) and code that defines how the model operates. By structuring your code to be compatible with this API, you benefit from a structured way to version your application so you can more systematically keep track of your experiments.

    To create a model in Weave, you need the following:
    - a class that inherits from `weave.Model`
    - type definitions on all attributes
    - a typed `predict` function with `@weave.op()` decorator

    ```python
    from weave import Model
    import weave

    class YourModel(Model):
        attribute1: str
        attribute2: int

        @weave.op()
        def predict(self, input_data: str) -> dict:
            # Model logic goes here
            prediction = self.attribute1 + ' ' + input_data
            return {'pred': prediction}
    ```

    You can call the model as usual with:
    ```python
    import weave
    weave.init('project-name')

    model = YourModel(attribute1='hello', attribute2=5)
    model.predict('world')
    ```

    This will track the model settings along with the inputs and outputs anytime you call `predict`.
    """

    # TODO: should be infer: Callable
    def get_infer_method(self) -> Callable:
        for infer_method_names in ("predict", "infer", "forward"):
            infer_method = getattr(self, infer_method_names, None)
            if infer_method:
                return infer_method
        raise ValueError(
            f"Model {self} does not have a predict, infer, or forward method."
        )


def get_infer_method(model: Model) -> Callable:
    for infer_method_names in ("predict", "infer", "forward"):
        infer_method = getattr(model, infer_method_names, None)
        if infer_method:
            return infer_method
    raise ValueError(
        f"Model {model} does not have a predict, infer, or forward method."
    )
