from typing import Any, Optional
from contextlib import contextmanager

import weave
from weave.flow.eval_imperative import EvaluationLogger
from weave.integrations.dspy.dspy_utils import (
    dspy_postprocess_inputs,
    dump_dspy_objects,
    get_op_name_for_callback,
)
from weave.trace.context import weave_client_context as weave_client_context
from weave.trace.serialization.serialize import dictify
from weave.trace.weave_client import Call
from weave.trace import settings

import_failed = False

try:
    from dspy.utils.callback import BaseCallback
except ImportError:
    import_failed = True


@contextmanager
def suppress_weave_call_links():
    """Context manager to temporarily suppress Weave call link printing.
    
    This is used during DSPy evaluations to avoid cluttering the output
    with individual call URLs while still allowing the main evaluation URL.
    """
    # Get the current context variable for print_call_link
    print_call_link_var = settings._context_vars["print_call_link"]
    
    # Save the current value
    current_value = print_call_link_var.get()
    
    # Temporarily set to False
    token = print_call_link_var.set(False)
    
    try:
        yield
    finally:
        # Restore the original value
        print_call_link_var.reset(token)

if not import_failed:

    class WeaveCallback(BaseCallback):
        def __init__(self) -> None:
            self._call_map: dict[str, Call] = {}
            # Track active evaluations for imperative logging
            self._active_evaluations: dict[str, EvaluationLogger] = {}
            self._evaluation_predictions: dict[str, list] = {}
            # Track when we're suppressing URLs during evaluation
            self._evaluation_call_ids: set[str] = set()
            self._suppression_active: bool = False

        def on_module_start(
            self, call_id: str, instance: Any, inputs: dict[str, Any]
        ) -> None:
            # Suppress URL printing for individual calls during evaluation
            if self._suppression_active:
                with suppress_weave_call_links():
                    self._create_module_call(call_id, instance, inputs)
            else:
                self._create_module_call(call_id, instance, inputs)
        
        def _create_module_call(
            self, call_id: str, instance: Any, inputs: dict[str, Any]
        ) -> None:
            """Helper method to create module calls."""
            gc = weave_client_context.require_weave_client()
            if instance is not None:
                inputs = {"self": dictify(instance), **inputs}
                if hasattr(instance, "signature"):
                    if hasattr(instance.signature, "model_json_schema"):
                        inputs["self"]["signature"] = (
                            instance.signature.model_json_schema()
                        )
                    else:
                        inputs["self"]["signature"] = instance.signature

            op_name = get_op_name_for_callback(instance, inputs)
            self._call_map[call_id] = gc.create_call(
                op_name,
                inputs=dspy_postprocess_inputs(inputs),
                display_name=op_name,
            )
            
            # Check if we're in an active evaluation and this is a prediction
            if self._active_evaluations:
                try:
                    # Store inputs for potential prediction logging
                    self._call_map[call_id]._dspy_eval_inputs = inputs
                except Exception:
                    pass

        def on_module_end(
            self,
            call_id: str,
            outputs: Optional[Any],
            exception: Optional[Exception] = None,
        ) -> None:
            gc = weave_client_context.require_weave_client()
            
            # Check if this is part of an evaluation and log prediction
            if call_id in self._call_map and self._active_evaluations:
                try:
                    call_obj = self._call_map[call_id]
                    if hasattr(call_obj, '_dspy_eval_inputs') and outputs is not None and exception is None:
                        # This looks like a prediction we should log
                        inputs = call_obj._dspy_eval_inputs
                        
                        # Find the active evaluation (for simplicity, use the first one)
                        # In a more robust implementation, we'd track which evaluation each call belongs to
                        for eval_call_id, eval_logger in self._active_evaluations.items():
                            try:
                                # Extract input data for Weave logging
                                prediction_inputs = {}
                                for key, value in inputs.items():
                                    if key != "self" and not key.startswith("_"):
                                        prediction_inputs[key] = value
                                
                                # Log the prediction
                                pred_logger = eval_logger.log_prediction(
                                    inputs=prediction_inputs,
                                    output=dump_dspy_objects(outputs)
                                )
                                
                                # For now, log a simple correctness score placeholder
                                # In a real implementation, this would come from the metric evaluation
                                pred_logger.log_score("prediction_logged", True)
                                pred_logger.finish()
                                
                                # Track the prediction for cleanup
                                if eval_call_id not in self._evaluation_predictions:
                                    self._evaluation_predictions[eval_call_id] = []
                                self._evaluation_predictions[eval_call_id].append(pred_logger)
                                
                                break  # Only log to one evaluation
                            except Exception as e:
                                print(f"Warning: Failed to log prediction to Weave: {e}")
                                pass
                except Exception:
                    pass
            
            if call_id in self._call_map:
                gc.finish_call(
                    self._call_map[call_id], dump_dspy_objects(outputs), exception
                )

        def on_lm_start(
            self,
            call_id: str,
            instance: Any,
            inputs: dict[str, Any],
        ):
            """A handler triggered when __call__ method of dspy.LM instance is called.

            Args:
                call_id: A unique identifier for the call. Can be used to connect start/end handlers.
                instance: The LM instance.
                inputs: The inputs to the LM's __call__ method. Each arguments is stored as
                    a key-value pair in a dictionary.
            """
            # Suppress URL printing for LM calls during evaluation
            if self._suppression_active:
                with suppress_weave_call_links():
                    self._create_lm_call(call_id, instance, inputs)
            else:
                self._create_lm_call(call_id, instance, inputs)
                
        def _create_lm_call(
            self, call_id: str, instance: Any, inputs: dict[str, Any]
        ) -> None:
            """Helper method to create LM calls."""
            gc = weave_client_context.require_weave_client()
            if instance is not None:
                inputs = {"self": dictify(instance), **inputs}

            op_name = get_op_name_for_callback(instance, inputs)
            self._call_map[call_id] = gc.create_call(
                op_name,
                inputs=dspy_postprocess_inputs(inputs),
                display_name=op_name,
            )

        def on_lm_end(
            self,
            call_id: str,
            outputs: dict[str, Any] | None,
            exception: Exception | None = None,
        ):
            """A handler triggered after __call__ method of dspy.LM instance is executed.

            Args:
                call_id: A unique identifier for the call. Can be used to connect start/end handlers.
                outputs: The outputs of the LM's __call__ method. If the method is interrupted by
                    an exception, this will be None.
                exception: If an exception is raised during the execution, it will be stored here.
            """
            gc = weave_client_context.require_weave_client()
            if call_id in self._call_map:
                gc.finish_call(
                    self._call_map[call_id], dump_dspy_objects(outputs), exception
                )

        def on_tool_start(
            self, call_id: str, instance: Any, inputs: dict[str, Any]
        ) -> None:
            # Suppress URL printing for tool calls during evaluation
            if self._suppression_active:
                with suppress_weave_call_links():
                    self._create_tool_call(call_id, instance, inputs)
            else:
                self._create_tool_call(call_id, instance, inputs)
                
        def _create_tool_call(
            self, call_id: str, instance: Any, inputs: dict[str, Any]
        ) -> None:
            """Helper method to create tool calls."""
            gc = weave_client_context.require_weave_client()
            if instance is not None:
                inputs = {"self": dictify(instance), **inputs}

            if hasattr(instance, "func"):
                instance.func = weave.op(instance.func)

            op_name = get_op_name_for_callback(instance, inputs)
            self._call_map[call_id] = gc.create_call(
                op_name,
                inputs=dspy_postprocess_inputs(inputs),
                display_name=op_name,
            )

        def on_tool_end(
            self,
            call_id: str,
            outputs: Optional[dict[str, Any]],
            exception: Optional[Exception] = None,
        ) -> None:
            gc = weave_client_context.require_weave_client()
            if call_id in self._call_map:
                gc.finish_call(
                    self._call_map[call_id], dump_dspy_objects(outputs), exception
                )

        def on_evaluate_start(
            self,
            call_id: str,
            instance: Any,
            inputs: dict[str, Any],
        ):
            """A handler triggered when evaluation is started.

            Args:
                call_id: A unique identifier for the call. Can be used to connect start/end handlers.
                instance: The Evaluate instance.
                inputs: The inputs to the Evaluate's __call__ method. Each arguments is stored as
                    a key-value pair in a dictionary.
            """
            # Create the evaluation call normally (this should show its URL)
            gc = weave_client_context.require_weave_client()
            if instance is not None:
                inputs = {"self": dictify(instance), **inputs}
            op_name = get_op_name_for_callback(instance, inputs)
            self._call_map[call_id] = gc.create_call(
                op_name,
                inputs=dspy_postprocess_inputs(inputs),
                display_name=op_name,
            )
            
            # Track this as an evaluation call and start suppressing other URLs
            self._evaluation_call_ids.add(call_id)
            self._suppression_active = True
            
            # Create Weave EvaluationLogger for imperative evaluation
            try:
                program = inputs.get("program")
                if program:
                    # Extract model info from the program
                    model_name = getattr(program, "__class__", {})
                    if hasattr(model_name, "__name__"):
                        model_name = model_name.__name__
                    else:
                        model_name = str(model_name)
                else:
                    model_name = "DSPyModule"
                
                # Create evaluation logger
                eval_logger = EvaluationLogger(
                    name=f"DSPy Evaluation - {model_name}",
                    model=model_name,
                    dataset="DSPy Dataset"
                )
                
                self._active_evaluations[call_id] = eval_logger
                self._evaluation_predictions[call_id] = []
                
            except Exception as e:
                # Don't let evaluation logging errors break DSPy evaluation
                print(f"Warning: Failed to create Weave evaluation logger: {e}")
                pass

        def on_evaluate_end(
            self,
            call_id: str,
            outputs: Any | None,
            exception: Exception | None = None,
        ):
            """A handler triggered after evaluation is executed.

            Args:
                call_id: A unique identifier for the call. Can be used to connect start/end handlers.
                outputs: The outputs of the Evaluate's __call__ method. If the method is interrupted by
                    an exception, this will be None.
                exception: If an exception is raised during the execution, it will be stored here.
            """
            # Stop suppressing URLs now that evaluation is ending
            if call_id in self._evaluation_call_ids:
                self._suppression_active = False
                self._evaluation_call_ids.remove(call_id)
            
            gc = weave_client_context.require_weave_client()
            if call_id in self._call_map:
                gc.finish_call(
                    self._call_map[call_id], dump_dspy_objects(outputs), exception
                )
            
            # Finalize Weave evaluation logging
            if call_id in self._active_evaluations:
                try:
                    eval_logger = self._active_evaluations[call_id]
                    predictions = self._evaluation_predictions.get(call_id, [])
                    
                    # Finish any remaining predictions
                    for pred_logger in predictions:
                        try:
                            if not pred_logger._has_finished:
                                pred_logger.finish()
                        except Exception:
                            pass  # Best effort cleanup
                    
                    # Create summary from DSPy outputs
                    summary = {}
                    if outputs is not None:
                        if hasattr(outputs, 'score'):
                            summary["score"] = outputs.score
                        elif isinstance(outputs, (int, float)):
                            summary["score"] = outputs
                        else:
                            summary["score"] = str(outputs)
                    
                    # Log summary and finalize evaluation
                    eval_logger.log_summary(summary)
                    
                    # Clean up
                    del self._active_evaluations[call_id]
                    del self._evaluation_predictions[call_id]
                    
                except Exception as e:
                    # Don't let cleanup errors break DSPy evaluation
                    print(f"Warning: Failed to finalize Weave evaluation: {e}")
                    pass
