from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Callable, Any

import weave
from weave.trace.autopatch import IntegrationSettings, OpSettings
from weave.trace.op_extensions.accumulator import add_accumulator
from weave.trace.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.serialize import dictify
from smolagents import PythonInterpreterTool

_smolagents_patcher: MultiPatcher | None = None


def smolagents_postprocess_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    if "self" in inputs:
        inputs["self"] = dictify(inputs["self"])
    return inputs


def smolagents_wrapper(name: str) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op = weave.op(fn, postprocess_inputs=smolagents_postprocess_inputs, postprocess_output=lambda x: dictify(x))
        op.name = name  # type: ignore
        return op

    return wrapper


def get_smolagents_patcher():
    multi_step_agent_patcher = [
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "MultiStepAgent.run",
            smolagents_wrapper("smolagents.MultiStepAgent.run"),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "MultiStepAgent.run",
            smolagents_wrapper("smolagents.MultiStepAgent.direct_run"),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "MultiStepAgent.run",
            smolagents_wrapper("smolagents.MultiStepAgent.execute_tool_call"),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "MultiStepAgent.run",
            smolagents_wrapper("smolagents.MultiStepAgent.extract_action"),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "MultiStepAgent.run",
            smolagents_wrapper("smolagents.MultiStepAgent.planning_step"),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "MultiStepAgent.run",
            smolagents_wrapper("smolagents.MultiStepAgent.provide_final_answer"),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "MultiStepAgent.run",
            smolagents_wrapper("smolagents.MultiStepAgent.step"),
        ),
    ]

    additional_agents_patcher = [
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "ToolCallingAgent.run",
            smolagents_wrapper("smolagents.ToolCallingAgent.run"),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "ToolCallingAgent.run",
            smolagents_wrapper("smolagents.ToolCallingAgent.step"),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "CodeAgent.run",
            smolagents_wrapper("smolagents.CodeAgent.run"),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "CodeAgent.run",
            smolagents_wrapper("smolagents.CodeAgent.step"),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "ManagedAgent.__call__",
            smolagents_wrapper("smolagents.ManagedAgent"),
        ),
    ]

    models_patcher = [
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "Model.__call__",
            smolagents_wrapper("smolagents.Model"),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "HfApiModel.__call__",
            smolagents_wrapper("smolagents.HfApiModel"),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "TransformersModel.__call__",
            smolagents_wrapper("smolagents.TransformersModel"),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "LiteLLMModel.__call__",
            smolagents_wrapper("smolagents.LiteLLMModel"),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "OpenAIServerModel.__call__",
            smolagents_wrapper("smolagents.OpenAIServerModel"),
        ),
    ]

    tools_patcher = [
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "Tool.__call__",
            smolagents_wrapper("smolagents.Tool"),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "Tool.forward",
            smolagents_wrapper("smolagents.Tool.forward"),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "PythonInterpreterTool.forward",
            smolagents_wrapper("smolagents.PythonInterpreterTool.forward"),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "FinalAnswerTool.forward",
            smolagents_wrapper("smolagents.FinalAnswerTool.forward"),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "UserInputTool.forward",
            smolagents_wrapper("smolagents.UserInputTool.forward"),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "DuckDuckGoSearchTool.forward",
            smolagents_wrapper("smolagents.DuckDuckGoSearchTool.forward"),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "GoogleSearchTool.forward",
            smolagents_wrapper("smolagents.GoogleSearchTool.forward"),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "VisitWebpageTool.forward",
            smolagents_wrapper("smolagents.VisitWebpageTool.forward"),
        ),
    ]

    return MultiPatcher(
        [
            *multi_step_agent_patcher,
            *additional_agents_patcher,
            *models_patcher,
            *tools_patcher,
        ]
    )
