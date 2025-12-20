from typing import Any

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.base64_content_conversion import store_content_object
from weave.trace_server.errors import (
    InvalidRequest,
)
from weave.type_wrappers.Content.content import Content


def _process_image_data_item(
    data_item: dict[str, Any],
    index: int,
    trace_server: Any | None = None,
    project_id: str | None = None,
    wb_user_id: str | None = None,
) -> dict[str, Any]:
    """Process a single image data item, creating Content objects from URLs or base64 data.

    Args:
        data_item (dict): The image data item from the API response.
        index (int): The index of this item in the data array.
        trace_server (Optional[Any]): The trace server instance for file storage.
        project_id (Optional[str]): The project ID for file storage.
        wb_user_id (Optional[str]): The user ID for object creation.

    Returns:
        dict: The modified data item with Content object references instead of raw data.

    Examples:
        Process an image data item::

            processed_item = _process_image_data_item(
                {"url": "https://example.com/image.png"},
                0,
                trace_server,
                project_id,
                wb_user_id
            )
    """
    # Make a copy to avoid modifying the original
    processed_item = data_item.copy()
    content_obj: Content[Any]

    try:
        # Handle URL-based images
        if "url" in data_item and data_item["url"] and trace_server and project_id:
            url = data_item["url"]
            # Use Content.from_url() to handle download and content creation
            content_obj = Content.from_url(
                url, metadata={"source_index": index, "_original_schema": "url"}
            )
            content_dict = store_content_object(content_obj, project_id, trace_server)
            processed_item["url"] = content_dict

        # Handle base64-encoded images
        elif (
            "b64_json" in data_item
            and data_item["b64_json"]
            and trace_server
            and project_id
        ):
            b64_data = data_item["b64_json"]

            content_obj = Content.from_base64(
                b64_data,
                mimetype="image/png",
                metadata={"source_index": index, "_original_schema": "b64_json"},
            )
            content_dict = store_content_object(content_obj, project_id, trace_server)
            processed_item["b64_json"] = content_dict

    except Exception as e:
        # Don't raise - just log the error and return the original item
        processed_item["error"] = str(e)

    return processed_item


def lite_llm_image_generation(
    api_key: str | None,
    inputs: dict[str, Any],
    provider: str | None = None,
    base_url: str | None = None,
    extra_headers: dict[str, str] | None = None,
    trace_server: Any | None = None,
    project_id: str | None = None,
    wb_user_id: str | None = None,
) -> tsi.ImageGenerationCreateRes:
    """Generate images using LiteLLM image generation.

    Args:
        api_key (Optional[str]): The API key for the LLM provider.
        inputs (dict[str, Any]): The input parameters for image generation.
        provider (Optional[str]): The provider name.
        base_url (Optional[str]): Custom base URL for the API.
        extra_headers (Optional[dict[str, str]]): Additional headers.
        trace_server (Optional[Any]): The trace server instance for file storage.
        project_id (Optional[str]): The project ID for file storage.
        wb_user_id (Optional[str]): The user ID for object creation.

    Returns:
        tsi.ImageGenerationCreateRes: The image generation response.

    Examples:
        Generate an image with a prompt::

            response = lite_llm_image_generation(
                api_key="sk-...",
                inputs={"model": "dall-e-3", "prompt": "A cat wearing a hat"}
            )
    """
    from litellm import image_generation

    model_name = inputs.get("model", "")

    if not model_name:
        raise InvalidRequest("Model name is required")

    try:
        # Make the image generation API call
        # Pass all parameters so LiteLLM can create proper model identifier for cost calculation
        image_params = {
            "model": inputs.get("model"),
            "prompt": inputs.get("prompt"),
            "api_key": api_key,
        }

        # Add image generation parameters based on model capabilities

        # Handle 'n' parameter (number of images)
        # DALL-E 3 only supports n=1, others can support multiple
        if model_name == "dall-e-3":
            image_params["n"] = 1  # DALL-E 3 only supports 1 image
        else:
            image_params["n"] = inputs.get("n", 1)

        # Only set quality parameter for models that support it (DALL-E 3 and gpt-image-1)
        if model_name in ["dall-e-3", "gpt-image-1", "gpt-image-1.5"]:
            default_quality = (
                "high"
                if model_name == "gpt-image-1" or model_name == "gpt-image-1.5"
                else "standard"
            )
            image_params["quality"] = default_quality

        # Only set style parameter for DALL-E 3
        if model_name == "dall-e-3":
            image_params["style"] = "natural"  # Default style

        # Set default size for models that need it
        if model_name == "dall-e-3":
            image_params["size"] = "1024x1024"
        elif model_name == "gpt-image-1" or model_name == "gpt-image-1.5":
            image_params["size"] = "1024x1024"
        else:
            image_params["size"] = "1024x1024"

        try:
            # gpt-image-1 doesn't support response_format parameter
            if model_name == "gpt-image-1" or model_name == "gpt-image-1.5":
                res = image_generation(**image_params)
            else:
                res = image_generation(response_format="url", **image_params)
        except Exception as e:
            raise

        response_data = res.model_dump()

        # Add model name and usage to response
        response_data["model"] = model_name
        if "usage" in response_data:
            usage = response_data["usage"]
            response_data["usage"]["prompt_tokens"] = (
                usage.get("prompt_tokens") or usage.get("input_tokens") or 0
            )
            response_data["usage"]["completion_tokens"] = (
                usage.get("completion_tokens")
                or usage.get("output_tokens")
                or usage.get("total_tokens")
                or 0
            )
            response_data["usage"]["total_tokens"] = usage.get("total_tokens") or 0

        # Convert images to Content objects and create message format
        if "data" in response_data:
            data_list = response_data.get("data", [])
            if isinstance(data_list, list):
                for index, data_item in enumerate(data_list):
                    if isinstance(data_item, dict):
                        processed_item = _process_image_data_item(
                            data_item, index, trace_server, project_id, wb_user_id
                        )

                        if "b64_json" in processed_item:
                            data_item["b64_json"] = processed_item["b64_json"]
                        if "url" in processed_item:
                            data_item["url"] = processed_item["url"]
                        if "error" in processed_item:
                            response_data["error"] = processed_item["error"]

        return tsi.ImageGenerationCreateRes(response=response_data)
    except Exception as e:
        error_message = str(e)
        error_message = error_message.replace("litellm.", "")
        return tsi.ImageGenerationCreateRes(response={"error": error_message})
