from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any, Callable

import weave
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings, OpSettings
from weave.trace.weave_client import Call

if TYPE_CHECKING:
    pass


_exa_patcher: MultiPatcher | None = None


def exa_on_finish(call: Call, output: Any, exception: BaseException | None) -> None:
    if getattr(output, "cost_dollars", None) and call.summary is not None:
        # Create a usage entry for Exa with the cost information
        exa_model_id = "exa"

        # Get the cost as a float to ensure it's a numeric value
        cost_value = float(output.cost_dollars.total)
        print(f"The cost value is {cost_value}")

        # Initialize the usage dictionary if it doesn't exist
        if "usage" not in call.summary:
            call.summary["usage"] = {}

        # Add Exa usage entry
        # We use 1 token and set the token cost to match the actual cost from Exa
        call.summary["usage"][exa_model_id] = {
            "requests": 1,
            "prompt_tokens": 1,
            "completion_tokens": 0,
            "total_tokens": 1,
            "prompt_token_cost": cost_value,  # This will be used directly by the token costs system
            "completion_token_cost": 0.0,
        }


def postprocess_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    "I want to remove the 'kwargs' key from the inputs if it is empty (when kwargs = {})"
    if "kwargs" in inputs and not inputs["kwargs"]:
        del inputs["kwargs"]
    return inputs


def exa_wrapper(settings: OpSettings) -> Callable:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        op = weave.op(fn, **op_kwargs)
        op._set_on_finish_handler(exa_on_finish)
        return op

    return wrapper


def get_exa_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _exa_patcher
    if _exa_patcher is not None:
        return _exa_patcher

    base = settings.op_settings
    search_settings = base.model_copy(
        update={
            "name": base.name or "Exa.search",
            "postprocess_inputs": postprocess_inputs,
        }
    )
    search_and_contents_settings = base.model_copy(
        update={
            "name": base.name or "Exa.search_and_contents",
            "postprocess_inputs": postprocess_inputs,
        }
    )

    _exa_patcher = MultiPatcher(
        [
            # Patch the search method
            SymbolPatcher(
                lambda: importlib.import_module("exa_py.api"),
                "Exa.search",
                exa_wrapper(search_settings),
            ),
            # Patch the search_and_contents method
            SymbolPatcher(
                lambda: importlib.import_module("exa_py.api"),
                "Exa.search_and_contents",
                exa_wrapper(search_and_contents_settings),
            ),
        ]
    )

    return _exa_patcher
