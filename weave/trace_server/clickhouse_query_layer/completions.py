# ClickHouse Completions - LLM completion operations
#
# This module handles LLM completion operations including streaming completions
# and image generation.

import datetime
import logging
from collections.abc import Callable, Iterator
from re import sub
from typing import TYPE_CHECKING, Any

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse_query_layer.calls import (
    end_call_for_insert_to_ch_insertable,
    start_call_for_insert_to_ch_insertable,
)
from weave.trace_server.clickhouse_query_layer.schema import (
    ALL_CALL_INSERT_COLUMNS,
    CallEndCHInsertable,
    CallStartCHInsertable,
)
from weave.trace_server.constants import (
    COMPLETIONS_CREATE_OP_NAME,
    IMAGE_GENERATION_CREATE_OP_NAME,
)
from weave.trace_server.errors import MissingLLMApiKeyError
from weave.trace_server.image_completion import lite_llm_image_generation
from weave.trace_server.llm_completion import (
    get_custom_provider_info,
    lite_llm_completion,
    lite_llm_completion_stream,
    resolve_and_apply_prompt,
)
from weave.trace_server.project_version.types import WriteTarget
from weave.trace_server.secret_fetcher_context import _secret_fetcher_context

if TYPE_CHECKING:
    from weave.trace_server.clickhouse_query_layer.batching import BatchManager
    from weave.trace_server.clickhouse_query_layer.client import ClickHouseClient
    from weave.trace_server.project_version.project_version import TableRoutingResolver

logger = logging.getLogger(__name__)


class CompletionsRepository:
    """Repository for LLM completion operations."""

    def __init__(
        self,
        ch_client: "ClickHouseClient",
        batch_manager: "BatchManager",
        table_routing_resolver: "TableRoutingResolver",
        obj_read_func: Callable[[tsi.ObjReadReq], tsi.ObjReadRes],
        insert_call_func: Callable[[Any], None],
        insert_call_batch_func: Callable[[list], None],
        model_to_provider_info_map: dict[str, Any],
    ):
        self._ch_client = ch_client
        self._batch_manager = batch_manager
        self._table_routing_resolver = table_routing_resolver
        self._obj_read = obj_read_func
        self._insert_call = insert_call_func
        self._insert_call_batch = insert_call_batch_func
        self._model_to_provider_info_map = model_to_provider_info_map

    def completions_create(
        self, req: tsi.CompletionsCreateReq
    ) -> tsi.CompletionsCreateRes:
        """Create an LLM completion."""
        # Resolve prompt if provided
        prompt = getattr(req.inputs, "prompt", None)
        template_vars = getattr(req.inputs, "template_vars", None)

        try:
            combined_messages, initial_messages = resolve_and_apply_prompt(
                prompt=prompt,
                messages=getattr(req.inputs, "messages", None),
                template_vars=template_vars,
                project_id=req.project_id,
                obj_read_func=self._obj_read,
            )
        except Exception as e:
            logger.error(f"Failed to resolve and apply prompt: {e}", exc_info=True)
            return tsi.CompletionsCreateRes(
                response={"error": f"Failed to resolve and apply prompt: {e!s}"}
            )

        # Setup model info
        model_info = self._model_to_provider_info_map.get(req.inputs.model)
        try:
            (
                model_name,
                api_key,
                provider,
                base_url,
                extra_headers,
                return_type,
            ) = _setup_completion_model_info(model_info, req, self._obj_read)
        except Exception as e:
            return tsi.CompletionsCreateRes(response={"error": str(e)})

        # Set the combined messages for LiteLLM
        req.inputs.messages = combined_messages

        # Make the API call
        start_time = datetime.datetime.now()
        res = lite_llm_completion(
            api_key=api_key,
            inputs=req.inputs,
            provider=provider,
            base_url=base_url,
            extra_headers=extra_headers,
            return_type=return_type,
        )
        end_time = datetime.datetime.now()

        if not req.track_llm_call:
            return tsi.CompletionsCreateRes(response=res.response)

        # Track the call
        write_target = self._table_routing_resolver.resolve_v2_write_target(
            req.project_id,
            self._ch_client.ch_client,
        )
        if write_target == WriteTarget.CALLS_COMPLETE:
            write_target = WriteTarget.CALLS_MERGED

        req.inputs.messages = initial_messages
        start = tsi.StartedCallSchemaForInsert(
            project_id=req.project_id,
            wb_user_id=req.wb_user_id,
            op_name=COMPLETIONS_CREATE_OP_NAME,
            started_at=start_time,
            inputs={**req.inputs.model_dump(exclude_none=True)},
            attributes={},
        )
        start_call = start_call_for_insert_to_ch_insertable(start)
        end = tsi.EndedCallSchemaForInsert(
            project_id=req.project_id,
            id=start_call.id,
            ended_at=end_time,
            output=res.response,
            summary={},
        )
        if "usage" in res.response:
            end.summary["usage"] = {model_name: res.response["usage"]}
        if "error" in res.response:
            end.exception = res.response["error"]

        end_call = end_call_for_insert_to_ch_insertable(end)
        calls: list[CallStartCHInsertable | CallEndCHInsertable] = [
            start_call,
            end_call,
        ]
        batch_data = []
        for call in calls:
            call_dict = call.model_dump()
            values = [call_dict.get(col) for col in ALL_CALL_INSERT_COLUMNS]
            batch_data.append(values)

        if write_target == WriteTarget.CALLS_MERGED:
            self._insert_call_batch(batch_data)

        return tsi.CompletionsCreateRes(
            response=res.response, weave_call_id=start_call.id
        )

    def completions_create_stream(
        self, req: tsi.CompletionsCreateReq
    ) -> Iterator[dict[str, Any]]:
        """Stream LLM completion chunks."""
        # Resolve prompt if provided
        prompt = getattr(req.inputs, "prompt", None)
        template_vars = getattr(req.inputs, "template_vars", None)

        try:
            combined_messages, initial_messages = resolve_and_apply_prompt(
                prompt=prompt,
                messages=getattr(req.inputs, "messages", None),
                template_vars=template_vars,
                project_id=req.project_id,
                obj_read_func=self._obj_read,
            )
        except Exception as e:
            logger.error(f"Failed to resolve and apply prompt: {e}", exc_info=True)

            def _single_error_iter(err: Exception) -> Iterator[dict[str, str]]:
                yield {"error": f"Failed to resolve and apply prompt: {err!s}"}

            return _single_error_iter(e)

        # Setup model info
        model_info = self._model_to_provider_info_map.get(req.inputs.model)
        try:
            (
                model_name,
                api_key,
                provider,
                base_url,
                extra_headers,
                return_type,
            ) = _setup_completion_model_info(model_info, req, self._obj_read)
        except Exception as e:

            def _single_error_iter(err: Exception) -> Iterator[dict[str, str]]:
                yield {"error": str(err)}

            return _single_error_iter(e)

        # Track start call if requested
        start_call: CallStartCHInsertable | None = None
        write_target: WriteTarget | None = None
        if req.track_llm_call:
            write_target = self._table_routing_resolver.resolve_v2_write_target(
                req.project_id,
                self._ch_client.ch_client,
            )
            if write_target == WriteTarget.CALLS_COMPLETE:
                write_target = WriteTarget.CALLS_MERGED

            tracked_inputs = req.inputs.model_dump(exclude_none=True)
            tracked_inputs["model"] = model_name
            tracked_inputs["messages"] = initial_messages
            if prompt:
                tracked_inputs["prompt"] = prompt
            if template_vars:
                tracked_inputs["template_vars"] = template_vars

            start = tsi.StartedCallSchemaForInsert(
                project_id=req.project_id,
                wb_user_id=req.wb_user_id,
                op_name=COMPLETIONS_CREATE_OP_NAME,
                started_at=datetime.datetime.now(),
                inputs=tracked_inputs,
                attributes={},
            )
            start_call = start_call_for_insert_to_ch_insertable(start)
            if write_target == WriteTarget.CALLS_MERGED:
                self._insert_call(start_call)

        # Set combined messages for LiteLLM
        req.inputs.messages = combined_messages

        # Make API call without prompt and template_vars
        api_inputs = req.inputs.model_copy()
        if hasattr(api_inputs, "prompt"):
            api_inputs.prompt = None
        if hasattr(api_inputs, "template_vars"):
            api_inputs.template_vars = None

        chunk_iter = lite_llm_completion_stream(
            api_key=api_key or "",
            inputs=api_inputs,
            provider=provider,
            base_url=base_url,
            extra_headers=extra_headers,
            return_type=return_type,
        )

        if not req.track_llm_call or start_call is None:
            return chunk_iter

        # Wrap with tracking
        return _create_tracked_stream_wrapper(
            self._insert_call,
            chunk_iter,
            start_call,
            model_name,
            req.project_id,
        )

    def image_create(
        self, req: tsi.ImageGenerationCreateReq, trace_server: Any
    ) -> tsi.ImageGenerationCreateRes:
        """Create an image generation."""
        secret_fetcher = _secret_fetcher_context.get()
        if secret_fetcher is None:
            return tsi.ImageGenerationCreateRes(
                response={"error": "Secret fetcher context not set"}
            )

        secrets = secret_fetcher.fetch("OPENAI_API_KEY")
        api_key = secrets.get("secrets", {}).get("OPENAI_API_KEY")

        if api_key is None:
            return tsi.ImageGenerationCreateRes(
                response={"error": "No OpenAI API key found"}
            )

        start_time = datetime.datetime.now()

        try:
            res = lite_llm_image_generation(
                api_key=api_key,
                inputs=req.inputs.model_dump(exclude_none=True),
                trace_server=trace_server,
                project_id=req.project_id,
                wb_user_id=req.wb_user_id,
            )
            if "error" in res.response:
                return tsi.ImageGenerationCreateRes(
                    response={"error": res.response["error"]}
                )
        except Exception as e:
            return tsi.ImageGenerationCreateRes(
                response={"error": f"Image generation failed: {e!s}"}
            )

        end_time = datetime.datetime.now()

        if req.track_llm_call is False:
            return res

        # Track the call
        input_data = req.inputs.model_dump(exclude_none=False)
        start = tsi.StartedCallSchemaForInsert(
            project_id=req.project_id,
            wb_user_id=req.wb_user_id,
            op_name=IMAGE_GENERATION_CREATE_OP_NAME,
            started_at=start_time,
            inputs=input_data,
            attributes={},
        )
        start_call = start_call_for_insert_to_ch_insertable(start)

        end = tsi.EndedCallSchemaForInsert(
            project_id=req.project_id,
            id=start_call.id,
            ended_at=end_time,
            output=res.response,
            summary={},
        )

        if "usage" in res.response:
            end.summary["usage"] = {req.inputs.model: res.response["usage"]}
        if "error" in res.response:
            end.exception = res.response["error"]

        end_call = end_call_for_insert_to_ch_insertable(end)
        calls: list[CallStartCHInsertable | CallEndCHInsertable] = [
            start_call,
            end_call,
        ]
        batch_data = []
        for call in calls:
            call_dict = call.model_dump()
            values = [call_dict.get(col) for col in ALL_CALL_INSERT_COLUMNS]
            batch_data.append(values)

        try:
            self._insert_call_batch(batch_data)
        except Exception as e:
            logger.exception("Error inserting call batch for image generation")

        return tsi.ImageGenerationCreateRes(
            response=res.response, weave_call_id=start_call.id
        )


# =============================================================================
# Helper Functions
# =============================================================================


def _sanitize_name_for_object_id(name: str) -> str:
    """Sanitize a name to be used as part of an object_id."""
    return sub(r"[^a-zA-Z0-9_-]", "_", name)


def _setup_completion_model_info(
    model_info: Any,
    req: tsi.CompletionsCreateReq,
    obj_read_func: Callable[[tsi.ObjReadReq], tsi.ObjReadRes],
) -> tuple[str, str | None, str | None, str | None, dict | None, str | None]:
    """Setup model info for completion.

    Returns:
        Tuple of (model_name, api_key, provider, base_url, extra_headers, return_type)
    """
    secret_fetcher = _secret_fetcher_context.get()
    if secret_fetcher is None:
        raise MissingLLMApiKeyError(
            "Secret fetcher context not set", api_key_name="N/A"
        )

    # Default values
    model_name = req.inputs.model
    api_key: str | None = None
    provider: str | None = None
    base_url: str | None = None
    extra_headers: dict | None = None
    return_type: str | None = None

    if model_info:
        # Model is in our known list, use the model info
        model_name = model_info.get("litellm_model", model_name)
        provider = model_info.get("provider")
        api_key_name = model_info.get("api_key_name")
        if api_key_name:
            secrets = secret_fetcher.fetch(api_key_name)
            api_key = secrets.get("secrets", {}).get(api_key_name)
    else:
        # Check if it's a custom provider model
        # Custom provider path - model_name format: custom::<provider>::<model>
        # Parse provider and model names, create sanitized object_id for lookup
        raw_model = req.inputs.model
        name_part = raw_model.replace("custom::", "")

        if "::" in name_part:
            # Format: custom::<provider>::<model>
            provider_name, model_name_part = name_part.split("::", 1)

            # Create sanitized object_id to match what was created during provider setup
            sanitized_provider = _sanitize_name_for_object_id(provider_name)
            sanitized_model = _sanitize_name_for_object_id(model_name_part)
            sanitized_object_id = f"{sanitized_provider}-{sanitized_model}"
        else:
            # Fallback: assume it's already in object_id format
            # Extract names from object_id (this is a fallback case)
            parts = name_part.split("-", 1) if "-" in name_part else [name_part, ""]
            provider_name = parts[0]  # May be sanitized
            sanitized_provider = provider_name  # Already sanitized
            sanitized_object_id = name_part

        custom_provider_info = get_custom_provider_info(
            project_id=req.project_id,
            provider_name=sanitized_provider,
            model_name=sanitized_object_id,
            obj_read_func=obj_read_func,
        )

        if custom_provider_info:
            # CustomProviderInfo is a Pydantic BaseModel - use attribute access
            model_name = custom_provider_info.actual_model_name
            base_url = custom_provider_info.base_url
            extra_headers = custom_provider_info.extra_headers
            return_type = custom_provider_info.return_type
            api_key = (
                custom_provider_info.api_key
            )  # Already fetched by get_custom_provider_info
        else:
            # Unknown model, try to get API key from common providers
            common_keys = ["OPENAI_API_KEY", "ANTHROPIC_API_KEY"]
            for key in common_keys:
                secrets = secret_fetcher.fetch(key)
                if secrets.get("secrets", {}).get(key):
                    api_key = secrets["secrets"][key]
                    break

    return model_name, api_key, provider, base_url, extra_headers, return_type


def _create_tracked_stream_wrapper(
    insert_call_func: Callable[[Any], None],
    chunk_iter: Iterator[dict[str, Any]],
    start_call: CallStartCHInsertable,
    model_name: str,
    project_id: str,
) -> Iterator[dict[str, Any]]:
    """Create a wrapper that tracks streaming completion chunks."""
    # Yield meta chunk with call ID first
    yield {"_meta": {"weave_call_id": start_call.id}}

    # Track state across chunks
    accumulated_response: dict[str, Any] = {}
    error_occurred: str | None = None

    try:
        for chunk in chunk_iter:
            # Yield the chunk to the caller
            yield chunk

            # Update accumulated response
            if "error" in chunk:
                error_occurred = chunk["error"]
            else:
                _update_accumulated_response(accumulated_response, chunk)

    finally:
        # Always insert the end call, even if there was an error
        end = tsi.EndedCallSchemaForInsert(
            project_id=project_id,
            id=start_call.id,
            ended_at=datetime.datetime.now(),
            output=accumulated_response,
            summary={},
            exception=error_occurred,
        )

        if accumulated_response.get("usage"):
            end.summary["usage"] = {model_name: accumulated_response["usage"]}

        end_call = end_call_for_insert_to_ch_insertable(end)
        insert_call_func(end_call)


def _update_accumulated_response(
    accumulated: dict[str, Any], chunk: dict[str, Any]
) -> None:
    """Update accumulated response from a streaming chunk."""
    # Handle various chunk formats from different providers
    if "choices" in chunk:
        if "choices" not in accumulated:
            accumulated["choices"] = []
        for choice in chunk["choices"]:
            idx = choice.get("index", 0)
            while len(accumulated["choices"]) <= idx:
                accumulated["choices"].append(
                    {"index": len(accumulated["choices"]), "message": {"content": ""}}
                )
            if "delta" in choice:
                delta = choice["delta"]
                if "content" in delta and delta["content"]:
                    accumulated["choices"][idx]["message"]["content"] += delta[
                        "content"
                    ]
            # Preserve finish_reason
            if "finish_reason" in choice and choice["finish_reason"]:
                accumulated["choices"][idx]["finish_reason"] = choice["finish_reason"]

    if "usage" in chunk:
        accumulated["usage"] = chunk["usage"]

    if "model" in chunk:
        accumulated["model"] = chunk["model"]
