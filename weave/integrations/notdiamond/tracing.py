from __future__ import annotations

import importlib
from typing import Callable

import weave
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings, OpSettings

_notdiamond_patcher: MultiPatcher | None = None


def nd_wrapper(settings: OpSettings) -> Callable[[Callable], Callable]:
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

    global _notdiamond_patcher
    if _notdiamond_patcher is not None:
        return _notdiamond_patcher

    base = settings.op_settings

    model_select_settings = base.model_copy(
        update={"name": base.name or "NotDiamond.model_select"}
    )
    async_model_select_settings = base.model_copy(
        update={"name": base.name or "NotDiamond.amodel_select"}
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
        update={"name": base.name or "NotDiamond.toolkit.custom_router.fit"}
    )
    toolkit_custom_router_eval_settings = base.model_copy(
        update={"name": base.name or "NotDiamond.toolkit.custom_router.eval"}
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

    all_patched_functions = (
        patched_client_functions
        + patched_toolkit_functions
        + patched_llmconfig_functions
    )

    _notdiamond_patcher = MultiPatcher(all_patched_functions)

    return _notdiamond_patcher
