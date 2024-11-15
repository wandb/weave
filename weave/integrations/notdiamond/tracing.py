import importlib
from typing import Callable

import weave
from weave.trace.patcher import MultiPatcher, SymbolPatcher


def nd_wrapper(name: str) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op = weave.op()(fn)
        op.name = name  # type: ignore
        return op

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


patched_client_functions = _patch_client_op("model_select")

patched_llmconfig_functions = [
    SymbolPatcher(
        lambda: importlib.import_module("notdiamond"),
        "LLMConfig.__init__",
        weave.op(),
    ),
    SymbolPatcher(
        lambda: importlib.import_module("notdiamond"),
        "LLMConfig.from_string",
        weave.op(),
    ),
]

patched_toolkit_functions = [
    SymbolPatcher(
        lambda: importlib.import_module("notdiamond.toolkit.custom_router"),
        "CustomRouter.fit",
        weave.op(),
    ),
    SymbolPatcher(
        lambda: importlib.import_module("notdiamond.toolkit.custom_router"),
        "CustomRouter.eval",
        weave.op(),
    ),
]

all_patched_functions = (
    patched_client_functions + patched_toolkit_functions + patched_llmconfig_functions
)

notdiamond_patcher = MultiPatcher(all_patched_functions)
