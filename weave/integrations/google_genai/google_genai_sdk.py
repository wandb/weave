import importlib
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, Union

import weave
from weave.trace.autopatch import IntegrationSettings, OpSettings
from weave.trace.op_extensions.accumulator import add_accumulator
from weave.trace.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.serialize import dictify
from weave.trace.weave_client import Call

if TYPE_CHECKING:
    from google.genai.types import GenerateContentResponse


def google_genai_postprocess_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    model_name = inputs["self"]._model if hasattr(inputs["self"], "_model") else None
    if "self" in inputs:
        inputs["self"] = dictify(inputs["self"])
    if model_name is not None:
        inputs["model"] = model_name
    return inputs


def google_genai_on_finish(
    call: Call, output: Any, exception: Union[BaseException, None]
) -> None:
    model_name = None
    if "model" in call.inputs:
        model_name = call.inputs["model"]
    else:
        raise ValueError("Unknown model type")
    usage = {model_name: {"requests": 1}}
    summary_update = {"usage": usage}
    if output:
        call.output = dictify(output)
        usage[model_name].update(
            {
                "cached_content_token_count": output.usage_metadata.cached_content_token_count,
                "prompt_token_count": output.usage_metadata.prompt_token_count,
                "candidates_token_count": output.usage_metadata.candidates_token_count,
                "total_token_count": output.usage_metadata.total_token_count,
            }
        )
    if call.summary is not None:
        call.summary.update(summary_update)


def google_genai_accumulator(
    acc: Union["GenerateContentResponse", None], value: "GenerateContentResponse"
) -> "GenerateContentResponse":
    if acc is None:
        return value

    for i, value_candidate in enumerate(value.candidates):
        for j, value_part in enumerate(value_candidate.content.parts):
            if value_part.text is not None:
                acc.candidates[i].content.parts[j].text += value_part.text

    if acc.usage_metadata.prompt_token_count is None:
        acc.usage_metadata.prompt_token_count = 0
    elif value.usage_metadata.prompt_token_count is not None:
        acc.usage_metadata.prompt_token_count += value.usage_metadata.prompt_token_count

    if acc.usage_metadata.candidates_token_count is None:
        acc.usage_metadata.candidates_token_count = 0
    elif value.usage_metadata.candidates_token_count is not None:
        acc.usage_metadata.candidates_token_count += (
            value.usage_metadata.candidates_token_count
        )

    if acc.usage_metadata.total_token_count is None:
        acc.usage_metadata.total_token_count = 0
    elif value.usage_metadata.total_token_count is not None:
        acc.usage_metadata.total_token_count += value.usage_metadata.total_token_count

    if acc.usage_metadata.cached_content_token_count is None:
        acc.usage_metadata.cached_content_token_count = 0
    elif value.usage_metadata.cached_content_token_count is not None:
        acc.usage_metadata.cached_content_token_count += (
            value.usage_metadata.cached_content_token_count
        )

    return acc


def google_genai_wrapper_sync(settings: OpSettings) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        if not op_kwargs.get("postprocess_inputs"):
            op_kwargs["postprocess_inputs"] = google_genai_postprocess_inputs

        op = weave.op(fn, **op_kwargs)
        if not op.name.endswith("count_tokens"):
            op._set_on_finish_handler(google_genai_on_finish)
        return add_accumulator(
            op,
            make_accumulator=lambda inputs: google_genai_accumulator,
            should_accumulate=lambda inputs: op.name.endswith("stream"),
        )

    return wrapper


def google_genai_wrapper_async(
    settings: OpSettings,
) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        def _fn_wrapper(fn: Callable) -> Callable:
            @wraps(fn)
            async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await fn(*args, **kwargs)

            return _async_wrapper

        op_kwargs = settings.model_dump()
        if not op_kwargs.get("postprocess_inputs"):
            op_kwargs["postprocess_inputs"] = google_genai_postprocess_inputs

        op = weave.op(_fn_wrapper(fn), **op_kwargs)
        if not op.name.endswith("count_tokens"):
            op._set_on_finish_handler(google_genai_on_finish)
        return add_accumulator(
            op,
            make_accumulator=lambda inputs: google_genai_accumulator,
            should_accumulate=lambda inputs: op.name.endswith("stream"),
        )

    return wrapper


def get_google_genai_patcher(
    settings: Union[IntegrationSettings, None] = None,
) -> Union[MultiPatcher, NoOpPatcher]:
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    base = settings.op_settings

    generate_content_settings = base.model_copy(
        update={"name": base.name or "google.genai.models.Models.generate_content"}
    )
    count_tokens_settings = base.model_copy(
        update={"name": base.name or "google.genai.models.Models.count_tokens"}
    )
    generate_content_async_settings = base.model_copy(
        update={"name": base.name or "google.genai.models.AsyncModels.generate_content"}
    )
    count_tokens_async_settings = base.model_copy(
        update={"name": base.name or "google.genai.models.AsyncModels.count_tokens"}
    )
    chat_settings = base.model_copy(
        update={"name": base.name or "google.genai.chats.Chat.send_message"}
    )
    chat_async_settings = base.model_copy(
        update={"name": base.name or "google.genai.chats.AsyncChat.send_message"}
    )
    generate_content_stream_settings = base.model_copy(
        update={
            "name": base.name or "google.genai.models.Models.generate_content_stream"
        }
    )
    generate_content_stream_async_settings = base.model_copy(
        update={
            "name": base.name
            or "google.genai.models.AsyncModels.generate_content_stream"
        }
    )
    chat_stream_settings = base.model_copy(
        update={"name": base.name or "google.genai.chats.Chat.send_message_stream"}
    )
    chat_stream_async_settings = base.model_copy(
        update={"name": base.name or "google.genai.chats.AsyncChat.send_message_stream"}
    )

    _google_genai_patcher = MultiPatcher(
        [
            SymbolPatcher(
                lambda: importlib.import_module("google.genai.models"),
                "Models.generate_content",
                google_genai_wrapper_sync(generate_content_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("google.genai.models"),
                "AsyncModels.generate_content",
                google_genai_wrapper_async(generate_content_async_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("google.genai.models"),
                "Models.count_tokens",
                google_genai_wrapper_sync(count_tokens_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("google.genai.models"),
                "AsyncModels.count_tokens",
                google_genai_wrapper_async(count_tokens_async_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("google.genai.chats"),
                "Chat.send_message",
                google_genai_wrapper_sync(chat_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("google.genai.chats"),
                "AsyncChat.send_message",
                google_genai_wrapper_async(chat_async_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("google.genai.models"),
                "Models.generate_content_stream",
                google_genai_wrapper_sync(generate_content_stream_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("google.genai.models"),
                "AsyncModels.generate_content_stream",
                google_genai_wrapper_async(generate_content_stream_async_settings),
            ),
        ]
    )

    return _google_genai_patcher
