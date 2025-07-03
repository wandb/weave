from __future__ import annotations

from weave.trace.context.weave_client_context import require_weave_client
from weave.trace.refs import parse_uri
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.interface.builtin_object_classes.llm_structured_model import (
    LLMStructuredCompletionModel,
)


def run_model(req: tsi.RunModelReq) -> tsi.RunModelRes:
    """Execute a model with the given inputs.

    Args:
        req: Model execution request containing model reference and inputs.

    Returns:
        Model execution response with output and call ID.

    Raises:
        TypeError: If model reference is invalid or inputs are not a dictionary.
        ValueError: If input type is invalid.
    """
    client = require_weave_client()
    loaded_model = client.get(parse_uri(req.model_ref))
    if not isinstance(loaded_model, LLMStructuredCompletionModel):
        raise TypeError("Invalid model reference")

    inputs_value: dict
    if req.inputs.input_type == "value":
        inputs_value = req.inputs.value

    elif req.inputs.input_type == "ref":
        inputs_value = client.get(parse_uri(req.inputs.value))

    else:
        raise ValueError("Invalid input type")

    if not isinstance(inputs_value, dict):
        raise TypeError("Inputs value must be a dictionary")

    # Sad - this should be async, but we can't do that because the model is not async
    result, call = loaded_model.predict.call(loaded_model, **inputs_value)
    return tsi.RunModelRes(output=result, call_id=call.id)
