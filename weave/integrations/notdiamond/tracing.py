import dataclasses
import importlib
from typing import Callable, Optional

import weave
from weave.trace.autopatch import IntegrationSettings, OpSettings
from weave.trace.patcher import MultiPatcher, SymbolPatcher

_notdiamond_patcher: Optional[MultiPatcher] = None


def nd_wrapper(settings: OpSettings) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = dataclasses.asdict(settings)
        op = weave.op(fn, **op_kwargs)
        return op

    return wrapper


def passthrough_wrapper(settings: OpSettings) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = dataclasses.asdict(settings)
        return weave.op(fn, **op_kwargs)

    return wrapper


def get_notdiamond_patcher(
    settings: Optional[IntegrationSettings] = None,
) -> MultiPatcher:
    global _notdiamond_patcher

    if _notdiamond_patcher is not None:
        return _notdiamond_patcher

    if settings is None:
        settings = IntegrationSettings()

    base = settings.op_settings

    model_select_settings = dataclasses.replace(
        base,
        name=base.name or "NotDiamond.model_select",
    )
    async_model_select_settings = dataclasses.replace(
        base,
        name=base.name or "NotDiamond.amodel_select",
    )
    patched_client_functions = [
        SymbolPatcher(
            lambda: importlib.import_module("notdiamond"),
            "NotDiamond.amodel_select",
            passthrough_wrapper(async_model_select_settings),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("notdiamond"),
            "NotDiamond.model_select",
            passthrough_wrapper(model_select_settings),
        ),
    ]

    llm_config_init_settings = dataclasses.replace(
        base,
        name=base.name or "NotDiamond.LLMConfig.__init__",
    )
    llm_config_from_string_settings = dataclasses.replace(
        base,
        name=base.name or "NotDiamond.LLMConfig.from_string",
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

    custom_router_fit_settings = dataclasses.replace(
        base,
        name=base.name or "CustomRouter.fit",
    )
    custom_router_eval_settings = dataclasses.replace(
        base,
        name=base.name or "CustomRouter.eval",
    )
    patched_toolkit_functions = [
        SymbolPatcher(
            lambda: importlib.import_module("notdiamond.toolkit.custom_router"),
            "CustomRouter.fit",
            passthrough_wrapper(custom_router_fit_settings),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("notdiamond.toolkit.custom_router"),
            "CustomRouter.eval",
            passthrough_wrapper(custom_router_eval_settings),
        ),
    ]

    all_patched_functions = (
        patched_client_functions
        + patched_toolkit_functions
        + patched_llmconfig_functions
    )

    _notdiamond_patcher = MultiPatcher(all_patched_functions)

    return _notdiamond_patcher
