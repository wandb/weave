"""Completions and image-generation mixin for ClickHouseTraceServer.

Extracts ``completions_create``, ``completions_create_stream``, and
``image_create`` into a reusable mixin class, together with the free
helper functions they depend on.
"""
# mypy: disable-error-code="attr-defined"

import dataclasses
import datetime
import logging
import re
from collections.abc import Callable, Iterator
from typing import Any

from weave.trace_server import environment as wf_env
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse.schema_converters import (
    complete_call_to_ch_insertable,
    end_call_for_insert_to_ch_insertable,
    start_call_for_insert_to_ch_insertable,
    start_call_insertable_to_complete_start,
)
from weave.trace_server.clickhouse_schema import (
    ALL_CALL_INSERT_COLUMNS,
    CallEndCHInsertable,
    CallStartCHInsertable,
)
from weave.trace_server.constants import (
    COMPLETIONS_CREATE_OP_NAME,
    IMAGE_GENERATION_CREATE_OP_NAME,
)
from weave.trace_server.errors import (
    InvalidRequest,
    MissingLLMApiKeyError,
)
from weave.trace_server.ids import generate_id
from weave.trace_server.image_completion import lite_llm_image_generation
from weave.trace_server.llm_completion import (
    _build_choices_array,
    _build_completion_response,
    get_custom_provider_info,
    lite_llm_completion,
    lite_llm_completion_stream,
    resolve_and_apply_prompt,
)
from weave.trace_server.model_providers.model_providers import (
    VERTEX_PROVIDER_NAMES,
    LLMModelProviderInfo,
)
from weave.trace_server.project_version.types import WriteTarget
from weave.trace_server.secret_fetcher_context import _secret_fetcher_context

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Mixin class
# ---------------------------------------------------------------------------


class CompletionsMixin:
    """Mixin providing completions_create, completions_create_stream, and image_create."""

    def completions_create(
        self, req: tsi.CompletionsCreateReq
    ) -> tsi.CompletionsCreateRes:
        # --- Resolve prompt if provided and set messages
        prompt = getattr(req.inputs, "prompt", None)
        template_vars = getattr(req.inputs, "template_vars", None)

        # Initialize initial_messages with the original messages
        initial_messages = getattr(req.inputs, "messages", None) or []

        if prompt:
            try:
                # Use helper to resolve prompt, combine messages, and apply template vars
                combined_messages, initial_messages = resolve_and_apply_prompt(
                    prompt=prompt,
                    messages=getattr(req.inputs, "messages", None),
                    template_vars=template_vars,
                    project_id=req.project_id,
                    obj_read_func=self.obj_read,
                )
                req.inputs.messages = combined_messages

            except Exception as e:
                logger.exception("Failed to resolve prompt")
                return tsi.CompletionsCreateRes(
                    response={"error": f"Failed to resolve prompt: {e!s}"}
                )

        # Use shared setup logic
        model_info = self._model_to_provider_info_map.get(req.inputs.model)
        try:
            completion_model_info = setup_completion_model_info(
                model_info, req, self.obj_read
            )
        except Exception as e:
            return tsi.CompletionsCreateRes(response={"error": str(e)})

        model_name = completion_model_info.model_name

        # Now that we have all the fields for both cases, we can make the API call
        start_time = datetime.datetime.now()

        # Make the API call
        res = lite_llm_completion(
            api_key=completion_model_info.api_key,
            inputs=req.inputs,
            provider=completion_model_info.provider,
            base_url=completion_model_info.base_url,
            extra_headers=completion_model_info.extra_headers,
            return_type=completion_model_info.return_type,
            vertex_credentials=completion_model_info.vertex_credentials,
        )

        end_time = datetime.datetime.now()

        if not req.track_llm_call:
            return tsi.CompletionsCreateRes(response=res.response)

        write_target = self.table_routing_resolver.resolve_v2_write_target(
            req.project_id,
            self.ch_client,
        )

        req.inputs.messages = initial_messages
        call_id = generate_id()
        trace_id = req.trace_id or generate_id()
        parent_id = req.parent_id

        # Build summary with usage info if available
        summary: tsi.SummaryInsertMap = {}
        if "usage" in res.response:
            summary["usage"] = {model_name: res.response["usage"]}

        # Check for exception
        exception = res.response.get("error")

        if write_target == WriteTarget.CALLS_COMPLETE:
            # Write directly to calls_complete table
            completed = tsi.CompletedCallSchemaForInsert(
                project_id=req.project_id,
                id=call_id,
                trace_id=trace_id,
                parent_id=parent_id,
                op_name=COMPLETIONS_CREATE_OP_NAME,
                started_at=start_time,
                ended_at=end_time,
                attributes={},
                inputs={
                    **req.inputs.model_dump(
                        exclude_none=True, exclude={"vertex_credentials"}
                    )
                },
                output=res.response,
                summary=summary,
                exception=exception,
                wb_user_id=req.wb_user_id,
            )
            ch_call = complete_call_to_ch_insertable(completed)
            self._insert_call_complete(ch_call)
        else:
            # Write to call_parts/calls_merged via start/end pattern
            start = tsi.StartedCallSchemaForInsert(
                project_id=req.project_id,
                id=call_id,
                trace_id=trace_id,
                parent_id=parent_id,
                wb_user_id=req.wb_user_id,
                op_name=COMPLETIONS_CREATE_OP_NAME,
                started_at=start_time,
                inputs={
                    **req.inputs.model_dump(
                        exclude_none=True, exclude={"vertex_credentials"}
                    )
                },
                attributes={},
            )
            start_call = start_call_for_insert_to_ch_insertable(start)
            end = tsi.EndedCallSchemaForInsert(
                project_id=req.project_id,
                id=start_call.id,
                ended_at=end_time,
                output=res.response,
                summary=summary,
            )
            if exception:
                end.exception = exception
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

            self._insert_call_batch(batch_data)

        return tsi.CompletionsCreateRes(response=res.response, weave_call_id=call_id)

    # -------------------------------------------------------------------
    # Streaming variant
    # -------------------------------------------------------------------
    def completions_create_stream(
        self, req: tsi.CompletionsCreateReq
    ) -> Iterator[dict[str, Any]]:
        """Stream LLM completion chunks.

        Mirrors ``completions_create`` but with streaming enabled.  If
        ``track_llm_call`` is True we emit a call_start record immediately and
        a call_end record once the stream finishes (successfully or not).

        When req.inputs.n > 1, properly separates and tracks all choices
        within a single call's output rather than creating separate calls.
        """
        # --- Resolve prompt if provided and prepend messages
        prompt = getattr(req.inputs, "prompt", None)
        template_vars = getattr(req.inputs, "template_vars", None)

        try:
            # Use helper to resolve prompt, combine messages, and apply template vars
            combined_messages, initial_messages = resolve_and_apply_prompt(
                prompt=prompt,
                messages=getattr(req.inputs, "messages", None),
                template_vars=template_vars,
                project_id=req.project_id,
                obj_read_func=self.obj_read,
            )
        except Exception as e:
            logger.exception("Failed to resolve and apply prompt")

            # Yield error as single chunk then stop.
            def _single_error_iter(err: Exception) -> Iterator[dict[str, str]]:
                yield {"error": f"Failed to resolve and apply prompt: {err!s}"}

            return _single_error_iter(e)

        # --- Shared setup logic (copy of completions_create up to litellm call)
        model_info = self._model_to_provider_info_map.get(req.inputs.model)
        try:
            completion_model_info = setup_completion_model_info(
                model_info, req, self.obj_read
            )
        except Exception as e:
            # Yield error as single chunk then stop.
            def _single_error_iter(err: Exception) -> Iterator[dict[str, str]]:
                yield {"error": str(err)}

            return _single_error_iter(e)

        model_name = completion_model_info.model_name
        api_key = completion_model_info.api_key
        provider = completion_model_info.provider
        base_url = completion_model_info.base_url
        extra_headers = completion_model_info.extra_headers
        return_type = completion_model_info.return_type
        vertex_credentials = completion_model_info.vertex_credentials

        # Track start call if requested
        start_call: CallStartCHInsertable | None = None
        write_target: WriteTarget | None = None
        if req.track_llm_call:
            write_target = self.table_routing_resolver.resolve_v2_write_target(
                req.project_id,
                self.ch_client,
            )
            # Prepare inputs for tracking: use original messages (with template syntax)
            # and include prompt and template_vars
            tracked_inputs = req.inputs.model_dump(
                exclude_none=True, exclude={"vertex_credentials"}
            )
            tracked_inputs["model"] = model_name
            tracked_inputs["messages"] = initial_messages
            if prompt:
                tracked_inputs["prompt"] = prompt
            if template_vars:
                tracked_inputs["template_vars"] = template_vars

            start = tsi.StartedCallSchemaForInsert(
                project_id=req.project_id,
                trace_id=req.trace_id,
                parent_id=req.parent_id,
                wb_user_id=req.wb_user_id,
                op_name=COMPLETIONS_CREATE_OP_NAME,
                started_at=datetime.datetime.now(),
                inputs=tracked_inputs,
                attributes={},
            )
            start_call = start_call_for_insert_to_ch_insertable(start)
            # Insert immediately so that callers can see the call in progress
            if write_target == WriteTarget.CALLS_COMPLETE:
                ch_complete_start = start_call_insertable_to_complete_start(start_call)
                self._insert_call_complete(ch_complete_start)
            else:
                self._insert_call(start_call)

        # Set the combined messages (with template vars replaced) for LiteLLM
        req.inputs.messages = combined_messages

        # Make a copy for the API call without prompt and template_vars
        api_inputs = req.inputs.model_copy()
        if hasattr(api_inputs, "prompt"):
            api_inputs.prompt = None
        if hasattr(api_inputs, "template_vars"):
            api_inputs.template_vars = None

        # --- Build the underlying chunk iterator
        chunk_iter = lite_llm_completion_stream(
            api_key=api_key or "",
            inputs=api_inputs,
            provider=provider,
            base_url=base_url,
            extra_headers=extra_headers,
            return_type=return_type,
            vertex_credentials=vertex_credentials,
        )

        # If tracking not requested just return chunks directly
        if not req.track_llm_call or start_call is None:
            return chunk_iter

        # Otherwise, wrap the iterator with tracking
        end_call_handler: Callable[[tsi.EndedCallSchemaForInsert], None] | None = None
        if write_target == WriteTarget.CALLS_COMPLETE:
            end_call_handler = lambda end: self._update_call_end_in_calls_complete(
                tsi.EndedCallSchemaForInsertWithStartedAt(
                    **end.model_dump(),
                    started_at=start_call.started_at,
                )
            )
        return create_tracked_stream_wrapper(
            self._insert_call,
            chunk_iter,
            start_call,
            model_name,
            req.project_id,
            end_call_handler=end_call_handler,
        )

    def image_create(
        self, req: tsi.ImageGenerationCreateReq
    ) -> tsi.ImageGenerationCreateRes:
        """Create images using LLM image generation.

        Args:
            req (tsi.ImageGenerationCreateReq): The image generation request.

        Returns:
            tsi.ImageGenerationCreateRes: The image generation response.
        """
        # Validate input parameters
        if req.inputs.model is None:
            return tsi.ImageGenerationCreateRes(
                response={"error": "No model specified in request"}
            )

        if req.inputs.prompt is None:
            return tsi.ImageGenerationCreateRes(
                response={"error": "No prompt specified in request"}
            )

        # Get API key from secret fetcher
        secret_fetcher = _secret_fetcher_context.get()
        if secret_fetcher is None:
            logger.error("No secret fetcher available for image generation request")
            return tsi.ImageGenerationCreateRes(
                response={
                    "error": "Unable to access required credentials for image generation"
                }
            )

        api_key = (
            secret_fetcher.fetch("OPENAI_API_KEY")
            .get("secrets", {})
            .get("OPENAI_API_KEY")
        )

        if api_key is None:
            return tsi.ImageGenerationCreateRes(
                response={"error": "No OpenAI API key found"}
            )

        # Now that we have the API key, we can make the API call
        start_time = datetime.datetime.now()

        try:
            res = lite_llm_image_generation(
                api_key=api_key,
                inputs=req.inputs.model_dump(exclude_none=True),
                trace_server=self,
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

        # Return response directly if not tracking calls
        if req.track_llm_call is False:
            return res

        # Capture all input fields for call tracking
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
            # Log error but don't fail the response
            print(f"Error inserting call batch for image generation: {e}", flush=True)

        return tsi.ImageGenerationCreateRes(
            response=res.response, weave_call_id=start_call.id
        )


# ---------------------------------------------------------------------------
# Free helper functions
# ---------------------------------------------------------------------------


def update_metadata_from_chunk(
    chunk: dict[str, Any], aggregated_metadata: dict[str, Any]
) -> None:
    """Update aggregated metadata from a chunk."""
    metadata_fields = [
        "id",
        "created",
        "model",
        "system_fingerprint",
        "service_tier",
        "usage",
    ]

    for field in metadata_fields:
        if field in chunk and field not in aggregated_metadata:
            if field == "service_tier":
                aggregated_metadata[field] = chunk.get(field, "default")
            else:
                aggregated_metadata[field] = chunk[field]


def process_tool_call_delta(
    tool_call_delta: list, tool_calls: list[dict[str, Any]]
) -> None:
    """Process tool call delta and update tool_calls list."""
    for tool_call in tool_call_delta:
        tool_call_index = tool_call.get("index", 0)

        # Ensure we have enough tool calls in our list
        while len(tool_calls) <= tool_call_index:
            tool_calls.append(
                {
                    "id": None,
                    "type": "function",
                    "function": {"name": "", "arguments": ""},
                }
            )

        existing_tool_call = tool_calls[tool_call_index]

        # Update existing tool call fields
        if tool_call.get("id"):
            existing_tool_call["id"] = tool_call["id"]
        if tool_call.get("type"):
            existing_tool_call["type"] = tool_call["type"]

        if "function" in tool_call:
            function_data = tool_call["function"]
            if function_data.get("name"):
                existing_tool_call["function"]["name"] = function_data["name"]
            if "arguments" in function_data:
                existing_tool_call["function"]["arguments"] += function_data[
                    "arguments"
                ]


def create_tracked_stream_wrapper(
    insert_call: Callable[[CallEndCHInsertable], None],
    chunk_iter: Iterator[dict[str, Any]],
    start_call: CallStartCHInsertable,
    model_name: str,
    project_id: str,
    end_call_handler: Callable[[tsi.EndedCallSchemaForInsert], None] | None = None,
) -> Iterator[dict[str, Any]]:
    """Create a wrapper that tracks streaming completion and emits call records."""

    def _stream_wrapper() -> Iterator[dict[str, Any]]:
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
                update_metadata_from_chunk(chunk, aggregated_metadata)

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
                                process_tool_call_delta(
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
            if end_call_handler is not None:
                end_call_handler(end)
            else:
                end_call_ch = end_call_for_insert_to_ch_insertable(end)
                insert_call(end_call_ch)

    return _stream_wrapper()


@dataclasses.dataclass(frozen=True)
class CompletionModelInfo:
    model_name: str
    api_key: str | None
    provider: str
    base_url: str | None
    extra_headers: dict[str, str]
    return_type: str | None
    vertex_credentials: str | None = None


def setup_completion_model_info(
    model_info: LLMModelProviderInfo | None,
    req: tsi.CompletionsCreateReq,
    obj_read: Callable[[tsi.ObjReadReq], tsi.ObjReadRes],
) -> CompletionModelInfo:
    """Extract model setup logic shared between completions_create and completions_create_stream.

    Returns:
        CompletionModelInfo containing model/provider/credential config.

    Note: api_key can be None for bedrock providers (AWS credentials) or vertex_ai
    when vertex_credentials is provided.
    """
    model_name = req.inputs.model
    api_key: str | None = None
    provider: str = "openai"  # Default provider
    base_url: str | None = None
    extra_headers: dict[str, str] = {}
    return_type: str | None = None
    vertex_credentials: str | None = getattr(req.inputs, "vertex_credentials", None)

    # Check for explicit custom provider prefix
    is_explicit_custom = model_name.startswith("custom::")

    is_coreweave = (
        model_info and model_info.get("litellm_provider") == "coreweave"
    ) or model_name.startswith("coreweave/")
    if is_coreweave:
        # See https://docs.litellm.ai/docs/providers/openai_compatible
        # but ignore the bit about omitting the /v1 because it is actually necessary
        req.inputs.model = "openai/" + model_name.removeprefix("coreweave/")
        provider = "custom"
        base_url = wf_env.inference_service_base_url()
        # The API key should have been passed in as an extra header.
        if req.inputs.extra_headers:
            api_key = req.inputs.extra_headers.pop("api_key", None)
            extra_headers = req.inputs.extra_headers
            req.inputs.extra_headers = None
        return_type = "openai"
        return CompletionModelInfo(
            model_name=model_name,
            api_key=api_key,
            provider=provider,
            base_url=base_url,
            extra_headers=extra_headers,
            return_type=return_type,
            vertex_credentials=None,
        )
    elif is_explicit_custom:
        # Custom provider path - model_name format: custom::<provider>::<model>
        # Parse provider and model names, create sanitized object_id for lookup
        name_part = model_name.replace("custom::", "")

        if "::" in name_part:
            # Format: custom::<provider>::<model>
            provider_name, model_name_part = name_part.split("::", 1)

            # Create sanitized object_id to match what was created during provider setup

            sanitized_provider = sanitize_name_for_object_id(provider_name)
            sanitized_model = sanitize_name_for_object_id(model_name_part)
            sanitized_object_id = f"{sanitized_provider}-{sanitized_model}"
        else:
            # Fallback: assume it's already in object_id format
            # Extract names from object_id (this is a fallback case)
            parts = name_part.split("-", 1) if "-" in name_part else [name_part, ""]
            provider_name = parts[0]  # May be sanitized
            model_name_part = parts[1] if len(parts) > 1 else ""
            sanitized_provider = provider_name  # Already sanitized
            sanitized_object_id = name_part

        custom_provider_info = get_custom_provider_info(
            project_id=req.project_id,
            provider_name=sanitized_provider,
            model_name=sanitized_object_id,
            obj_read_func=obj_read,
        )

        base_url = custom_provider_info.base_url
        final_model_name = custom_provider_info.actual_model_name
        provider_model_name = (
            f"{provider_name}/{final_model_name}"
            if "::" in name_part
            else final_model_name
        )

        # prefix the model name with "ollama/" if it is an ollama model else with openai/
        req.inputs.model = (
            "ollama/" + final_model_name
            if "ollama" in provider_name.lower()
            else "openai/" + final_model_name
        )

        return CompletionModelInfo(
            model_name=provider_model_name,
            api_key=custom_provider_info.api_key,
            provider="custom",
            base_url=base_url,
            extra_headers=custom_provider_info.extra_headers,
            return_type=custom_provider_info.return_type,
            vertex_credentials=None,
        )
    elif model_info:
        secret_name = model_info.get("api_key_name")
        if not secret_name:
            raise InvalidRequest(f"No secret name found for model {model_name}")

        secret_fetcher = _secret_fetcher_context.get()
        if not secret_fetcher:
            raise InvalidRequest(
                f"No secret fetcher found, cannot fetch API key for model {model_name}"
            )

        api_key = secret_fetcher.fetch(secret_name).get("secrets", {}).get(secret_name)
        provider = model_info.get("litellm_provider", "openai")
        is_vertex_provider = provider in VERTEX_PROVIDER_NAMES
        if is_vertex_provider and vertex_credentials:
            api_key = None  # Use vertex_credentials instead
        credentials_satisfied = is_vertex_provider and vertex_credentials
        if (
            not api_key
            and provider not in {"bedrock", "bedrock_converse"}
            and not credentials_satisfied
        ):
            raise MissingLLMApiKeyError(
                f"No API key {secret_name} found for model {model_name}",
                api_key_name=secret_name,
            )

    return CompletionModelInfo(
        model_name=model_name,
        api_key=api_key,
        provider=provider,
        base_url=base_url,
        extra_headers=extra_headers,
        return_type=return_type,
        vertex_credentials=vertex_credentials,
    )


def sanitize_name_for_object_id(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", name)
