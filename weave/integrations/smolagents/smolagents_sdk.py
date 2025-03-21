import importlib
from typing import Any, Callable, Optional, Union

import weave
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings, OpSettings
from weave.trace.serialization.serialize import dictify

_smolagents_patcher: Optional[MultiPatcher] = None


def smolagents_postprocess_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    if "self" in inputs:
        inputs["self"] = dictify(inputs["self"])
    return inputs


def smolagents_wrapper(settings: OpSettings) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        if not op_kwargs.get("postprocess_inputs"):
            op_kwargs["postprocess_inputs"] = smolagents_postprocess_inputs

        op = weave.op(fn, **op_kwargs)
        return op

    return wrapper


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
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "MultiStepAgent.execute_tool_call",
            smolagents_wrapper(
                base.model_copy(
                    update={
                        "name": base.name
                        or "smolagents.MultiStepAgent.execute_tool_call"
                    }
                )
            ),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "MultiStepAgent.extract_action",
            smolagents_wrapper(
                base.model_copy(
                    update={
                        "name": base.name or "smolagents.MultiStepAgent.extract_action"
                    }
                )
            ),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "MultiStepAgent.provide_final_answer",
            smolagents_wrapper(
                base.model_copy(
                    update={
                        "name": base.name
                        or "smolagents.MultiStepAgent.provide_final_answer"
                    }
                )
            ),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "MultiStepAgent.run",
            smolagents_wrapper(
                base.model_copy(
                    update={"name": base.name or "smolagents.MultiStepAgent.run"}
                )
            ),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "MultiStepAgent.__call__",
            smolagents_wrapper(
                base.model_copy(
                    update={"name": base.name or "smolagents.MultiStepAgent"}
                )
            ),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "MultiStepAgent.write_memory_to_messages",
            smolagents_wrapper(
                base.model_copy(
                    update={
                        "name": base.name
                        or "smolagents.MultiStepAgent.write_memory_to_messages"
                    }
                )
            ),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "CodeAgent.step",
            smolagents_wrapper(
                base.model_copy(
                    update={"name": base.name or "smolagents.CodeAgent.step"}
                )
            ),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "ToolCallingAgent.step",
            smolagents_wrapper(
                base.model_copy(
                    update={"name": base.name or "smolagents.ToolCallingAgent.step"}
                )
            ),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents.models"),
            "HfApiModel.__call__",
            smolagents_wrapper(
                base.model_copy(update={"name": base.name or "smolagents.HfApiModel"})
            ),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents.models"),
            "OpenAIServerModel.__call__",
            smolagents_wrapper(
                base.model_copy(
                    update={"name": base.name or "smolagents.OpenAIServerModel"}
                )
            ),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents.models"),
            "TransformersModel.__call__",
            smolagents_wrapper(
                base.model_copy(
                    update={"name": base.name or "smolagents.TransformersModel"}
                )
            ),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents.models"),
            "LiteLLMModel.__call__",
            smolagents_wrapper(
                base.model_copy(update={"name": base.name or "smolagents.LiteLLMModel"})
            ),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents.models"),
            "AzureOpenAIServerModel.__call__",
            smolagents_wrapper(
                base.model_copy(
                    update={"name": base.name or "smolagents.AzureOpenAIServerModel"}
                )
            ),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "Tool.__call__",
            smolagents_wrapper(
                base.model_copy(update={"name": base.name or "smolagents.Tool"})
            ),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "PythonInterpreterTool.__call__",
            smolagents_wrapper(
                base.model_copy(
                    update={"name": base.name or "smolagents.PythonInterpreterTool"}
                )
            ),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "FinalAnswerTool.__call__",
            smolagents_wrapper(
                base.model_copy(
                    update={"name": base.name or "smolagents.FinalAnswerTool"}
                )
            ),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "UserInputTool.__call__",
            smolagents_wrapper(
                base.model_copy(
                    update={"name": base.name or "smolagents.UserInputTool"}
                )
            ),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "DuckDuckGoSearchTool.__call__",
            smolagents_wrapper(
                base.model_copy(
                    update={"name": base.name or "smolagents.DuckDuckGoSearchTool"}
                )
            ),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "GoogleSearchTool.__call__",
            smolagents_wrapper(
                base.model_copy(
                    update={"name": base.name or "smolagents.GoogleSearchTool"}
                )
            ),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "VisitWebpageTool.__call__",
            smolagents_wrapper(
                base.model_copy(
                    update={"name": base.name or "smolagents.VisitWebpageTool"}
                )
            ),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "SpeechToTextTool.__call__",
            smolagents_wrapper(
                base.model_copy(
                    update={"name": base.name or "smolagents.SpeechToTextTool"}
                )
            ),
        ),
    ]

    _smolagents_patcher = MultiPatcher(patchers)
    return _smolagents_patcher
