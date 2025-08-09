from __future__ import annotations

import importlib
import logging
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable
from urllib.parse import urlparse

import weave
from weave.integrations.openai.gpt_image_utils import (
    openai_image_edit_wrapper_async,
    openai_image_edit_wrapper_sync,
    openai_image_variation_wrapper_async,
    openai_image_variation_wrapper_sync,
    openai_image_wrapper_async,
    openai_image_wrapper_sync,
)
from weave.integrations.openai.openai_utils import (
    openai_accumulator,
    openai_on_finish_post_processor,
    openai_on_input_handler,
    should_use_accumulator,
)
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings, OpSettings
from weave.trace.op import (
    Op,
    ProcessedInputs,
    _add_accumulator,
    _default_on_input_handler,
)

if TYPE_CHECKING:
    from openai.types.responses import Response, ResponseStreamEvent

_openai_patcher: MultiPatcher | None = None

logger = logging.getLogger(__name__)


def maybe_unwrap_api_response(value: Any) -> Any:
    """If the caller requests a raw response, we unwrap the APIResponse object.
    We take a very conservative approach to only unwrap the types we know about.
    """
    maybe_value: Any = None
    try:
        from openai._legacy_response import LegacyAPIResponse

        if isinstance(value, LegacyAPIResponse):
            maybe_value = value.parse()
    except:
        pass

    try:
        from openai._response import APIResponse

        if isinstance(value, APIResponse):
            maybe_value = value.parse()
    except:
        pass

    try:
        from openai.types.chat import ChatCompletion, ChatCompletionChunk

        if isinstance(maybe_value, (ChatCompletion, ChatCompletionChunk)):
            return maybe_value
    except:
        pass

    return value

def convert_completion_to_dict(obj: Any) -> dict:
    return {
        "client": {
            "base_url": str(obj._client._base_url),
            "version": obj._client._version,
        },
    }


def completion_instance_check(obj: Any) -> bool:
    return (
        hasattr(obj, "messages")
        and hasattr(obj, "_client")
        and hasattr(obj._client, "_base_url")
        and hasattr(obj._client, "_version")
    )


def openai_on_input_handler_extended(
    func: Op, args: tuple, kwargs: dict
) -> ProcessedInputs | None:
    original_args = args
    original_kwargs = kwargs

    processed_inputs = _default_on_input_handler(func, tuple(args), kwargs)
    inputs = processed_inputs.inputs

    args = list(args)  # type: ignore[assignment]
    if len(args) > 0 and completion_instance_check(args[0]):
        # This will be the `self` argument to the function, convert it to a dict
        args[0] = convert_completion_to_dict(args[0])  # type: ignore[index]
        inputs.update({"self": args[0]})

    # Check for EasyPrompt usage
    result = openai_on_input_handler(func, tuple(args), kwargs)
    if result is not None:
        result.inputs.update(inputs)
        processed_inputs.args = result.args
        processed_inputs.kwargs = result.kwargs
        processed_inputs.inputs = result.inputs
        return processed_inputs

    return ProcessedInputs(
        original_args=original_args,
        original_kwargs=original_kwargs,
        args=tuple(args),
        kwargs=kwargs,
        inputs=inputs,
    )


def create_wrapper_sync(settings: OpSettings) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        "We need to do this so we can check if `stream` is used"

        def _add_stream_options(fn: Callable) -> Callable:
            @wraps(fn)
            def _wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
                if kwargs.get("stream") and kwargs.get("stream_options") is None:
                    completion = self
                    base_url = str(completion._client._base_url)
                    # Only set stream_options if it targets the OpenAI endpoints
                    if urlparse(base_url).hostname == "api.openai.com":
                        kwargs["stream_options"] = {"include_usage": True}
                return fn(self, *args, **kwargs)

            return _wrapper

        def _openai_stream_options_is_set(inputs: dict) -> bool:
            if inputs.get("stream_options") is not None:
                return True
            return False

        op_kwargs = settings.model_dump()
        op = weave.op(_add_stream_options(fn), **op_kwargs)

        op._set_on_input_handler(openai_on_input_handler_extended)
        return _add_accumulator(
            op,  # type: ignore
            make_accumulator=lambda inputs: lambda acc, value: openai_accumulator(
                acc, value, skip_last=not _openai_stream_options_is_set(inputs)
            ),
            should_accumulate=should_use_accumulator,
            on_finish_post_processor=openai_on_finish_post_processor,
        )

    return wrapper


# Surprisingly, the async `client.chat.completions.create` does not pass
# `inspect.iscoroutinefunction`, so we can't dispatch on it and must write
# it manually here...
def create_wrapper_async(settings: OpSettings) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        "We need to do this so we can check if `stream` is used"

        def _add_stream_options(fn: Callable) -> Callable:
            @wraps(fn)
            async def _wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
                if kwargs.get("stream") and kwargs.get("stream_options") is None:
                    completion = self
                    base_url = str(completion._client._base_url)
                    # Only set stream_options if it targets the OpenAI endpoints
                    if urlparse(base_url).hostname == "api.openai.com":
                        kwargs["stream_options"] = {"include_usage": True}
                return await fn(self, *args, **kwargs)

            return _wrapper

        def _openai_stream_options_is_set(inputs: dict) -> bool:
            if inputs.get("stream_options") is not None:
                return True
            return False

        op_kwargs = settings.model_dump()
        op = weave.op(_add_stream_options(fn), **op_kwargs)
        op._set_on_input_handler(openai_on_input_handler_extended)
        return _add_accumulator(
            op,  # type: ignore
            make_accumulator=lambda inputs: lambda acc, value: openai_accumulator(
                acc, value, skip_last=not _openai_stream_options_is_set(inputs)
            ),
            should_accumulate=should_use_accumulator,
            on_finish_post_processor=openai_on_finish_post_processor,
        )

    return wrapper


def _pad_output(acc: Response, value: ResponseStreamEvent) -> Response:
    if len(acc.output) <= value.output_index:
        missing_len = value.output_index - len(acc.output) + 1
        acc.output.extend([""] * missing_len)
    return acc


### Responses API
def responses_accumulator(acc: Response | None, value: ResponseStreamEvent) -> Response:
    from openai.types.responses import (
        Response,
        ResponseAudioDeltaEvent,
        ResponseAudioDoneEvent,
        ResponseAudioTranscriptDeltaEvent,
        ResponseAudioTranscriptDoneEvent,
        ResponseCodeInterpreterCallCodeDeltaEvent,
        ResponseCodeInterpreterCallCodeDoneEvent,
        ResponseCodeInterpreterCallCompletedEvent,
        ResponseCodeInterpreterCallInProgressEvent,
        ResponseCodeInterpreterCallInterpretingEvent,
        ResponseCompletedEvent,
        ResponseContentPartAddedEvent,
        ResponseContentPartDoneEvent,
        ResponseCreatedEvent,
        ResponseErrorEvent,
        ResponseFailedEvent,
        ResponseFileSearchCallCompletedEvent,
        ResponseFileSearchCallInProgressEvent,
        ResponseFileSearchCallSearchingEvent,
        ResponseFunctionCallArgumentsDeltaEvent,
        ResponseFunctionCallArgumentsDoneEvent,
        ResponseIncompleteEvent,
        ResponseInProgressEvent,
        ResponseOutputItemAddedEvent,
        ResponseOutputItemDoneEvent,
        ResponseRefusalDeltaEvent,
        ResponseRefusalDoneEvent,
        ResponseTextDeltaEvent,
        ResponseTextDoneEvent,
        ResponseWebSearchCallCompletedEvent,
        ResponseWebSearchCallInProgressEvent,
        ResponseWebSearchCallSearchingEvent,
    )

    # ResponseOutputTextAnnotationAddedEvent was introduced in openai 1.80.0
    is_new_sdk = False
    try:
        from openai.types.responses import ResponseOutputTextAnnotationAddedEvent

        is_new_sdk = True
    except ImportError:
        pass

    if acc is None:
        acc = Response(
            id="",
            created_at=0,
            model="",
            object="response",
            output=[],
            parallel_tool_calls=False,
            tool_choice="auto",
            tools=[],
        )

    # 1. "Response" object events, either at the start or end of a slice of the stream
    if isinstance(
        value,
        (
            ResponseCreatedEvent,
            ResponseInProgressEvent,
            ResponseIncompleteEvent,
            ResponseCompletedEvent,
            ResponseFailedEvent,
        ),
    ):
        # In the happy path, the final event is ResponseCompletedEvent with a fully
        # populated response object.  This is the most faithful representation, so
        # just use this if available.

        # As an MVP this alone is probably sufficient for the streaming case (assuming
        # the user does not close the stream mid-response).
        acc = value.response

    # 2. "Delta" events, which are streamed parts appended to an InProgressEvent
    # 2a. Events with an output_index
    elif isinstance(
        value,
        (
            ResponseCodeInterpreterCallCodeDeltaEvent,
            ResponseFunctionCallArgumentsDeltaEvent,
            ResponseRefusalDeltaEvent,
            ResponseTextDeltaEvent,
        ),
    ):
        acc = _pad_output(acc, value)

        acc.output[value.output_index] += value.delta

    # 2b. Events without an output_index
    elif isinstance(
        value,
        (
            ResponseAudioDeltaEvent,
            ResponseAudioTranscriptDeltaEvent,
        ),
    ):
        # Not obvious how to handle these since there is no output_index
        if not acc.output:
            acc.output = [""]

        if value.delta is None:
            # This is likely the case where not all event types are available in the SDK (ResponseOutputTextAnnotationAddedEvent)
            logger.warning(
                "Some responses could not be processed with your current version of the OpenAI SDK. Please upgrade to the latest version."
            )
        else:
            acc.output[0] += value.delta

    elif is_new_sdk:
        if isinstance(value, ResponseOutputTextAnnotationAddedEvent):
            # Not obvious how to handle this since there is no delta
            ...

    # Everything else
    elif isinstance(
        value,
        (
            ResponseContentPartAddedEvent,
            ResponseErrorEvent,
            ResponseOutputItemAddedEvent,
        ),
    ):
        ...

    # 3. No-op events: these are not needed for the accumulator
    # 3a. "Done" events
    elif isinstance(
        value,
        (
            ResponseAudioDoneEvent,
            ResponseAudioTranscriptDoneEvent,
            ResponseCodeInterpreterCallCodeDoneEvent,
            ResponseContentPartDoneEvent,
            ResponseFunctionCallArgumentsDoneEvent,
            ResponseOutputItemDoneEvent,
            ResponseRefusalDoneEvent,
            ResponseTextDoneEvent,
        ),
    ):
        pass  # Nothing to do here

    # 3b. "Tool Completed" events
    elif isinstance(
        value,
        (
            ResponseCodeInterpreterCallCompletedEvent,
            ResponseFileSearchCallCompletedEvent,
            ResponseWebSearchCallCompletedEvent,
        ),
    ):
        pass  # Nothing to do here

    # 3c. "Tool In Progress" events
    elif isinstance(
        value,
        (
            ResponseCodeInterpreterCallInProgressEvent,
            ResponseFileSearchCallInProgressEvent,
            ResponseWebSearchCallInProgressEvent,
        ),
    ):
        pass  # Nothing to do here

    # 3d. "Tool Action" events
    elif isinstance(
        value,
        (
            ResponseCodeInterpreterCallInterpretingEvent,
            ResponseFileSearchCallSearchingEvent,
            ResponseWebSearchCallSearchingEvent,
        ),
    ):
        pass  # Nothing to do here

    return acc


def should_use_responses_accumulator(inputs: dict) -> bool:
    return isinstance(inputs, dict) and inputs.get("stream") is True


def create_wrapper_responses_sync(
    settings: OpSettings,
) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()

        @wraps(fn)
        def _inner(*args: Any, **kwargs: Any) -> Any:
            return fn(*args, **kwargs)

        op = weave.op(_inner, **op_kwargs)
        op._set_on_input_handler(openai_on_input_handler)
        return _add_accumulator(
            op,  # type: ignore
            make_accumulator=lambda inputs: lambda acc, value: responses_accumulator(
                acc, value
            ),
            should_accumulate=should_use_responses_accumulator,
            on_finish_post_processor=lambda value: value,
        )

    return wrapper


def create_wrapper_responses_async(
    settings: OpSettings,
) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()

        @wraps(fn)
        async def _inner(*args: Any, **kwargs: Any) -> Any:
            return await fn(*args, **kwargs)

        op = weave.op(_inner, **op_kwargs)
        op._set_on_input_handler(openai_on_input_handler)
        return _add_accumulator(
            op,  # type: ignore
            make_accumulator=lambda inputs: lambda acc, value: responses_accumulator(
                acc, value
            ),
            should_accumulate=should_use_responses_accumulator,
            on_finish_post_processor=lambda value: value,
        )

    return wrapper


def get_openai_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _openai_patcher
    if _openai_patcher is not None:
        return _openai_patcher

    base = settings.op_settings

    completions_create_settings = base.model_copy(
        update={"name": base.name or "openai.chat.completions.create"}
    )
    async_completions_create_settings = base.model_copy(
        update={"name": base.name or "openai.chat.completions.create"}
    )
    completions_parse_settings = base.model_copy(
        update={"name": base.name or "openai.beta.chat.completions.parse"}
    )
    async_completions_parse_settings = base.model_copy(
        update={"name": base.name or "openai.beta.chat.completions.parse"}
    )
    moderation_create_settings = base.model_copy(
        update={"name": base.name or "openai.moderations.create"}
    )
    async_moderation_create_settings = base.model_copy(
        update={"name": base.name or "openai.moderations.create"}
    )
    embeddings_create_settings = base.model_copy(
        update={"name": base.name or "openai.embeddings.create"}
    )
    async_embeddings_create_settings = base.model_copy(
        update={"name": base.name or "openai.embeddings.create"}
    )
    responses_create_settings = base.model_copy(
        update={"name": base.name or "openai.responses.create"}
    )
    async_responses_create_settings = base.model_copy(
        update={"name": base.name or "openai.responses.create"}
    )
    responses_parse_settings = base.model_copy(
        update={"name": base.name or "openai.responses.parse"}
    )
    async_responses_parse_settings = base.model_copy(
        update={"name": base.name or "openai.responses.parse"}
    )
    images_generate_settings = base.model_copy(
        update={"name": base.name or "openai.images.generate"}
    )
    async_images_generate_settings = base.model_copy(
        update={"name": base.name or "openai.images.generate"}
    )
    images_edit_settings = base.model_copy(
        update={"name": base.name or "openai.images.edit"}
    )
    async_images_edit_settings = base.model_copy(
        update={"name": base.name or "openai.images.edit"}
    )
    images_create_variation_settings = base.model_copy(
        update={"name": base.name or "openai.images.create_variation"}
    )
    async_images_create_variation_settings = base.model_copy(
        update={"name": base.name or "openai.images.create_variation"}
    )

    _openai_patcher = MultiPatcher(
        [
            SymbolPatcher(
                lambda: importlib.import_module("openai.resources.chat.completions"),
                "Completions.create",
                create_wrapper_sync(settings=completions_create_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("openai.resources.chat.completions"),
                "AsyncCompletions.create",
                create_wrapper_async(settings=async_completions_create_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module(
                    "openai.resources.beta.chat.completions"
                ),
                "Completions.parse",
                create_wrapper_sync(settings=completions_parse_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module(
                    "openai.resources.beta.chat.completions"
                ),
                "AsyncCompletions.parse",
                create_wrapper_async(settings=async_completions_parse_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("openai.resources.moderations"),
                "Moderations.create",
                create_wrapper_sync(settings=moderation_create_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("openai.resources.moderations"),
                "AsyncModerations.create",
                create_wrapper_async(settings=async_moderation_create_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("openai.resources.embeddings"),
                "Embeddings.create",
                create_wrapper_sync(settings=embeddings_create_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("openai.resources.embeddings"),
                "AsyncEmbeddings.create",
                create_wrapper_async(settings=async_embeddings_create_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("openai.resources.responses"),
                "Responses.create",
                create_wrapper_responses_sync(settings=responses_create_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("openai.resources.responses"),
                "AsyncResponses.create",
                create_wrapper_responses_async(
                    settings=async_responses_create_settings
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("openai.resources.responses"),
                "Responses.parse",
                create_wrapper_responses_sync(settings=responses_parse_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("openai.resources.responses"),
                "AsyncResponses.parse",
                create_wrapper_responses_async(settings=async_responses_parse_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("openai.resources.images"),
                "Images.generate",
                openai_image_wrapper_sync(settings=images_generate_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("openai.resources.images"),
                "AsyncImages.generate",
                openai_image_wrapper_async(settings=async_images_generate_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("openai.resources.images"),
                "Images.edit",
                openai_image_edit_wrapper_sync(settings=images_edit_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("openai.resources.images"),
                "AsyncImages.edit",
                openai_image_edit_wrapper_async(settings=async_images_edit_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("openai.resources.images"),
                "Images.create_variation",
                openai_image_variation_wrapper_sync(
                    settings=images_create_variation_settings
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("openai.resources.images"),
                "AsyncImages.create_variation",
                openai_image_variation_wrapper_async(
                    settings=async_images_create_variation_settings
                ),
            ),
        ]
    )

    return _openai_patcher
