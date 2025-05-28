from __future__ import annotations

import importlib
from typing import Any, Callable

import weave
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings, OpSettings
from weave.trace.serialization.serialize import dictify

_smolagents_patcher: MultiPatcher | None = None


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
) -> SymbolPatcher | None:
    try:
        module = importlib.import_module(base_symbol)
    except ImportError:
        return None
    class_name, _, method_name = attribute_name.partition(".")

    # Check if the class exists in the module
    if not hasattr(module, class_name):
        return None

    cls = getattr(module, class_name)

    # Check if the method exists in the class
    if method_name and not hasattr(cls, method_name):
        return None

    display_name = base_symbol + "." + attribute_name
    display_name = (
        display_name.replace(".__call__", "")
        if attribute_name.endswith(".__call__")
        else display_name
    )
    return SymbolPatcher(
        lambda: module,
        attribute_name,
        smolagents_wrapper(
            settings.model_copy(update={"name": settings.name or display_name})
        ),
    )


def get_multi_step_agent_patchers(
    agent_class_name: str, settings: OpSettings
) -> list[SymbolPatcher | None]:
    return [
        get_symbol_patcher("smolagents", f"{agent_class_name}.run", settings),
        get_symbol_patcher(
            "smolagents", f"{agent_class_name}.provide_final_answer", settings
        ),
        get_symbol_patcher(
            "smolagents", f"{agent_class_name}.execute_tool_call", settings
        ),
        get_symbol_patcher("smolagents", f"{agent_class_name}.__call__", settings),
        get_symbol_patcher("smolagents", f"{agent_class_name}.step", settings),
    ]


def get_smolagents_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _smolagents_patcher
    if _smolagents_patcher is not None:
        return _smolagents_patcher

    base = settings.op_settings
    patchers = [
        patcher
        for patcher in [
            # Patch model-related classes
            get_symbol_patcher("smolagents", "TransformersModel.__call__", base),
            get_symbol_patcher("smolagents", "HfApiModel.__call__", base),
            get_symbol_patcher("smolagents", "InferenceClientModel.__call__", base),
            get_symbol_patcher("smolagents", "LiteLLMModel.__call__", base),
            get_symbol_patcher("smolagents", "OpenAIServerModel.__call__", base),
            get_symbol_patcher("smolagents", "AzureOpenAIServerModel.__call__", base),
            get_symbol_patcher("smolagents", "MLXModel.__call__", base),
            get_symbol_patcher("smolagents", "VLLMModel.__call__", base),
            # Patch relevant Agent functions
            *get_multi_step_agent_patchers("MultiStepAgent", base),
            *get_multi_step_agent_patchers("ToolCallingAgent", base),
            *get_multi_step_agent_patchers("CodeAgent", base),
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
        # Filter out None values
        # Some symbols may not exist in every Agent type for example
        # `execute_tool_call` is available only in ToolCallingAgent and it's subtypes
        # We don't want to raise an error if the symbol doesn't exist
        # and we don't want to add a patcher for it
        # so we filter out None values when `get_multi_step_agent_patchers` returns None for that symbol
        # this should keep it generic for all Agent types
        if patcher is not None
    ]

    _smolagents_patcher = MultiPatcher(patchers)
    return _smolagents_patcher
