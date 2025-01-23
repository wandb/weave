import importlib
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, Optional, Union

import weave
from weave.trace.autopatch import IntegrationSettings
from weave.trace.op_extensions.accumulator import add_accumulator
from weave.trace.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher

if TYPE_CHECKING:
    from huggingface_hub.inference._generated.types.chat_completion import (
        ChatCompletionOutput,
        ChatCompletionStreamOutput,
    )

_huggingface_patcher: Optional[MultiPatcher] = None


def huggingface_accumulator(
    acc: Optional[Union["ChatCompletionStreamOutput", "ChatCompletionOutput"]],
    value: "ChatCompletionStreamOutput",
) -> "ChatCompletionOutput":
    from huggingface_hub.inference._generated.types.chat_completion import (
        ChatCompletionOutput,
        ChatCompletionOutputComplete,
        ChatCompletionOutputMessage,
        ChatCompletionOutputUsage,
    )

    if acc is None:
        acc = ChatCompletionOutput(
            choices=[
                ChatCompletionOutputComplete(
                    index=choice.index,
                    message=ChatCompletionOutputMessage(
                        content=choice.delta.content or "",
                        role=choice.delta.role or "assistant",
                    ),
                    finish_reason=None,
                )
                for choice in value.choices
            ],
            created=value.created,
            id=value.id,
            model=value.model,
            system_fingerprint=value.system_fingerprint,
            usage=value.usage,
        )
        return acc

    # Accumulate subsequent chunks
    for idx, value_choice in enumerate(value.choices):
        acc.choices[idx].message.content += value_choice.delta.content or ""

    if acc.usage is None:
        acc.usage = ChatCompletionOutputUsage(
            completion_tokens=0, prompt_tokens=0, total_tokens=0
        )
    # # For some reason, value.usage is always coming `None`
    # # Might be a bug in `huggingface_hub.InferenceClient`
    # if value.usage is not None:
    #     acc.usage.completion_tokens += value.usage.completion_tokens
    #     acc.usage.prompt_tokens += value.usage.prompt_tokens
    #     acc.usage.total_tokens += value.usage.total_tokens
    return acc


def huggingface_wrapper_sync(name: str) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op = weave.op()(fn)
        op.name = name
        return add_accumulator(
            op,  # type: ignore
            make_accumulator=lambda inputs: huggingface_accumulator,
            should_accumulate=lambda inputs: isinstance(inputs, dict)
            and bool(inputs.get("stream")),
        )

    return wrapper


def huggingface_wrapper_async(name: str) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        def _fn_wrapper(fn: Callable) -> Callable:
            @wraps(fn)
            async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await fn(*args, **kwargs)

            return _async_wrapper

        "We need to do this so we can check if `stream` is used"
        op = weave.op()(_fn_wrapper(fn))
        op.name = name  # type: ignore
        return add_accumulator(
            op,  # type: ignore
            make_accumulator=lambda inputs: huggingface_accumulator,
            should_accumulate=lambda inputs: isinstance(inputs, dict)
            and bool(inputs.get("stream")),
        )

    return wrapper


def get_huggingface_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _huggingface_patcher
    if _huggingface_patcher is not None:
        return _huggingface_patcher

    _huggingface_patcher = MultiPatcher(
        [
            SymbolPatcher(
                lambda: importlib.import_module("huggingface_hub"),
                "InferenceClient.chat_completion",
                huggingface_wrapper_sync(
                    name="huggingface_hub.InferenceClient.chat_completion"
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("huggingface_hub"),
                "AsyncInferenceClient.chat_completion",
                huggingface_wrapper_async(
                    name="huggingface_hub.AsyncInferenceClient.chat_completion"
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("huggingface_hub"),
                "InferenceClient.document_question_answering",
                huggingface_wrapper_sync(
                    name="huggingface_hub.InferenceClient.document_question_answering"
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("huggingface_hub"),
                "AsyncInferenceClient.document_question_answering",
                huggingface_wrapper_sync(
                    name="huggingface_hub.AsyncInferenceClient.document_question_answering"
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("huggingface_hub"),
                "InferenceClient.visual_question_answering",
                huggingface_wrapper_sync(
                    name="huggingface_hub.InferenceClient.visual_question_answering"
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("huggingface_hub"),
                "AsyncInferenceClient.visual_question_answering",
                huggingface_wrapper_sync(
                    name="huggingface_hub.AsyncInferenceClient.visual_question_answering"
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("huggingface_hub"),
                "InferenceClient.fill_mask",
                huggingface_wrapper_sync(
                    name="huggingface_hub.InferenceClient.fill_mask"
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("huggingface_hub"),
                "AsyncInferenceClient.fill_mask",
                huggingface_wrapper_sync(
                    name="huggingface_hub.AsyncInferenceClient.fill_mask"
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("huggingface_hub"),
                "InferenceClient.question_answering",
                huggingface_wrapper_sync(
                    name="huggingface_hub.InferenceClient.question_answering"
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("huggingface_hub"),
                "AsyncInferenceClient.question_answering",
                huggingface_wrapper_sync(
                    name="huggingface_hub.AsyncInferenceClient.question_answering"
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("huggingface_hub"),
                "InferenceClient.sentence_similarity",
                huggingface_wrapper_sync(
                    name="huggingface_hub.InferenceClient.sentence_similarity"
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("huggingface_hub"),
                "AsyncInferenceClient.sentence_similarity",
                huggingface_wrapper_sync(
                    name="huggingface_hub.AsyncInferenceClient.sentence_similarity"
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("huggingface_hub"),
                "InferenceClient.summarization",
                huggingface_wrapper_sync(
                    name="huggingface_hub.InferenceClient.summarization"
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("huggingface_hub"),
                "AsyncInferenceClient.summarization",
                huggingface_wrapper_sync(
                    name="huggingface_hub.AsyncInferenceClient.summarization"
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("huggingface_hub"),
                "InferenceClient.table_question_answering",
                huggingface_wrapper_sync(
                    name="huggingface_hub.InferenceClient.table_question_answering"
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("huggingface_hub"),
                "AsyncInferenceClient.table_question_answering",
                huggingface_wrapper_sync(
                    name="huggingface_hub.AsyncInferenceClient.table_question_answering"
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("huggingface_hub"),
                "InferenceClient.text_classification",
                huggingface_wrapper_sync(
                    name="huggingface_hub.InferenceClient.text_classification"
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("huggingface_hub"),
                "AsyncInferenceClient.text_classification",
                huggingface_wrapper_sync(
                    name="huggingface_hub.AsyncInferenceClient.text_classification"
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("huggingface_hub"),
                "InferenceClient.token_classification",
                huggingface_wrapper_sync(
                    name="huggingface_hub.InferenceClient.token_classification"
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("huggingface_hub"),
                "AsyncInferenceClient.token_classification",
                huggingface_wrapper_sync(
                    name="huggingface_hub.AsyncInferenceClient.token_classification"
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("huggingface_hub"),
                "InferenceClient.translation",
                huggingface_wrapper_sync(
                    name="huggingface_hub.InferenceClient.translation"
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("huggingface_hub"),
                "AsyncInferenceClient.translation",
                huggingface_wrapper_sync(
                    name="huggingface_hub.AsyncInferenceClient.translation"
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("huggingface_hub"),
                "InferenceClient.zero_shot_classification",
                huggingface_wrapper_sync(
                    name="huggingface_hub.InferenceClient.zero_shot_classification"
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("huggingface_hub"),
                "AsyncInferenceClient.zero_shot_classification",
                huggingface_wrapper_sync(
                    name="huggingface_hub.AsyncInferenceClient.zero_shot_classification"
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("huggingface_hub"),
                "InferenceClient.text_to_image",
                huggingface_wrapper_sync(
                    name="huggingface_hub.InferenceClient.text_to_image"
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("huggingface_hub"),
                "AsyncInferenceClient.text_to_image",
                huggingface_wrapper_sync(
                    name="huggingface_hub.AsyncInferenceClient.text_to_image"
                ),
            ),
        ]
    )
    return _huggingface_patcher
