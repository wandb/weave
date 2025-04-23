from typing import Callable, Optional

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

NOVA_MODELS = ("nova-pro-v1", "nova-lite-v1", "nova-micro-v1")


def lite_llm_completion(
    api_key: str,
    inputs: tsi.CompletionsCreateRequestInputs,
    provider: Optional[str] = None,
    base_url: Optional[str] = None,
    extra_headers: Optional[dict[str, str]] = None,
    return_type: Optional[str] = None,
) -> tsi.CompletionsCreateRes:
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


class CustomProviderInfo(BaseModel):
    base_url: str
    api_key: str
    extra_headers: dict[str, str]
    return_type: str
    actual_model_name: str


def get_custom_provider_info(
    project_id: str,
    model_name: str,
    obj_read_func: Callable,
) -> CustomProviderInfo:
    """
    Extract provider information from a custom provider model.
    Args:
        project_id: The project ID
        model_name: The model name (format: <provider_id>/<provider_model_id>)
        obj_read_func: Function to read objects from the database
        secret_fetcher: Secret fetcher to get API keys
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

    # Parse the model name to extract provider_id and provider_model_id
    # Format: <provider_id>/<provider_model_id>
    parts = model_name.split("/")
    if len(parts) < 2:
        raise InvalidRequest(f"Invalid custom provider model format: {model_name}")

    provider_id = parts[0]
    provider_model_id = parts[1]

    # Default values
    base_url = None
    secret_name = None
    extra_headers = {}
    return_type = "openai"
    actual_model_name = model_name

    try:
        # Fetch the provider object
        provider_obj_req = tsi.ObjReadReq(
            project_id=project_id,
            object_id=provider_id,
            digest="latest",
            metadata_only=False,
        )
        provider_obj_res = obj_read_func(provider_obj_req)

        if provider_obj_res.obj.base_object_class != "Provider":
            raise InvalidRequest(
                f"Object {provider_id} is not a Provider, it is a {provider_obj_res.obj.base_object_class}"
            )

        provider_obj = Provider.model_validate(provider_obj_res.obj.val)

        base_url = provider_obj.base_url
        secret_name = provider_obj.api_key_name
        extra_headers = provider_obj.extra_headers
        return_type = provider_obj.return_type

    except Exception as e:
        raise InvalidRequest(f"Failed to fetch provider information: {str(e)}")

    try:
        # Fetch the provider model object
        # Provider models have the format: <provider_id>-<provider_model>
        provider_model_obj_req = tsi.ObjReadReq(
            project_id=project_id,
            object_id=f"{provider_id}-{provider_model_id}",
            digest="latest",
            metadata_only=False,
        )
        provider_model_obj_res = obj_read_func(provider_model_obj_req)

        if provider_model_obj_res.obj.base_object_class != "ProviderModel":
            raise InvalidRequest(
                f"Object {provider_model_id} is not a ProviderModel, it is a {provider_model_obj_res.obj.base_object_class}"
            )

        provider_model_obj = ProviderModel.model_validate(
            provider_model_obj_res.obj.val
        )

        # Use the provider model's name as the actual model name for the API call
        actual_model_name = provider_model_obj.name

    except Exception as e:
        raise InvalidRequest(f"Failed to fetch provider_model information: {str(e)}")

    # Get the API key
    if not secret_name:
        raise InvalidRequest(f"No secret name found for provider {provider_id}")

    api_key = secret_fetcher.fetch(secret_name).get("secrets", {}).get(secret_name)

    if not api_key:
        raise MissingLLMApiKeyError(
            f"No API key {secret_name} found for provider {provider_id}",
            api_key_name=secret_name,
        )

    return CustomProviderInfo(
        base_url=base_url,
        api_key=api_key,
        extra_headers=extra_headers,
        return_type=return_type,
        actual_model_name=actual_model_name,
    )
