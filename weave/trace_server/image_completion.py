import base64
import json
from typing import Any, Optional

import requests

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import (
    InvalidRequest,
)
from weave.trace_server.trace_server_interface_util import str_digest
from weave.type_wrappers.Content.content import Content


def _download_image_from_url(url: str) -> bytes:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.content


def _decode_base64_image(b64_data: str) -> bytes:
    # Remove data URL prefix if present (e.g., "data:image/png;base64,")
    if b64_data.startswith("data:"):
        b64_data = b64_data.split(",", 1)[1]

    # Validate base64 before decoding
    import re

    if not re.match(r"^[A-Za-z0-9+/]*={0,2}$", b64_data):
        raise ValueError("Invalid base64 characters in image data")

    decoded = base64.b64decode(b64_data, validate=True)
    return decoded


def create_content_object(
    data: bytes,
    original_schema: str,
    project_id: str,
    trace_server: Any,
    mimetype: Optional[str] = None,
    wb_user_id: Optional[str] = None,
) -> str:
    """
    Create a proper Content object structure and store its files.

    Args:
        data: Raw byte content
        original_schema: The schema to restore the original base64 string
        project_id: Project ID for storage
        trace_server: Trace server instance for file storage
        mimetype: MIME type of the content
        wb_user_id: User ID for object creation

    Returns:
        str: Weave internal reference URI to the stored Content object

    Examples:
        Create and store a Content object::

            ref = create_content_object(
                image_data,
                "url",
                project_id,
                trace_server,
                "image/png"
            )
    """
    content_obj = Content.from_bytes(
        data, mimetype=mimetype, metadata={"_original_schema": original_schema}
    )

    content_data = content_obj.data
    metadata_data = json.dumps(content_obj.model_dump(exclude={"data"})).encode("utf-8")

    # Create files in storage
    # 1. Store the actual content
    content_req = tsi.FileCreateReq(
        project_id=project_id, name="content", content=content_data
    )
    content_res = trace_server.file_create(content_req)

    # 2. Store the metadata
    metadata_req = tsi.FileCreateReq(
        project_id=project_id, name="metadata.json", content=metadata_data
    )
    metadata_res = trace_server.file_create(metadata_req)

    # We exclude the load op because it isn't possible to get from the server side
    content_obj_dict = {
        "_type": "CustomWeaveType",
        "weave_type": {"type": "weave.type_wrappers.Content.content.Content"},
        "files": {"content": content_res.digest, "metadata.json": metadata_res.digest},
    }
    content_obj_digest = str_digest(json.dumps(content_obj_dict))
    object_id = f"content_{content_obj_digest}"

    ref_digest = trace_server.obj_create(
        tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=project_id,
                object_id=object_id,
                val=content_obj_dict,
                wb_user_id=wb_user_id,
            )
        )
    )

    ref = f"weave-trace-internal:///{project_id}/object/{object_id}:{ref_digest.digest}"
    return ref


def _process_image_data_item(
    data_item: dict[str, Any],
    index: int,
    trace_server: Optional[Any] = None,
    project_id: Optional[str] = None,
    wb_user_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Process a single image data item, downloading/decoding and creating Content objects.

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

    try:
        # Handle URL-based images
        if "url" in data_item and data_item["url"] and trace_server and project_id:
            url = data_item["url"]
            image_data = _download_image_from_url(url)

            # Try to infer mimetype from URL
            mimetype = "image/png"  # Default
            if url.lower().endswith(".jpg") or url.lower().endswith(".jpeg"):
                mimetype = "image/jpeg"
            elif url.lower().endswith(".webp"):
                mimetype = "image/webp"

            # Create proper Content object with file storage
            content_ref = create_content_object(
                data=image_data,
                original_schema="url",
                project_id=project_id,
                trace_server=trace_server,
                mimetype=mimetype,
                wb_user_id=wb_user_id,
            )
            processed_item["content_ref"] = content_ref

        # Handle base64-encoded images
        elif (
            "b64_json" in data_item
            and data_item["b64_json"]
            and trace_server
            and project_id
        ):
            b64_data = data_item["b64_json"]
            image_data = _decode_base64_image(b64_data)

            # Create proper Content object with file storage
            content_ref = create_content_object(
                data=image_data,
                original_schema="b64_json",
                project_id=project_id,
                trace_server=trace_server,
                mimetype="image/png",  # Base64 images are typically PNG
                wb_user_id=wb_user_id,
            )
            processed_item["content_ref"] = content_ref

            # Clear/mark the original base64 data as converted
            processed_item["b64_json"] = "Converted to Content"

    except Exception as e:
        # Don't raise - just log the error and return the original item
        processed_item["processing_error"] = str(e)

    return processed_item


def lite_llm_image_generation(
    api_key: Optional[str],
    inputs: dict[str, Any],
    provider: Optional[str] = None,
    base_url: Optional[str] = None,
    extra_headers: Optional[dict[str, str]] = None,
    trace_server: Optional[Any] = None,
    project_id: Optional[str] = None,
    wb_user_id: Optional[str] = None,
) -> tsi.ImageGenerationCreateRes:
    """
    Generate images using LiteLLM image generation.

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
        if model_name in ["dall-e-3", "gpt-image-1"]:
            default_quality = "high" if model_name == "gpt-image-1" else "standard"
            image_params["quality"] = default_quality

        # Only set style parameter for DALL-E 3
        if model_name == "dall-e-3":
            image_params["style"] = "natural"  # Default style

        # Set default size for models that need it
        if model_name == "dall-e-3":
            image_params["size"] = "1024x1024"
        elif model_name == "gpt-image-1":
            image_params["size"] = "1024x1024"
        else:
            image_params["size"] = "1024x1024"

        try:
            # gpt-image-1 doesn't support response_format parameter
            if model_name == "gpt-image-1":
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

        # Process and convert images to Content objects
        if "data" in response_data:
            try:
                data_list = response_data.get("data", [])
                if isinstance(data_list, list):
                    processed_data = []
                    for index, data_item in enumerate(data_list):
                        if isinstance(data_item, dict):
                            processed_item = _process_image_data_item(
                                data_item, index, trace_server, project_id, wb_user_id
                            )
                            processed_data.append(processed_item)
                        else:
                            processed_data.append(data_item)
                    response_data["data"] = processed_data
            except Exception as e:
                # Continue without failing - the response will still contain the original data
                pass

        return tsi.ImageGenerationCreateRes(response=response_data)
    except Exception as e:
        error_message = str(e)
        error_message = error_message.replace("litellm.", "")
        return tsi.ImageGenerationCreateRes(response={"error": error_message})
