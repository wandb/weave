from typing import Optional

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import (
    InvalidRequest,
    MissingLLMApiKeyError,
)
from weave.trace_server.secret_fetcher_context import _secret_fetcher_context

NOVA_MODELS = ("nova-pro-v1", "nova-lite-v1", "nova-micro-v1")


def lite_llm_completion(
    api_key: str,
    inputs: tsi.CompletionsCreateRequestInputs,
    provider: Optional[str] = None,
) -> tsi.CompletionsCreateRes:
    aws_access_key_id, aws_secret_access_key, aws_region_name = None, None, None
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

    import litellm

    # This allows us to drop params that are not supported by the LLM provider
    litellm.drop_params = True
    try:
        res = litellm.completion(
            **inputs.model_dump(exclude_none=True),
            api_key=api_key,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_region_name=aws_region_name,
        )
        return tsi.CompletionsCreateRes(response=res.model_dump())
    except Exception as e:
        error_message = str(e)
        error_message = error_message.replace("litellm.", "")
        return tsi.CompletionsCreateRes(response={"error": error_message})


def get_bedrock_credentials(
    model_name: str,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
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
