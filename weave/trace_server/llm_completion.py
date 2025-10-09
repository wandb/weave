from __future__ import annotations

import dataclasses
import datetime
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, Callable

from pydantic import BaseModel

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import (
    InvalidRequest,
    MissingLLMApiKeyError,
)
from weave.trace_server.interface.builtin_object_classes.provider import (
    Provider,
    ProviderModel,
)
from weave.trace_server.secret_fetcher_context import _secret_fetcher_context

# Import types only for type checking to avoid circular imports
if TYPE_CHECKING:
    from weave.trace_server.clickhouse_schema import (
        CallEndCHInsertable,
        CallStartCHInsertable,
    )

NOVA_MODELS = ("nova-pro-v1", "nova-lite-v1", "nova-micro-v1")

# Import helper functions needed by the stream wrapper
# These create a circular import, so we'll import them locally in the functions that need them


def lite_llm_completion(
    api_key: str | None,
    inputs: tsi.CompletionsCreateRequestInputs,
    provider: str | None = None,
    base_url: str | None = None,
    extra_headers: dict[str, str] | None = None,
    return_type: str | None = None,
) -> tsi.CompletionsCreateRes:
    # Setup provider-specific credentials and model modifications
    (
        aws_access_key_id,
        aws_secret_access_key,
        aws_region_name,
        azure_api_base,
        azure_api_version,
    ) = _setup_provider_credentials_and_model(inputs, provider)

    import litellm

    # This allows us to drop params that are not supported by the LLM provider
    litellm.drop_params = True

    # Handle custom provider
    if provider == "custom" and base_url:
        try:
            # Prepare headers
            headers = extra_headers or {}

            # Make the API call using litellm
            res = litellm.completion(
                **inputs.model_dump(exclude_none=True),
                api_key=api_key,
                api_base=base_url,
                extra_headers=headers,
            )

            # Convert the response based on return_type if needed
            if return_type and return_type != "openai":
                # Handle different return types if needed in the future
                pass

            return tsi.CompletionsCreateRes(response=res.model_dump())
        except Exception as e:
            error_message = str(e)
            error_message = error_message.replace("litellm.", "")
            return tsi.CompletionsCreateRes(response={"error": error_message})
    elif provider == "custom" and not base_url:
        raise InvalidRequest(
            "Invalid provider configuration: must provide base_url if provider is 'custom'"
        )
    elif base_url and provider != "custom":
        raise InvalidRequest(
            f"Invalid provider configuration: provider '{provider}' must be 'custom' if base_url is provided"
        )

    try:
        res = litellm.completion(
            **inputs.model_dump(exclude_none=True),
            api_key=api_key,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_region_name=aws_region_name,
            api_base=azure_api_base,
            api_version=azure_api_version,
        )
        return tsi.CompletionsCreateRes(response=res.model_dump())
    except Exception as e:
        error_message = str(e)
        error_message = error_message.replace("litellm.", "")
        return tsi.CompletionsCreateRes(response={"error": error_message})


def get_bedrock_credentials(
    model_name: str,
) -> tuple[str, str, str]:
    secret_fetcher = _secret_fetcher_context.get()
    if not secret_fetcher:
        raise InvalidRequest(
            f"No secret fetcher found, cannot fetch API key for model {model_name}"
        )

    aws_access_key_id = (
        secret_fetcher.fetch("AWS_ACCESS_KEY_ID")
        .get("secrets", {})
        .get("AWS_ACCESS_KEY_ID")
    )
    aws_secret_access_key = (
        secret_fetcher.fetch("AWS_SECRET_ACCESS_KEY")
        .get("secrets", {})
        .get("AWS_SECRET_ACCESS_KEY")
    )
    aws_region_name = (
        secret_fetcher.fetch("AWS_REGION_NAME")
        .get("secrets", {})
        .get("AWS_REGION_NAME")
    )
    if not aws_region_name:
        raise MissingLLMApiKeyError(
            f"No AWS region name found for model {model_name}",
            api_key_name="AWS_REGION_NAME",
        )
    elif not aws_access_key_id:
        raise MissingLLMApiKeyError(
            f"No AWS access key ID found for model {model_name}",
            api_key_name="AWS_ACCESS_KEY_ID",
        )
    elif not aws_secret_access_key:
        raise MissingLLMApiKeyError(
            f"No AWS secret access key found for model {model_name}",
            api_key_name="AWS_SECRET_ACCESS_KEY",
        )

    return aws_access_key_id, aws_secret_access_key, aws_region_name


def get_azure_credentials(model_name: str) -> tuple[str, str]:
    secret_fetcher = _secret_fetcher_context.get()
    if not secret_fetcher:
        raise InvalidRequest(
            f"No secret fetcher found, cannot fetch API key for model {model_name}"
        )

    azure_api_base = (
        secret_fetcher.fetch("AZURE_API_BASE").get("secrets", {}).get("AZURE_API_BASE")
    )
    if not azure_api_base:
        raise MissingLLMApiKeyError(
            f"No Azure API base found for model {model_name}",
            api_key_name="AZURE_API_BASE",
        )

    azure_api_version = (
        secret_fetcher.fetch("AZURE_API_VERSION")
        .get("secrets", {})
        .get("AZURE_API_VERSION")
    )
    if not azure_api_version:
        raise MissingLLMApiKeyError(
            f"No Azure API version found for model {model_name}",
            api_key_name="AZURE_API_VERSION",
        )

    return azure_api_base, azure_api_version


def _setup_provider_credentials_and_model(
    inputs: tsi.CompletionsCreateRequestInputs,
    provider: str | None = None,
) -> tuple[str | None, str | None, str | None, str | None, str | None]:
    """Setup provider-specific credentials and model modifications.

    Returns: (aws_access_key_id, aws_secret_access_key, aws_region_name, azure_api_base, azure_api_version)
    """
    aws_access_key_id, aws_secret_access_key, aws_region_name = None, None, None
    azure_api_base, azure_api_version = None, None

    if provider == "bedrock" or provider == "bedrock_converse":
        aws_access_key_id, aws_secret_access_key, aws_region_name = (
            get_bedrock_credentials(inputs.model)
        )
        # Nova models need the region in the model name
        if any(x in inputs.model for x in NOVA_MODELS) and aws_region_name:
            aws_inference_region = aws_region_name.split("-")[0]
            inputs.model = "bedrock/" + aws_inference_region + "." + inputs.model
    # XAI models don't support response_format
    elif provider == "xai":
        inputs.response_format = None
        if "grok-3-mini" in inputs.model:
            inputs.presence_penalty = None
            inputs.frequency_penalty = None
    elif provider == "azure" or provider == "azure_ai":
        azure_api_base, azure_api_version = get_azure_credentials(inputs.model)

    return (
        aws_access_key_id,
        aws_secret_access_key,
        aws_region_name,
        azure_api_base,
        azure_api_version,
    )


class CustomProviderInfo(BaseModel):
    base_url: str
    api_key: str
    extra_headers: dict[str, str]
    return_type: str
    actual_model_name: str


def get_custom_provider_info(
    project_id: str,
    provider_name: str,
    model_name: str,
    obj_read_func: Callable,
) -> CustomProviderInfo:
    """Extract provider information from a custom provider model.

    Args:
        project_id: The project ID
        provider_name: The provider name (e.g., "ollama", "openrouter_xai")
        model_name: The object_id for ProviderModel lookup (e.g., "ollama-gemma2_2b")
        obj_read_func: Function to read objects from the database
    Returns:
        CustomProviderInfo containing:
        - base_url: The base URL for the provider
        - api_key: The API key for the provider
        - extra_headers: Extra headers to send with the request
        - return_type: The return type for the provider
        - actual_model_name: The actual model name to use for the API call
    """
    secret_fetcher = _secret_fetcher_context.get()
    if not secret_fetcher:
        raise InvalidRequest(
            f"No secret fetcher found, cannot fetch API key for model {model_name}"
        )

    # Fetch the ProviderModel object
    try:
        provider_model_obj_req = tsi.ObjReadReq(
            project_id=project_id,
            object_id=model_name,
            digest="latest",  # Use latest version
            metadata_only=False,
        )
        provider_model_obj_res = obj_read_func(provider_model_obj_req)

        if (
            provider_model_obj_res.obj is None
            or provider_model_obj_res.obj.base_object_class != "ProviderModel"
        ):
            raise InvalidRequest(
                f"Could not find ProviderModel with object_id {model_name}"
            )

        provider_model_obj = ProviderModel.model_validate(
            provider_model_obj_res.obj.val
        )
        actual_model_name = provider_model_obj.name

        provider_obj_req = tsi.ObjReadReq(
            project_id=project_id,
            object_id=provider_name,  # Empty for digest lookup
            digest=provider_model_obj.provider,
            metadata_only=False,
        )
        provider_obj_res = obj_read_func(provider_obj_req)

        if (
            provider_obj_res.obj is None
            or provider_obj_res.obj.base_object_class != "Provider"
        ):
            raise InvalidRequest(
                f"Could not find Provider for model object_id {provider_name}"
            )

        provider_obj = Provider.model_validate(provider_obj_res.obj.val)

    except Exception as e:
        raise InvalidRequest(
            f"Failed to fetch provider model information: {e!s}"
        ) from e

    secret_name = provider_obj.api_key_name

    # Get the API key
    if not secret_name:
        raise InvalidRequest(f"No secret name found for provider {provider_name}")

    api_key = secret_fetcher.fetch(secret_name).get("secrets", {}).get(secret_name)

    if not api_key:
        raise MissingLLMApiKeyError(
            f"No API key {secret_name} found for provider {provider_name}",
            api_key_name=secret_name,
        )

    return CustomProviderInfo(
        base_url=provider_obj.base_url,
        api_key=api_key,
        extra_headers=provider_obj.extra_headers,
        return_type=provider_obj.return_type,
        actual_model_name=actual_model_name,
    )


# ---------------------------------------------------------------------------
# Streaming variant
# ---------------------------------------------------------------------------


def lite_llm_completion_stream(
    api_key: str | None,
    inputs: tsi.CompletionsCreateRequestInputs,
    provider: str | None = None,
    base_url: str | None = None,
    extra_headers: dict[str, str] | None = None,
    return_type: str | None = None,
) -> Iterator[dict[str, Any]]:
    """Stream completion chunks from the underlying LLM provider using litellm.

    This mirrors :pyfunc:`lite_llm_completion` but sets ``stream=True`` and yields
    dictionary chunks that can be serialized with ``json.dumps``.  Error handling
    follows the non-streaming version: any exception is surfaced to the caller
    as a single error chunk and the iterator terminates.
    """
    # Setup provider-specific credentials and model modifications
    (
        aws_access_key_id,
        aws_secret_access_key,
        aws_region_name,
        azure_api_base,
        azure_api_version,
    ) = _setup_provider_credentials_and_model(inputs, provider)

    import litellm

    litellm.drop_params = True

    # Helper to produce a generator of dicts from litellm chunks
    def _generate_chunks() -> Iterator[dict[str, Any]]:
        try:
            if provider == "custom" and base_url:
                headers = extra_headers or {}

                model_dict = inputs.model_dump(
                    exclude=[
                        "extra_headers",
                        "stream",
                        "stream_options",
                    ]
                )

                stream = litellm.completion(
                    **model_dict,
                    api_key=api_key,
                    api_base=base_url,
                    extra_headers=headers,
                    stream=True,
                    stream_options={"include_usage": True},
                )
            else:
                stream = litellm.completion(
                    **inputs.model_dump(exclude_none=True),
                    api_key=api_key,
                    aws_access_key_id=aws_access_key_id,
                    aws_secret_access_key=aws_secret_access_key,
                    aws_region_name=aws_region_name,
                    api_base=azure_api_base,
                    api_version=azure_api_version,
                    stream=True,
                    stream_options={"include_usage": True},
                )

            for chunk in stream:
                # ``chunk`` is a BaseModel (ChatCompletionChunk). Convert to dict.
                if hasattr(chunk, "model_dump"):
                    yield chunk.model_dump()
                else:
                    yield chunk  # type: ignore[return-value]
        except Exception as e:
            error_message = str(e).replace("litellm.", "")
            yield {"error": error_message}

    # If the caller wants a custom return type transformation (currently unused)
    # they can wrap the generator themselves. We just return the raw iterator.
    return _generate_chunks()


@dataclasses.dataclass
class ChoiceMessage:
    """Typed representation of a choice message."""

    content: str | None
    role: str
    tool_calls: list[dict[str, Any]] | None
    function_call: dict[str, Any] | None
    reasoning_content: str | None


@dataclasses.dataclass
class CompletionChoice:
    """Typed representation of a completion choice."""

    finish_reason: str | None
    index: int
    message: ChoiceMessage


@dataclasses.dataclass
class CompletionResponse:
    """Typed representation of a completion response."""

    id: str
    created: int
    model: str
    object: str
    system_fingerprint: str
    choices: list[dict[str, Any]]
    usage: dict[str, Any]
    service_tier: str


def _build_choice_content(content_parts: list[str]) -> str | None:
    """Build content string from accumulated parts."""
    if not content_parts:
        return None
    return "".join(content_parts)


def _build_choice_reasoning(reasoning_parts: list[str]) -> str | None:
    """Build reasoning content string from accumulated parts."""
    if not reasoning_parts:
        return None
    return "".join(reasoning_parts)


def _create_completion_choice(
    choice_index: int,
    content_parts: list[str],
    tool_calls: list[dict[str, Any]],
    reasoning_parts: list[str],
    finish_reason: str | None,
) -> CompletionChoice:
    """Create a properly structured completion choice."""
    cleaned_tool_calls = _clean_tool_calls(tool_calls)
    content = _build_choice_content(content_parts)

    # If no content but we have tool calls, set content to None explicitly
    if not content and cleaned_tool_calls:
        content = None
    elif not content:
        content = ""

    message = ChoiceMessage(
        content=content,
        role="assistant",
        tool_calls=cleaned_tool_calls if cleaned_tool_calls else None,
        function_call=None,
        reasoning_content=_build_choice_reasoning(reasoning_parts),
    )

    return CompletionChoice(
        finish_reason=finish_reason,
        index=choice_index,
        message=message,
    )


def _build_choices_array(
    choice_contents: dict[int, list[str]],
    choice_tool_calls: dict[int, list[dict[str, Any]]],
    choice_reasoning_content: dict[int, list[str]],
    choice_finish_reasons: dict[int, str | None],
) -> list[dict[str, Any]]:
    """Build the choices array from accumulated choice data."""
    # Get all choice indexes that have any data
    all_choice_indexes = (
        set(choice_contents.keys())
        | set(choice_tool_calls.keys())
        | set(choice_reasoning_content.keys())
    )

    choices = []
    for choice_index in sorted(all_choice_indexes):
        choice = _create_completion_choice(
            choice_index=choice_index,
            content_parts=choice_contents.get(choice_index, []),
            tool_calls=choice_tool_calls.get(choice_index, []),
            reasoning_parts=choice_reasoning_content.get(choice_index, []),
            finish_reason=choice_finish_reasons.get(choice_index),
        )
        choices.append(dataclasses.asdict(choice))

    return choices


def _build_completion_response(
    aggregated_metadata: dict[str, Any],
    choices_array: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a complete completion response."""
    response = CompletionResponse(
        id=aggregated_metadata.get("id", ""),
        created=aggregated_metadata.get("created", 0),
        model=aggregated_metadata.get("model", ""),
        object="chat.completion",
        system_fingerprint=aggregated_metadata.get("system_fingerprint", ""),
        choices=choices_array,
        usage=aggregated_metadata.get("usage", {}),
        service_tier=aggregated_metadata.get("service_tier", "default"),
    )
    return dataclasses.asdict(response)


def _clean_tool_calls(tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Clean up tool_calls - remove incomplete ones and ensure proper format."""
    cleaned_tool_calls = [
        {
            "function": {
                "arguments": tool_call["function"]["arguments"],
                "name": tool_call["function"]["name"],
            },
            "id": tool_call["id"],
            "type": "function",
        }
        for tool_call in tool_calls
        if tool_call.get("id") is not None
        and tool_call.get("function", {}).get("name") is not None
    ]
    return cleaned_tool_calls


def _build_aggregated_output(
    aggregated_metadata: dict[str, Any],
    assistant_acc: list[str],
    tool_calls: list[dict[str, Any]],
    chunk: dict[str, Any],
    reasoning_content: list[str],
    choice_index: int = 0,
) -> dict[str, Any]:
    """Build the aggregated output from accumulated data."""
    current_finish_reason = chunk.get("choices", [{}])[0].get("finish_reason")

    # Use the typed approach for consistency
    choice = _create_completion_choice(
        choice_index=choice_index,
        content_parts=assistant_acc,
        tool_calls=tool_calls,
        reasoning_parts=reasoning_content,
        finish_reason=current_finish_reason,
    )

    choices_array = [dataclasses.asdict(choice)]
    return _build_completion_response(aggregated_metadata, choices_array)


def _create_tracked_stream_wrapper(
    insert_call: Callable[[CallEndCHInsertable], None],
    chunk_iter: Iterator[dict[str, Any]],
    start_call: CallStartCHInsertable,
    model_name: str,
    project_id: str,
) -> Iterator[dict[str, Any]]:
    """Create a wrapper that tracks streaming completion and emits call records."""

    def _stream_wrapper() -> Iterator[dict[str, Any]]:
        # Import helper functions locally to avoid circular imports
        from weave.trace_server.clickhouse_trace_server_batched import (
            _end_call_for_insert_to_ch_insertable_end_call,
            _process_tool_call_delta,
            _update_metadata_from_chunk,
        )

        # (1) send meta chunk first so clients can associate stream
        yield {"_meta": {"weave_call_id": start_call.id}}

        # Initialize accumulation variables for all choices
        aggregated_output: dict[str, Any] | None = None
        choice_contents: dict[int, list[str]] = {}  # Track content by choice index
        choice_tool_calls: dict[
            int, list[dict[str, Any]]
        ] = {}  # Track tool calls by choice index
        choice_reasoning_content: dict[
            int, list[str]
        ] = {}  # Track reasoning by choice index
        choice_finish_reasons: dict[
            int, str | None
        ] = {}  # Track finish reasons by choice index
        aggregated_metadata: dict[str, Any] = {}

        try:
            for chunk in chunk_iter:
                yield chunk  # Yield to client immediately

                if not isinstance(chunk, dict):
                    continue

                # Accumulate metadata from chunks
                _update_metadata_from_chunk(chunk, aggregated_metadata)

                # Process all choices in the chunk
                choices = chunk.get("choices")
                if choices:
                    for choice in choices:
                        choice_index = choice.get("index", 0)

                        # Initialize choice accumulators if not present
                        if choice_index not in choice_contents:
                            choice_contents[choice_index] = []
                            choice_tool_calls[choice_index] = []
                            choice_reasoning_content[choice_index] = []
                            choice_finish_reasons[choice_index] = None

                        # Update finish reason
                        if "finish_reason" in choice:
                            choice_finish_reasons[choice_index] = choice[
                                "finish_reason"
                            ]

                        delta = choice.get("delta")
                        if delta and isinstance(delta, dict):
                            # Accumulate assistant content for this choice
                            content_piece = delta.get("content")
                            if content_piece:
                                choice_contents[choice_index].append(content_piece)

                            # Handle tool calls for this choice
                            tool_call_delta = delta.get("tool_calls")
                            if tool_call_delta:
                                _process_tool_call_delta(
                                    tool_call_delta, choice_tool_calls[choice_index]
                                )

                            # Handle reasoning content for this choice
                            reasoning_content_delta = delta.get("reasoning_content")
                            if reasoning_content_delta:
                                choice_reasoning_content[choice_index].append(
                                    reasoning_content_delta
                                )

        finally:
            # Build final aggregated output with all choices
            if choice_contents or choice_tool_calls or choice_reasoning_content:
                choices_array = _build_choices_array(
                    choice_contents,
                    choice_tool_calls,
                    choice_reasoning_content,
                    choice_finish_reasons,
                )
                aggregated_output = _build_completion_response(
                    aggregated_metadata,
                    choices_array,
                )

            # Prepare summary and end call
            summary: dict[str, Any] = {}
            if aggregated_output is not None and model_name is not None:
                aggregated_output["model"] = model_name

                if "usage" in aggregated_output:
                    summary["usage"] = {model_name: aggregated_output["usage"]}

            end = tsi.EndedCallSchemaForInsert(
                project_id=project_id,
                id=start_call.id,
                ended_at=datetime.datetime.now(),
                output=aggregated_output,
                summary=summary,
            )
            end_call = _end_call_for_insert_to_ch_insertable_end_call(
                end, None
            )  # No trace_server in stream wrapper
            insert_call(end_call)

    return _stream_wrapper()
