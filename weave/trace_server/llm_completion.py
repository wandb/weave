from collections.abc import Callable, Iterator
from typing import Any

from pydantic import BaseModel

from weave.prompt.prompt import format_message_with_template_vars
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import (
    InvalidRequest,
    MissingLLMApiKeyError,
    NotFoundError,
)
from weave.trace_server.interface.builtin_object_classes.provider import (
    Provider,
    ProviderModel,
)
from weave.trace_server.secret_fetcher_context import _secret_fetcher_context

NOVA_MODELS = ("nova-pro-v1", "nova-lite-v1", "nova-micro-v1")


def parse_prompt_reference(prompt: str) -> tuple[str, str, str | None]:
    """Parse a prompt reference into its components.

    Supports multiple reference formats:
    1. Internal URI: "weave-trace-internal:///project_id/object/name:digest"
    2. Full weave URI: "weave:///entity/project/object/name:digest"
    3. Simple format: "object_id:digest" or "object_id:vN"
    4. Name only: "object_id" (assumes latest version)

    Args:
        prompt: The prompt reference string to parse

    Returns:
        Tuple of (object_id, version, project_id_from_uri)
        - object_id: The name/ID of the prompt object
        - version: The version/digest (or "latest" if not specified)
        - project_id_from_uri: The project_id extracted from URI (None for simple format)

    Raises:
        InvalidRequest: If the prompt reference format is invalid

    Examples:
        >>> parse_prompt_reference("my_prompt:v1")
        ("my_prompt", "v1", None)

        >>> parse_prompt_reference("my_prompt")
        ("my_prompt", "latest", None)

        >>> parse_prompt_reference("weave:///entity/project/object/my_prompt:abc123")
        ("my_prompt", "abc123", "project_id")
    """
    from weave.trace_server import refs_internal as ri

    # Handle Weave URI formats (internal and external)
    if prompt.startswith(("weave-trace-internal:///", "weave:///")):
        try:
            parsed_ref = ri.parse_internal_uri(prompt)
            if not isinstance(parsed_ref, ri.InternalObjectRef):
                raise InvalidRequest(
                    f"Prompt reference must be an object reference, got: {type(parsed_ref).__name__}"
                )
            else:
                return (
                    parsed_ref.name,
                    parsed_ref.version,
                    parsed_ref.project_id or None,
                )
        except InvalidRequest:
            # Re-raise InvalidRequest as-is
            raise
        except Exception as e:
            raise InvalidRequest(
                f"Failed to parse prompt reference '{prompt}': {e!s}"
            ) from e

    # Handle simple formats
    if ":" in prompt:
        # Format: "object_id:version"
        object_id, version = prompt.rsplit(":", 1)
        return object_id, version, None

    # Format: "object_id" (no version specified)
    return prompt, "latest", None


def resolve_prompt_messages(
    prompt: str,
    project_id: str,
    obj_read_func: Callable[[tsi.ObjReadReq], tsi.ObjReadRes],
) -> list[dict[str, Any]]:
    """Resolve a prompt reference to its messages.

    Args:
        prompt: The prompt reference (e.g., "weave:///entity/project/object/prompt_name:version")
        project_id: The project ID (can be overridden if prompt contains a full URI with project_id)
        obj_read_func: Function to read objects from the database

    Returns:
        List of messages from the prompt
    """
    object_id, version, uri_project_id = parse_prompt_reference(prompt)

    # Use project_id from URI if available, otherwise use the provided one
    if uri_project_id:
        project_id = uri_project_id

    # Fetch the prompt object
    try:
        prompt_obj_req = tsi.ObjReadReq(
            project_id=project_id,
            object_id=object_id,
            digest=version,
            metadata_only=False,
        )
        prompt_obj_res = obj_read_func(prompt_obj_req)

        if prompt_obj_res.obj is None:
            raise NotFoundError(f"Could not find prompt with ref {prompt}")

        # Validate that this is a Prompt or MessagesPrompt object
        if prompt_obj_res.obj.base_object_class not in ("Prompt", "MessagesPrompt"):
            raise InvalidRequest(
                f"Prompt {prompt} is not a Prompt or MessagesPrompt (found {prompt_obj_res.obj.base_object_class})"
            )

        # Extract messages from the prompt object
        prompt_val = prompt_obj_res.obj.val

        if not isinstance(prompt_val, dict):
            raise InvalidRequest(f"Prompt {prompt} has invalid format")

        messages = prompt_val.get("messages", [])

        if not isinstance(messages, list):
            raise InvalidRequest(f"Prompt {prompt} messages field is not a list")
        else:
            return messages
    except NotFoundError:
        raise
    except Exception as e:
        raise InvalidRequest(
            f"Failed to resolve prompt reference {prompt}: {e!s}"
        ) from e


def resolve_and_apply_prompt(
    prompt: str | None,
    messages: list[dict[str, Any]] | None,
    template_vars: dict[str, Any] | None,
    project_id: str,
    obj_read_func: Callable[[tsi.ObjReadReq], tsi.ObjReadRes],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Resolve prompt reference and apply template variables to combined messages.

    This helper consolidates the logic for:
    1. Resolving a prompt reference to its messages (if provided)
    2. Combining prompt messages with user-provided messages
    3. Applying template variable substitution to the combined messages

    Args:
        prompt: Optional prompt reference (e.g., "weave:///entity/project/object/prompt:digest")
        messages: Optional list of user-provided message dictionaries
        template_vars: Optional dictionary of template variables to replace
        project_id: The project ID for resolving the prompt
        obj_read_func: Function to read objects from the database

    Returns:
        Tuple of (combined_templated_messages, initial_messages):
        - combined_templated_messages: The final messages with prompt + user messages + template vars applied
        - initial_messages: The original user-provided messages (before template vars)

    Raises:
        NotFoundError: If the prompt reference cannot be found
        InvalidRequest: If the prompt format is invalid or required template variables are missing

    Examples:
        >>> # With prompt and template vars
        >>> combined, initial = resolve_and_apply_prompt(
        ...     prompt="weave:///entity/project/object/my_prompt:v1",
        ...     messages=[{"role": "user", "content": "Hello"}],
        ...     template_vars={"name": "World"},
        ...     project_id="entity/project",
        ...     obj_read_func=obj_read
        ... )

        >>> # Without prompt (just user messages)
        >>> combined, initial = resolve_and_apply_prompt(
        ...     prompt=None,
        ...     messages=[{"role": "user", "content": "Hello {name}"}],
        ...     template_vars={"name": "World"},
        ...     project_id="entity/project",
        ...     obj_read_func=obj_read
        ... )
    """
    initial_messages = messages or []
    prompt_messages = []

    # Step 1: Resolve prompt reference to messages (if provided)
    if prompt:
        prompt_messages = resolve_prompt_messages(
            prompt=prompt,
            project_id=project_id,
            obj_read_func=obj_read_func,
        )

    # Step 2: Combine prompt messages with user messages
    combined_messages = prompt_messages + initial_messages

    # Step 3: Apply template variable substitution (if provided)
    if template_vars and combined_messages:
        combined_messages = [
            (
                format_message_with_template_vars(msg, **template_vars)
                # Skip template variable substitution for assistant messages
                # If for example we specified a JSON response format, the assistant message would be a JSON string.
                if msg.get("role") != "assistant"
                else msg
            )
            for msg in combined_messages
        ]

    return combined_messages, initial_messages


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

    # Exclude weave-specific fields that litellm doesn't understand
    inputs_dict = inputs.model_dump(
        exclude_none=True, exclude={"prompt", "template_vars"}
    )

    # Handle custom provider
    if provider == "custom" and base_url:
        try:
            # Prepare headers
            headers = extra_headers or {}

            # Make the API call using litellm
            res = litellm.completion(
                **inputs_dict,
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
            **inputs_dict,
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


class ChoiceMessage(BaseModel):
    """Typed representation of a choice message."""

    content: str | None = None
    role: str
    tool_calls: list[dict[str, Any]] | None = None
    function_call: dict[str, Any] | None = None
    reasoning_content: str | None = None


class CompletionChoice(BaseModel):
    """Typed representation of a completion choice."""

    finish_reason: str | None = None
    index: int
    message: ChoiceMessage


class CompletionResponse(BaseModel):
    """Typed representation of a completion response."""

    id: str
    created: int
    model: str
    object: str
    system_fingerprint: str | None = None
    choices: list[dict[str, Any]]
    usage: dict[str, Any]
    service_tier: str | None = None


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
        choices.append(choice.model_dump())

    return choices


def _build_completion_response(
    aggregated_metadata: dict[str, Any],
    choices_array: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a complete completion response."""
    response = CompletionResponse(
        id=aggregated_metadata.get("id") or "",
        created=aggregated_metadata.get("created") or 0,
        model=aggregated_metadata.get("model") or "",
        object="chat.completion",
        system_fingerprint=aggregated_metadata.get("system_fingerprint"),
        choices=choices_array,
        usage=aggregated_metadata.get("usage") or {},
        service_tier=aggregated_metadata.get("service_tier"),
    )
    return response.model_dump()


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
