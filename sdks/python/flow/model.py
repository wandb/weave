from typing import Callable

from weave.flow.obj import Object

INFER_METHOD_NAMES = {"predict", "infer", "forward", "invoke"}


class MissingInferenceMethodError(Exception): ...


class Model(Object):
    """
    Intended to capture a combination of code and data the operates on an input.
    For example it might call an LLM with a prompt to make a prediction or generate
    text.

    When you change the attributes or the code that defines your model, these changes
    will be logged and the version will be updated. This ensures that you can compare
    the predictions across different versions of your model. Use this to iterate on
    prompts or to try the latest LLM and compare predictions across different settings

    Examples:

    ```python
    class YourModel(Model):
        attribute1: str
        attribute2: int

        @weave.op()
        def predict(self, input_data: str) -> dict:
            # Model logic goes here
            prediction = self.attribute1 + ' ' + input_data
            return {'pred': prediction}
    ```
    """

    # TODO: should be infer: Callable

    def get_infer_method(self) -> Callable:
        for name in INFER_METHOD_NAMES:
            if infer_method := getattr(self, name, None):
                return infer_method
        raise MissingInferenceMethodError(
            f"Missing a method with name in ({INFER_METHOD_NAMES})"
        )


def get_infer_method(model: Model) -> Callable:
    for name in INFER_METHOD_NAMES:
        if (infer_method := getattr(model, name, None)) is not None:
            return infer_method
    raise MissingInferenceMethodError(
        f"Missing a method with name in ({INFER_METHOD_NAMES})"
    )
