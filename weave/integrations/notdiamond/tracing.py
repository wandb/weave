from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any

import weave
from weave.integrations.integration_metadata import (
    library_integration,
    with_integration_metadata,
)
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings, OpSettings

_notdiamond_patcher: MultiPatcher | None = None
NOTDIAMOND_INTEGRATION = library_integration("notdiamond")


def not_diamond_wrapper(settings: OpSettings) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        op = weave.op(fn, **op_kwargs)
        return op

    return wrapper


def passthrough_wrapper(settings: OpSettings) -> Callable:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        return weave.op(fn, **op_kwargs)

    return wrapper


def _postprocess_model_output(output: Any) -> Any:
    model_dump = getattr(output, "model_dump", None)
    if callable(model_dump):
        return model_dump(mode="json")
    return output


def _chain_postprocess_output(
    postprocess_output: Callable[[Any], Any] | None,
) -> Callable[[Any], Any]:
    def postprocess(output: Any) -> Any:
        if postprocess_output is not None:
            output = postprocess_output(output)
        return _postprocess_model_output(output)

    return postprocess


def _patch_client_op(method_name: str) -> list[SymbolPatcher]:
    return [
        SymbolPatcher(
            lambda: importlib.import_module("notdiamond"),
            f"NotDiamond.a{method_name}",
            weave.op(),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("notdiamond"),
            f"NotDiamond.{method_name}",
            weave.op(),
        ),
    ]


def get_notdiamond_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _notdiamond_patcher  # noqa: PLW0603
    if _notdiamond_patcher is not None:
        return _notdiamond_patcher

    base = with_integration_metadata(settings.op_settings, NOTDIAMOND_INTEGRATION)

    model_select_settings = base.model_copy(
        update={
            "name": base.name or "NotDiamond.model_select",
            "kind": base.kind or "tool",
        }
    )
    async_model_select_settings = base.model_copy(
        update={
            "name": base.name or "NotDiamond.amodel_select",
            "kind": base.kind or "tool",
        }
    )
    patched_client_functions = [
        SymbolPatcher(
            lambda: importlib.import_module("notdiamond"),
            "NotDiamond.model_select",
            passthrough_wrapper(model_select_settings),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("notdiamond"),
            "NotDiamond.amodel_select",
            passthrough_wrapper(async_model_select_settings),
        ),
    ]

    llm_config_init_settings = base.model_copy(
        update={"name": base.name or "NotDiamond.LLMConfig.__init__"}
    )
    llm_config_from_string_settings = base.model_copy(
        update={"name": base.name or "NotDiamond.LLMConfig.from_string"}
    )
    patched_llmconfig_functions = [
        SymbolPatcher(
            lambda: importlib.import_module("notdiamond"),
            "LLMConfig.__init__",
            passthrough_wrapper(llm_config_init_settings),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("notdiamond"),
            "LLMConfig.from_string",
            passthrough_wrapper(llm_config_from_string_settings),
        ),
    ]

    toolkit_custom_router_fit_settings = base.model_copy(
        update={
            "name": base.name or "NotDiamond.toolkit.custom_router.fit",
            "kind": base.kind or "tool",
        }
    )
    toolkit_custom_router_eval_settings = base.model_copy(
        update={
            "name": base.name or "NotDiamond.toolkit.custom_router.eval",
            "kind": base.kind or "tool",
        }
    )
    patched_toolkit_functions = [
        SymbolPatcher(
            lambda: importlib.import_module("notdiamond.toolkit.custom_router"),
            "CustomRouter.fit",
            passthrough_wrapper(toolkit_custom_router_fit_settings),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("notdiamond.toolkit.custom_router"),
            "CustomRouter.eval",
            passthrough_wrapper(toolkit_custom_router_eval_settings),
        ),
    ]
    model_router_select_settings = base.model_copy(
        update={
            "name": base.name or "NotDiamond.model_router.select_model",
            "kind": base.kind or "tool",
            "postprocess_output": _chain_postprocess_output(base.postprocess_output),
        }
    )
    custom_router_train_settings = base.model_copy(
        update={
            "name": base.name or "NotDiamond.custom_router.train_custom_router",
            "kind": base.kind or "tool",
            "postprocess_output": _chain_postprocess_output(base.postprocess_output),
        }
    )
    patched_resource_functions = [
        SymbolPatcher(
            lambda: importlib.import_module("notdiamond.resources.model_router"),
            "ModelRouterResource.select_model",
            passthrough_wrapper(model_router_select_settings),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("notdiamond.resources.custom_router"),
            "CustomRouterResource.train_custom_router",
            passthrough_wrapper(custom_router_train_settings),
        ),
    ]

    all_patched_functions = (
        patched_client_functions
        + patched_resource_functions
        + patched_toolkit_functions
        + patched_llmconfig_functions
    )

    _notdiamond_patcher = MultiPatcher(all_patched_functions)

    return _notdiamond_patcher
