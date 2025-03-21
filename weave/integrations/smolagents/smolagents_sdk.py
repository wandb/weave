import importlib
from typing import Any, Callable, Optional, Union

import weave
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings, OpSettings
from weave.trace.serialization.serialize import dictify

_smolagents_patcher: Optional[MultiPatcher] = None


def smolagents_postprocess_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    if "self" in inputs:
        dictified_self = dictify(inputs["self"])
        # Make sure that the object type is rendered correctly in the Weave UI
        if "__class__" not in dictified_self:
            dictified_self["__class__"] = {
                "module": inputs["self"].__class__.__module__,
                "qualname": inputs["self"].__class__.__qualname__,
                "name": inputs["self"].__class__.__name__,
            }
        inputs["self"] = dictified_self
    return inputs


def smolagents_wrapper(settings: OpSettings) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        if not op_kwargs.get("postprocess_inputs"):
            op_kwargs["postprocess_inputs"] = smolagents_postprocess_inputs

        op = weave.op(fn, **op_kwargs)
        return op

    return wrapper


def get_symbol_patcher(
    base_symbol: str, attribute_name: str, settings: OpSettings
) -> SymbolPatcher:
    display_name = base_symbol + "." + attribute_name
    display_name = (
        display_name.replace(".__call__", "")
        if attribute_name.endswith(".__call__")
        else display_name
    )
    return SymbolPatcher(
        lambda: importlib.import_module(base_symbol),
        attribute_name,
        smolagents_wrapper(
            settings.model_copy(update={"name": settings.name or display_name})
        ),
    )


def get_smolagents_patcher(
    settings: Optional[IntegrationSettings] = None,
) -> Union[MultiPatcher, NoOpPatcher]:
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _smolagents_patcher
    if _smolagents_patcher is not None:
        return _smolagents_patcher

    base = settings.op_settings
    patchers = [
        # Patch model-related classes
        get_symbol_patcher("smolagents", "TransformersModel.__call__", base),
        get_symbol_patcher("smolagents", "HfApiModel.__call__", base),
        get_symbol_patcher("smolagents", "LiteLLMModel.__call__", base),
        get_symbol_patcher("smolagents", "OpenAIServerModel.__call__", base),
        get_symbol_patcher("smolagents", "AzureOpenAIServerModel.__call__", base),
        get_symbol_patcher("smolagents", "MLXModel.__call__", base),
        get_symbol_patcher("smolagents", "VLLMModel.__call__", base),
        # Patch relevant MultiStepAgent functions
        get_symbol_patcher("smolagents", "MultiStepAgent.run", base),
        get_symbol_patcher(
            "smolagents", "MultiStepAgent.write_memory_to_messages", base
        ),
        get_symbol_patcher("smolagents", "MultiStepAgent.extract_action", base),
        get_symbol_patcher("smolagents", "MultiStepAgent.provide_final_answer", base),
        get_symbol_patcher("smolagents", "MultiStepAgent.execute_tool_call", base),
        get_symbol_patcher("smolagents", "MultiStepAgent.__call__", base),
        # Patch relevant Agent functions
        get_symbol_patcher(
            "smolagents", "ToolCallingAgent.initialize_system_prompt", base
        ),
        get_symbol_patcher("smolagents", "ToolCallingAgent.step", base),
        get_symbol_patcher("smolagents", "CodeAgent.initialize_system_prompt", base),
        get_symbol_patcher("smolagents", "CodeAgent.step", base),
        # Patch relevant Tool functions
        get_symbol_patcher("smolagents", "Tool.forward", base),
        get_symbol_patcher("smolagents", "Tool.__call__", base),
        get_symbol_patcher("smolagents", "PipelineTool.forward", base),
        get_symbol_patcher("smolagents", "PipelineTool.__call__", base),
        get_symbol_patcher("smolagents", "PythonInterpreterTool.forward", base),
        get_symbol_patcher("smolagents", "PythonInterpreterTool.__call__", base),
        get_symbol_patcher("smolagents", "FinalAnswerTool.forward", base),
        get_symbol_patcher("smolagents", "FinalAnswerTool.__call__", base),
        get_symbol_patcher("smolagents", "UserInputTool.forward", base),
        get_symbol_patcher("smolagents", "UserInputTool.__call__", base),
        get_symbol_patcher("smolagents", "DuckDuckGoSearchTool.forward", base),
        get_symbol_patcher("smolagents", "DuckDuckGoSearchTool.__call__", base),
        get_symbol_patcher("smolagents", "GoogleSearchTool.forward", base),
        get_symbol_patcher("smolagents", "GoogleSearchTool.__call__", base),
        get_symbol_patcher("smolagents", "VisitWebpageTool.forward", base),
        get_symbol_patcher("smolagents", "VisitWebpageTool.__call__", base),
        get_symbol_patcher("smolagents", "SpeechToTextTool.forward", base),
        get_symbol_patcher("smolagents", "SpeechToTextTool.__call__", base),
    ]

    _smolagents_patcher = MultiPatcher(patchers)
    return _smolagents_patcher
