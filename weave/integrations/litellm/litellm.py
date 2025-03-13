from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any, Callable

import weave
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings, OpSettings
from weave.trace.op import _add_accumulator

if TYPE_CHECKING:
    from litellm.utils import ModelResponse

_litellm_patcher: MultiPatcher | None = None


# This accumulator is nearly identical to the mistral accumulator, just with different types.
def litellm_accumulator(
    acc: ModelResponse | None,
    value: ModelResponse,
) -> ModelResponse:
    # This import should be safe at this point
    from litellm.utils import Choices, Message, ModelResponse, Usage

    if acc is None:
        acc = ModelResponse(
            id=value.id,
            object=value.object,
            created=value.created,
            model=value.model,
            choices=[],
            usage=Usage(prompt_tokens=0, total_tokens=0, completion_tokens=None),
        )

    # Merge in the usage info
    if "usage" in value.model_fields_set and value.usage is not None:
        acc.usage.prompt_tokens += value.usage.prompt_tokens
        acc.usage.total_tokens += value.usage.total_tokens
        if acc.usage.completion_tokens is None:
            acc.usage.completion_tokens = value.usage.completion_tokens
        else:
            acc.usage.completion_tokens += value.usage.completion_tokens

    # Loop through the choices and add their deltas
    for delta_choice in value.choices:
        while delta_choice.index >= len(acc.choices):
            acc.choices.append(
                Choices(
                    index=len(acc.choices),
                    message=Message(role="", content=""),
                    finish_reason=None,
                )
            )
        acc.choices[delta_choice.index].message.role = (
            delta_choice.delta.role or acc.choices[delta_choice.index].message.role
        )
        acc.choices[delta_choice.index].message.content += (
            delta_choice.delta.content or ""
        )
        if delta_choice.delta.tool_calls:
            if acc.choices[delta_choice.index].message.tool_calls is None:
                acc.choices[delta_choice.index].message.tool_calls = []
            acc.choices[
                delta_choice.index
            ].message.tool_calls += delta_choice.delta.tool_calls
        acc.choices[delta_choice.index].finish_reason = (
            delta_choice.finish_reason or acc.choices[delta_choice.index].finish_reason
        )

    return acc


# LiteLLM does so odd stuff with pydantic objects which result in our auto
# serialization not working correctly. Here we just blindly dump to a dict instead.
def litellm_on_finish_post_processor(value: Any) -> Any:
    import pydantic

    value_to_finish = value
    if isinstance(value, pydantic.BaseModel):
        value_to_finish = value.model_dump()

    return value_to_finish


# Unlike other integrations, streaming is based on input flag, not
def should_use_accumulator(inputs: dict) -> bool:
    return isinstance(inputs, dict) and bool(inputs.get("stream"))


def make_wrapper(settings: OpSettings) -> Callable:
    def litellm_wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        op = weave.op(fn, **op_kwargs)
        return _add_accumulator(
            op,  # type: ignore
            make_accumulator=lambda inputs: litellm_accumulator,
            should_accumulate=should_use_accumulator,
            on_finish_post_processor=litellm_on_finish_post_processor,
        )

    return litellm_wrapper


def get_litellm_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _litellm_patcher
    if _litellm_patcher is not None:
        return _litellm_patcher

    base = settings.op_settings

    completion_settings = base.model_copy(
        update={"name": base.name or "litellm.completion"}
    )
    acompletion_settings = base.model_copy(
        update={"name": base.name or "litellm.acompletion"}
    )

    _litellm_patcher = MultiPatcher(
        [
            SymbolPatcher(
                lambda: importlib.import_module("litellm"),
                "completion",
                make_wrapper(completion_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("litellm"),
                "acompletion",
                make_wrapper(acompletion_settings),
            ),
        ]
    )

    return _litellm_patcher
