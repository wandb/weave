import importlib
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, Optional, Union

import weave
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings, OpSettings
from weave.trace.op import _add_accumulator
from weave.trace.serialization.serialize import dictify

if TYPE_CHECKING:
    from huggingface_hub.inference._generated.types.chat_completion import (
        ChatCompletionOutput,
        ChatCompletionStreamOutput,
    )

_huggingface_patcher: Optional[MultiPatcher] = None


def huggingface_postprocess_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    if "self" in inputs:
        inputs["self"] = dictify(inputs["self"])
    return inputs


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
    # # For some reason, value.usage is always `None` when streaming.
    # # This might be a bug in `huggingface_hub.InferenceClient`
    # if value.usage is not None:
    #     acc.usage.completion_tokens += value.usage.completion_tokens
    #     acc.usage.prompt_tokens += value.usage.prompt_tokens
    #     acc.usage.total_tokens += value.usage.total_tokens
    return acc


def huggingface_wrapper_sync(settings: OpSettings) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        if not op_kwargs.get("postprocess_inputs"):
            op_kwargs["postprocess_inputs"] = huggingface_postprocess_inputs

        op = weave.op(fn, **op_kwargs)
        return _add_accumulator(
            op,  # type: ignore
            make_accumulator=lambda inputs: huggingface_accumulator,
            should_accumulate=lambda inputs: isinstance(inputs, dict)
            and bool(inputs.get("stream")),
        )

    return wrapper


def huggingface_wrapper_async(settings: OpSettings) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        def _fn_wrapper(fn: Callable) -> Callable:
            @wraps(fn)
            async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await fn(*args, **kwargs)

            return _async_wrapper

        op_kwargs = settings.model_dump()
        if not op_kwargs.get("postprocess_inputs"):
            op_kwargs["postprocess_inputs"] = huggingface_postprocess_inputs

        op = weave.op(_fn_wrapper(fn), **op_kwargs)
        return _add_accumulator(
            op,  # type: ignore
            make_accumulator=lambda inputs: huggingface_accumulator,
            should_accumulate=lambda inputs: isinstance(inputs, dict)
            and bool(inputs.get("stream")),
        )

    return wrapper


def get_huggingface_patcher(
    settings: Optional[IntegrationSettings] = None,
) -> Union[MultiPatcher, NoOpPatcher]:
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _huggingface_patcher
    if _huggingface_patcher is not None:
        return _huggingface_patcher

    base = settings.op_settings
    patchers = []

    chat_completion_settings = base.model_copy(
        update={"name": base.name or "huggingface_hub.InferenceClient.chat_completion"}
    )
    patchers.append(
        SymbolPatcher(
            lambda: importlib.import_module("huggingface_hub"),
            "InferenceClient.chat_completion",
            huggingface_wrapper_sync(chat_completion_settings),
        )
    )

    chat_completion_async_settings = base.model_copy(
        update={
            "name": base.name or "huggingface_hub.AsyncInferenceClient.chat_completion"
        }
    )
    patchers.append(
        SymbolPatcher(
            lambda: importlib.import_module("huggingface_hub"),
            "AsyncInferenceClient.chat_completion",
            huggingface_wrapper_async(chat_completion_async_settings),
        )
    )

    document_question_answering_settings = base.model_copy(
        update={
            "name": base.name
            or "huggingface_hub.InferenceClient.document_question_answering"
        }
    )
    patchers.append(
        SymbolPatcher(
            lambda: importlib.import_module("huggingface_hub"),
            "InferenceClient.document_question_answering",
            huggingface_wrapper_sync(document_question_answering_settings),
        )
    )

    document_question_answering_async_settings = base.model_copy(
        update={
            "name": base.name
            or "huggingface_hub.AsyncInferenceClient.document_question_answering"
        }
    )
    patchers.append(
        SymbolPatcher(
            lambda: importlib.import_module("huggingface_hub"),
            "AsyncInferenceClient.document_question_answering",
            huggingface_wrapper_sync(document_question_answering_async_settings),
        )
    )
    visual_question_answering_settings = base.model_copy(
        update={
            "name": base.name
            or "huggingface_hub.InferenceClient.visual_question_answering"
        }
    )
    patchers.append(
        SymbolPatcher(
            lambda: importlib.import_module("huggingface_hub"),
            "InferenceClient.visual_question_answering",
            huggingface_wrapper_sync(visual_question_answering_settings),
        )
    )
    visual_question_answering_async_settings = base.model_copy(
        update={
            "name": base.name
            or "huggingface_hub.AsyncInferenceClient.visual_question_answering"
        }
    )
    patchers.append(
        SymbolPatcher(
            lambda: importlib.import_module("huggingface_hub"),
            "AsyncInferenceClient.visual_question_answering",
            huggingface_wrapper_sync(visual_question_answering_async_settings),
        )
    )
    fill_mask_settings = base.model_copy(
        update={"name": base.name or "huggingface_hub.InferenceClient.fill_mask"}
    )
    patchers.append(
        SymbolPatcher(
            lambda: importlib.import_module("huggingface_hub"),
            "InferenceClient.fill_mask",
            huggingface_wrapper_sync(fill_mask_settings),
        )
    )

    fill_mask_async_settings = base.model_copy(
        update={"name": base.name or "huggingface_hub.AsyncInferenceClient.fill_mask"}
    )
    patchers.append(
        SymbolPatcher(
            lambda: importlib.import_module("huggingface_hub"),
            "AsyncInferenceClient.fill_mask",
            huggingface_wrapper_sync(fill_mask_async_settings),
        )
    )

    question_answering_settings = base.model_copy(
        update={
            "name": base.name or "huggingface_hub.InferenceClient.question_answering"
        }
    )
    patchers.append(
        SymbolPatcher(
            lambda: importlib.import_module("huggingface_hub"),
            "InferenceClient.question_answering",
            huggingface_wrapper_sync(question_answering_settings),
        )
    )

    question_answering_async_settings = base.model_copy(
        update={
            "name": base.name
            or "huggingface_hub.AsyncInferenceClient.question_answering"
        }
    )
    patchers.append(
        SymbolPatcher(
            lambda: importlib.import_module("huggingface_hub"),
            "AsyncInferenceClient.question_answering",
            huggingface_wrapper_sync(question_answering_async_settings),
        )
    )

    sentence_similarity_settings = base.model_copy(
        update={
            "name": base.name or "huggingface_hub.InferenceClient.sentence_similarity"
        }
    )
    patchers.append(
        SymbolPatcher(
            lambda: importlib.import_module("huggingface_hub"),
            "InferenceClient.sentence_similarity",
            huggingface_wrapper_sync(sentence_similarity_settings),
        )
    )

    sentence_similarity_async_settings = base.model_copy(
        update={
            "name": base.name
            or "huggingface_hub.AsyncInferenceClient.sentence_similarity"
        }
    )
    patchers.append(
        SymbolPatcher(
            lambda: importlib.import_module("huggingface_hub"),
            "AsyncInferenceClient.sentence_similarity",
            huggingface_wrapper_sync(sentence_similarity_async_settings),
        )
    )

    summarization_settings = base.model_copy(
        update={"name": base.name or "huggingface_hub.InferenceClient.summarization"}
    )
    patchers.append(
        SymbolPatcher(
            lambda: importlib.import_module("huggingface_hub"),
            "InferenceClient.summarization",
            huggingface_wrapper_sync(summarization_settings),
        )
    )

    summarization_async_settings = base.model_copy(
        update={
            "name": base.name or "huggingface_hub.AsyncInferenceClient.summarization"
        }
    )
    patchers.append(
        SymbolPatcher(
            lambda: importlib.import_module("huggingface_hub"),
            "AsyncInferenceClient.summarization",
            huggingface_wrapper_sync(summarization_async_settings),
        )
    )

    table_question_answering_settings = base.model_copy(
        update={
            "name": base.name
            or "huggingface_hub.InferenceClient.table_question_answering"
        }
    )
    patchers.append(
        SymbolPatcher(
            lambda: importlib.import_module("huggingface_hub"),
            "InferenceClient.table_question_answering",
            huggingface_wrapper_sync(table_question_answering_settings),
        )
    )

    table_question_answering_async_settings = base.model_copy(
        update={
            "name": base.name
            or "huggingface_hub.AsyncInferenceClient.table_question_answering"
        }
    )
    patchers.append(
        SymbolPatcher(
            lambda: importlib.import_module("huggingface_hub"),
            "AsyncInferenceClient.table_question_answering",
            huggingface_wrapper_sync(table_question_answering_async_settings),
        )
    )

    text_classification_settings = base.model_copy(
        update={
            "name": base.name or "huggingface_hub.InferenceClient.text_classification"
        }
    )
    patchers.append(
        SymbolPatcher(
            lambda: importlib.import_module("huggingface_hub"),
            "InferenceClient.text_classification",
            huggingface_wrapper_sync(text_classification_settings),
        )
    )

    text_classification_async_settings = base.model_copy(
        update={
            "name": base.name
            or "huggingface_hub.AsyncInferenceClient.text_classification"
        }
    )
    patchers.append(
        SymbolPatcher(
            lambda: importlib.import_module("huggingface_hub"),
            "AsyncInferenceClient.text_classification",
            huggingface_wrapper_sync(text_classification_async_settings),
        )
    )

    token_classification_settings = base.model_copy(
        update={
            "name": base.name or "huggingface_hub.InferenceClient.token_classification"
        }
    )
    patchers.append(
        SymbolPatcher(
            lambda: importlib.import_module("huggingface_hub"),
            "InferenceClient.token_classification",
            huggingface_wrapper_sync(token_classification_settings),
        )
    )

    token_classification_async_settings = base.model_copy(
        update={
            "name": base.name
            or "huggingface_hub.AsyncInferenceClient.token_classification"
        }
    )
    patchers.append(
        SymbolPatcher(
            lambda: importlib.import_module("huggingface_hub"),
            "AsyncInferenceClient.token_classification",
            huggingface_wrapper_sync(token_classification_async_settings),
        )
    )

    translation_settings = base.model_copy(
        update={"name": base.name or "huggingface_hub.InferenceClient.translation"}
    )
    patchers.append(
        SymbolPatcher(
            lambda: importlib.import_module("huggingface_hub"),
            "InferenceClient.translation",
            huggingface_wrapper_sync(translation_settings),
        )
    )

    translation_async_settings = base.model_copy(
        update={"name": base.name or "huggingface_hub.AsyncInferenceClient.translation"}
    )
    patchers.append(
        SymbolPatcher(
            lambda: importlib.import_module("huggingface_hub"),
            "AsyncInferenceClient.translation",
            huggingface_wrapper_sync(translation_async_settings),
        )
    )

    zero_shot_classification_settings = base.model_copy(
        update={
            "name": base.name
            or "huggingface_hub.InferenceClient.zero_shot_classification"
        }
    )
    patchers.append(
        SymbolPatcher(
            lambda: importlib.import_module("huggingface_hub"),
            "InferenceClient.zero_shot_classification",
            huggingface_wrapper_sync(zero_shot_classification_settings),
        )
    )

    zero_shot_classification_async_settings = base.model_copy(
        update={
            "name": base.name
            or "huggingface_hub.AsyncInferenceClient.zero_shot_classification"
        }
    )
    patchers.append(
        SymbolPatcher(
            lambda: importlib.import_module("huggingface_hub"),
            "AsyncInferenceClient.zero_shot_classification",
            huggingface_wrapper_sync(zero_shot_classification_async_settings),
        )
    )

    text_to_image_settings = base.model_copy(
        update={"name": base.name or "huggingface_hub.InferenceClient.text_to_image"}
    )
    patchers.append(
        SymbolPatcher(
            lambda: importlib.import_module("huggingface_hub"),
            "InferenceClient.text_to_image",
            huggingface_wrapper_sync(text_to_image_settings),
        )
    )

    text_to_image_async_settings = base.model_copy(
        update={
            "name": base.name or "huggingface_hub.AsyncInferenceClient.text_to_image"
        }
    )
    patchers.append(
        SymbolPatcher(
            lambda: importlib.import_module("huggingface_hub"),
            "AsyncInferenceClient.text_to_image",
            huggingface_wrapper_sync(text_to_image_async_settings),
        )
    )

    image_to_image_settings = base.model_copy(
        update={"name": base.name or "huggingface_hub.InferenceClient.image_to_image"}
    )
    patchers.append(
        SymbolPatcher(
            lambda: importlib.import_module("huggingface_hub"),
            "InferenceClient.image_to_image",
            huggingface_wrapper_sync(image_to_image_settings),
        )
    )

    image_to_image_async_settings = base.model_copy(
        update={
            "name": base.name or "huggingface_hub.AsyncInferenceClient.image_to_image"
        }
    )
    patchers.append(
        SymbolPatcher(
            lambda: importlib.import_module("huggingface_hub"),
            "AsyncInferenceClient.image_to_image",
            huggingface_wrapper_sync(image_to_image_async_settings),
        )
    )

    _huggingface_patcher = MultiPatcher(patchers)
    return _huggingface_patcher
