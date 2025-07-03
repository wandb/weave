"""
Model execution script for isolated user contexts.

This module contains the actual model execution logic that runs within
the isolated child process. It's designed to be minimal and focused on
just the execution task, with all security and context management
handled by the parent process.

The module handles:
- Loading models from references
- Processing different input types (direct values or references)
- Executing model predictions with proper tracing
"""

from __future__ import annotations

from weave.trace.context.weave_client_context import require_weave_client
from weave.trace.refs import parse_uri
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.interface.builtin_object_classes.llm_structured_model import (
    LLMStructuredCompletionModel,
)


def run_model(req: tsi.RunModelReq) -> tsi.RunModelRes:
    """
    Execute a model with the given inputs in an isolated context.

    This function is designed to run within a child process with a properly
    scoped WeaveClient. It loads the model from a reference, processes the
    inputs, and executes the model's predict method.

    Args:
        req: Model execution request containing:
            - model_ref: URI reference to the model object
            - inputs: Either direct values or a reference to input values
            - project_id: Project scope for the execution
            - wb_user_id: User context for the execution

    Returns:
        Model execution response containing:
            - output: The model's prediction result
            - call_id: Unique identifier for the traced call

    Raises:
        TypeError: If the model reference doesn't point to a valid LLMStructuredCompletionModel
                  or if the inputs are not a dictionary when resolved
        ValueError: If the input type is neither 'value' nor 'ref'
    """
    # Get the scoped client from context (set up by parent process)
    client = require_weave_client()

    # Load the model from its reference
    loaded_model = client.get(parse_uri(req.model_ref))
    if not isinstance(loaded_model, LLMStructuredCompletionModel):
        raise TypeError(
            f"Invalid model reference: expected LLMStructuredCompletionModel, "
            f"got {type(loaded_model).__name__}"
        )

    # Process inputs based on their type
    inputs_value: dict
    if isinstance(req.inputs, dict):
        # Direct value provided
        inputs_value = req.inputs

    elif isinstance(req.inputs, str):
        # Reference to inputs - load from Weave
        inputs_value = client.get(parse_uri(req.inputs))

    else:
        raise ValueError(
            f"Invalid input type: {req.inputs.input_type}. "
            "Must be either 'value' or 'ref'"
        )

    # Validate inputs are a dictionary (required for **kwargs expansion)
    if not isinstance(inputs_value, dict):
        raise TypeError(
            f"Inputs value must be a dictionary, got {type(inputs_value).__name__}"
        )

    # Execute the model with tracing
    # Note: This is synchronous because the model interface is not async yet
    # TODO: Support async models when the interface is updated
    result, call = loaded_model.predict.call(loaded_model, **inputs_value)

    # Return the result and trace information
    return tsi.RunModelRes(output=result, call_id=call.id)
