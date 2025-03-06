import inspect
import textwrap
import time
import traceback
from dataclasses import dataclass
from typing import Any, Callable, Optional, Union

from rich import print

from weave.flow.obj import Object
from weave.trace.isinstance import weave_isinstance
from weave.trace.op import Op, OpCallError, as_op, is_op
from weave.trace.op_caller import async_call_op
from weave.trace.weave_client import Call

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


def get_infer_method(model: Model) -> Op:
    for name in INFER_METHOD_NAMES:
        if (infer_method := getattr(model, name, None)) is not None:
            if not is_op(infer_method):
                raise ValueError(
                    f"Model {model} must implement `{name}` as a weave.op() decorated function."
                )
            return infer_method
    raise MissingInferenceMethodError(
        f"Missing a method with name in ({INFER_METHOD_NAMES})"
    )


# Using `dataclass` because pydantic does not like `Call` as a property
@dataclass
class ApplyModelSuccess:
    model_output: Any
    model_call: Call
    model_latency: float


@dataclass
class ApplyModelError:
    model_latency: float


ApplyModelResult = Union[ApplyModelSuccess, ApplyModelError]
PreprocessModelInput = Callable[[dict], dict]


async def apply_model_async(
    model: Union[Op, Model],
    example: dict,
    preprocess_model_input: Optional[PreprocessModelInput] = None,
) -> ApplyModelResult:
    """Asynchronously applies a model (class or operation) to a given example.

    This function handles the execution of a model against input data with proper type checking
    and client context management. It supports both class-based models and operation-based models.

    Args:
        model: The model to apply, can be either a class type or a Weave Operation (Op)
        example: The input data to process through the model
        preprocess_model_input: A function that preprocesses the example before passing it to the model

    Returns:
        Any: The result of applying the model to the example

    Raises:
        TypeError: If the model is neither a class type nor an Op
        ValueError: If type checking fails between model input requirements and example
    """
    if preprocess_model_input is None:
        model_input = example
    else:
        model_input = preprocess_model_input(example)  # type: ignore

    model_self = None
    model_predict_op: Op
    if is_op(model):
        model_predict_op = as_op(model)
    elif weave_isinstance(model, Model):
        model_self = model
        model_predict_op = get_infer_method(model)
    else:
        raise ValueError(f"Unknown model type: {model}")

    model_predict_fn_name = model_predict_op.name

    predict_signature = inspect.signature(model_predict_op)
    model_predict_arg_names = list(predict_signature.parameters.keys())

    model_predict_args = {
        k: v for k, v in model_input.items() if k in model_predict_arg_names
    }
    try:
        model_predict_op = as_op(model_predict_op)
        if model_self is not None:
            model_predict_args = {
                **model_predict_args,
                "self": model_self,
            }
        model_start_time = time.time()
        model_output, model_call = await async_call_op(
            model_predict_op, **model_predict_args
        )
    except OpCallError as e:
        dataset_column_names = list(example.keys())
        dataset_column_names_str = ", ".join(dataset_column_names[:3])
        if len(dataset_column_names) > 3:
            dataset_column_names_str += ", ..."
        required_arg_names = [
            param.name
            for param in predict_signature.parameters.values()
            if param.default == inspect.Parameter.empty
        ]

        message = textwrap.dedent(
            f"""
            Call error: {e}

            Options for resolving:
            a. change {model_predict_fn_name} argument names to match a subset of dataset column names: {dataset_column_names_str}
            b. change dataset column names to match expected {model_predict_fn_name} argument names: {required_arg_names}
            c. construct Evaluation with a preprocess_model_input function that accepts a dataset example and returns a dict with keys expected by {model_predict_fn_name}
            """
        )
        raise OpCallError(message)
    except Exception:
        print("model_output failed")
        traceback.print_exc()
        return ApplyModelError(model_latency=time.time() - model_start_time)

    return ApplyModelSuccess(
        model_output=model_output,
        model_call=model_call,
        model_latency=time.time() - model_start_time,
    )
