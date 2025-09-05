from typing import Optional, Union, cast, Callable, TypeVar, Type, Any
from pydantic import BaseModel, Field
from audio_buffer import AudioBufferManager
from weave.integrations.openai_realtime import models
from weave.integrations.openai_realtime.encoding import pcm_to_wav
from weave.type_wrappers.Content import Content
from weave.integrations.openai_realtime.state_manager import StateStore, StoredItem
from weave.trace.weave_client import Call

from weave.integrations.openai_realtime import models
import logging

from weave.integrations.openai_realtime.state_manager import StateStore
logger = logging.getLogger(__name__)

DeltaMessage = Union[
    models.ResponseTextDeltaMessage,
    models.ResponseAudioDeltaMessage,
    models.ResponseAudioTranscriptDeltaMessage,
    models.ResponseFunctionCallArgumentsDeltaMessage
]
# def update_response(response: models.Response, msg: DeltaMessage):
#     if isinstance(msg, models.ResponseFunctionCallArgumentsDeltaMessage):
#
#     if msg.output_index >= len(response.output):
#         response.output.append(
class ResponseItemState:
    create_params: Optional[models.ResponseCreateParams]
    response: Optional[models.Response]

# Each Item can have a content array
# User Items have only content
# Response Items have output array and optionally content for messages

class UserItem:
    id: models.ItemID
    input_text: Optional[str]
    input_audio: Optional[bytearray]
    transcript: Optional[str]
class StateExporter(StateStore):
    conversation_calls: dict[models.ConversationID, Call] = Field(default_factory=dict)

    committed_item_ids: set[models.ItemID] = Field(default_factory=set)

    input_buffer: AudioBufferManager = Field(default_factory=AudioBufferManager)
    output_buffer: AudioBufferManager = Field(default_factory=AudioBufferManager)

    response_calls: dict[models.ResponseID, Call] = Field(default_factory=dict)
    responses: dict[models.ResponseID, models.Response] = Field(default_factory=dict)

    pending_response: Optional[models.Response] = None
    pending_create_params: Optional[models.ResponseCreateParams] = None


    def __init__(self):
        super().__init__()

    # def handle_conversation_item_created(msg: models.ItemCreatedMessage) -> None:
    #     self.items[msg.item.id]
    # def handle_response_output_audio_transcript_delta(self, msg: models.ResponseAudioTranscriptDeltaMessage) -> None:
    # def handle_response_output_audio_delta(self, msg: models.ResponseAudioDeltaMessage) -> None:
    # def handle_response_output_text_delta(self, msg: models.ResponseTextDeltaMessage) -> None:
    # def handle_response_create(self, msg: models.ResponseCreateMessage) -> None:
    #     self.pending_create_params = msg

    def apply_input_audio_cleared(self, _msg: models.InputAudioBufferClearedMessage) -> None:
        self.input_audio_buffer.clear()

    def apply_input_audio_committed(self, msg: models.InputAudioBufferCommittedMessage) -> None:
        # Track commits against items for turn completeness checks
        self.committed_item_ids.add(msg.item_id)

    def handle_response_created(self, msg: models.ResponseCreatedMessage) -> None:
        self.pending_response = msg.response

    def handle_input_audio_append(self, msg: models.InputAudioBufferAppendMessage) -> None:
        self.input_audio_buffer.append_base64(msg.audio)

    def handle_response_audio_delta(self, msg: models.ResponseAudioDeltaMessage) -> None:
        self.output_buffer.append_base64(msg.delta)


    # def handle_response_output_item_added(self, msg: models.ResponseOutputItemAddedMessage):
    #     pending_response = self.pending_response
    #
    #     if not self.pending_response:
    #         logger.error("Tried to add item to response that does not exist")
    #         return
    #
    #     if msg.output_index > len(self.pending_response.output) - 1:
    #         self.pending_response.response.output.append(msg.item)
    #
    #     self.pending_response.response.output
    # def handle_conversation_item_created(self, msg: models.ItemCreatedMessage) -> None:
    #     if 
    #     if msg.item.type == "function_call":


    def handle_response_done(self, msg: models.ResponseDoneMessage) -> None:
        from weave.trace.context.weave_client_context import require_weave_client
        pending_create_params = self.pending_create_params
        pending_response = self.pending_response
        if pending_response is None:
            logger.error("Attempted to finish response that was never created")
            return
        inputs = pending_response.model_dump()
        if pending_create_params is not None:
            inputs.update(pending_create_params.model_dump())
            self.pending_create_params = None

        client = require_weave_client()

        resp_id = msg.response.id
        conv_id = msg.response.conversation_id
        input_data = {}

        conv_call = None
        if conv_id:
            conv_call = self.conversation_calls.get(conv_id)
            if not conv_call:
                conv_call = client.create_call(op=conv_id, inputs={})
                self.conversation_calls[conv_id] = conv_call
        if self.session:
            input_data['session'] = self.session


        call = client.create_call(resp_id, inputs=inputs, parent=conv_call)

        output_dict = msg.response.model_dump()
        for output_idx, output in enumerate(msg.response.output):
            if output.type == "message":
                item_id = output.id
                for content_idx, content in enumerate(output.content):
                    content_dict = content.model_dump()
                    if content.type == "audio":
                        content_dict = output.content[content_idx].model_dump()
                        audio_bytes = self.resp_audio_bytes[(resp_id, item_id, content_idx)]
                        if not audio_bytes:
                            logger.error("failed to fetch audio bytes")
                            continue
                        content_dict["audio"] = Content.from_bytes(pcm_to_wav(bytes(audio_bytes)), extension=".wav")
                    output_dict["output"][output_idx]["content"][content_idx] = content_dict
        client.finish_call(call, output=output_dict)


        # content.append(self.resp_audio_transcripts.get
        # client.finish_call(call, )


    # def _build_input_payload(self, response_id: models.ResponseID) -> dict[str, object]:

#     def _build_output_payload(self, resp_id: models.ResponseID) -> dict[str, object]:
#         """Build Output payload matching the requested schema."""
#         resp = self.get_response(resp_id)
#         sess = self.session
# # Build assistant message by formatting the first assistant ResponseMessageItem
#         assistant_message: dict[str, object] = {"role": "assistant", "content": []}
#         for it in resp.output:
#             if isinstance(it, models.ResponseMessageItem) and getattr(it, "role", None) == "assistant":
#                 fmt = self._format_item(it, response_id=resp.id)
#                 if fmt is not None:
#                     assistant_message = fmt
#                 break
#
#         usage_obj: Optional[dict[str, object]] = None
#         if resp.usage is not None:
#             u = resp.usage
#             usage_obj = {
#                 "total_tokens": u.total_tokens,
#                 "input_tokens": u.input_tokens,
#                 "output_tokens": u.output_tokens,
#                 "input_token_details": (u.input_token_details.model_dump() if u.input_token_details else None),
#                 "output_token_details": (u.output_token_details.model_dump() if u.output_token_details else None),
#             }
#
#         return {
#             "id": resp.id,
#             "model": (sess.model if sess else None) or "gpt-4o-realtime",
#             "status": resp.status,
#             "status_details": resp.status_details,
#             "object": "chat.completion",
#             "usage": usage_obj,
#             "choices": [
#                 {
#                     "index": 0,
#                     "message": assistant_message,
#                 }
#             ],
#         }
#
#     def _on_client_complete(self, _rec: TurnRecord) -> None:
#         logger.debug("_on_client_complete: inputs complete for response")
#         # Once inputs for a turn are completed, create a weave call for this turn
#         # using the same formatted inputs as the export function.
#         rec = _rec
#         if not rec.response_id:
#             logger.warning("_on_client_complete: missing response_id; cannot create call")
#             return
#         # Avoid creating duplicate calls
#         if rec.response_id in self._weave_calls:
#             logger.debug("_on_client_complete: call already exists for response_id=%s", rec.response_id)
#             return
#         # Ensure we have a session id to bind the thread context
#         sess = self.state.session
#         if not sess:
#             logger.warning("_on_client_complete: no session; skipping trace creation")
#             return
#         try:
#             import weave  # local import to avoid hard dependency at module import time
#             # Acquire client from context within a thread tied to the session id
#             with weave.thread(sess.id):
#                 from weave.trace.context.weave_client_context import get_weave_client
#                 client = get_weave_client()
#                 if not client:
#                     logger.warning("_on_client_complete: no weave client in context; skipping")
#                     return
#                 # Build inputs matching export formatting
#                 inputs = self._build_inputs_payload(rec)
#                 # Use the op name conversation_turn, like sessions.py
#                 call = client.create_call(op="conversation_turn", inputs=inputs)
#                 self._weave_calls[rec.response_id] = call
#                 # If the response already finished, finish immediately here
#                 if rec.response_done:
#                     outputs = self._build_output_payload(rec)
#                     client.finish_call(call, output=outputs)
#         except Exception as e:
#             logger.error(f"Error submitting trace in _on_client_complete - {e}")
#             # Never let tracing interfere with core flow
#             return
#
#     def _build_inputs_payload(self, rec: TurnRecord) -> dict[str, object]:
#         """Build Inputs payload matching the requested schema."""
#         sess = self.state.session
#         item_ids = self._collect_input_item_ids(rec)
#
#         # Helper: response_id for an assistant message item
#         def _response_id_for_item(iid: models.ItemID) -> Optional[models.ResponseID]:
#             return self._get_response_for_item(iid)
#
#         messages: list[dict[str, object]] = []
#
#         for iid in item_ids:
#             it = self.state.items.get(iid)
#             if it is None:
#                 continue
#             rid = _response_id_for_item(iid)
#             formatted = self._format_item(it, response_id=rid)
#             if formatted is None:
#                 continue
#             role = formatted.get("role")
#             if role == "system":
#                 # Preserve original behavior: collapse to a single string
#                 parts_obj = formatted.get("content")
#                 texts: list[str] = []
#                 if isinstance(parts_obj, list):
#                     for p in parts_obj:
#                         if isinstance(p, dict):
#                             t = p.get("text")
#                             if p.get("type") == "text" and isinstance(t, str) and t:
#                                 texts.append(t)
#                 messages.append({"role": "system", "content": "\n".join(texts) if texts else ""})
#             elif role == "assistant" and formatted.get("tool_calls") is None:
#                 # Preserve original behavior: only include audio parts for assistant context
#                 parts_obj = formatted.get("content")
#                 audio_parts: Optional[list[dict[str, object]]] = None
#                 if isinstance(parts_obj, list):
#                     audio_list = [p for p in parts_obj if isinstance(p, dict) and p.get("type") == "audio"]
#                     audio_parts = audio_list or None
#                 messages.append({
#                     "role": "assistant",
#                     "content": audio_parts or None,
#                     "refusal": None,
#                     "annotations": [],
#                     "function_call": None,
#                     "tool_calls": None,
#                 })
#             else:
#                 messages.append(formatted)
#
#         result = {}
#         if sess:
#             result = sess.model_dump()
#         result["messages"] = messages
#         return result
#
#
    def _format_item(
        self,
        item: object,
        *,
        response_id: Optional[models.ResponseID] = None,
    ) -> Optional[dict[str, object]]:
        """Format any conversation or response item into a single message-like object.

        - Message items -> {role, content: [mapped parts]}
        - Function call -> assistant tool_calls envelope
        - Function call output -> tool role message
        """
        # The function call instance check fails so just use this
        if getattr(item, "type", None) == "function_call":
             return {
                 "role": "assistant",
                 "content": None,
                 "refusal": None,
                 "annotations": [],
                 "function_call": None,
                 "tool_calls": [
                     {
                         "id": getattr(item, "call_id", None),
                         "type": "function",
                         "function": {
                             "name": getattr(item, "name", None),
                             "arguments": getattr(item, "arguments", None),
                         },
                     }
                 ],
             }

        if getattr(item, "type", None) == "function_call_output":
            call_id = getattr(item, "call_id", None)
            name = None
            for other in self.items.values():
                if getattr(other, "type", None) == "function_call" and getattr(other, "call_id", None) == call_id:
                    name = getattr(other, "name", None)
                    break

                return {
                    "role": "tool",
                    "content": getattr(item, "output", None),
                    "tool_call_id": call_id,
                    "name": name,
                }
        # System message
        if isinstance(item, (models.ClientSystemMessageItem, models.ServerSystemMessageItem)):
            parts: list[dict[str, object]] = []
            for idx, p in enumerate(getattr(item, "content", []) or []):
                out = self._format_content_part(p, item_id=getattr(item, "id", None), content_index=idx)
                if out is not None:
                    parts.append(out)
            return {"role": "system", "content": parts}

        # User message
        if isinstance(item, (models.ClientUserMessageItem, models.ServerUserMessageItem)):
            parts: list[dict[str, object]] = []
            iid = getattr(item, "id", None)
            for idx, p in enumerate(getattr(item, "content", []) or []):
                out = self._format_content_part(p, item_id=iid, content_index=idx)
                if out is not None:
                    parts.append(out)
            return {"role": "user", "content": parts}

        # Assistant message (may appear as server message or response item)
        if isinstance(item, (models.ClientAssistantMessageItem, models.ServerAssistantMessageItem, models.ResponseMessageItem)):
            parts: list[dict[str, object]] = []
            iid = getattr(item, "id", None)
            for idx, p in enumerate(getattr(item, "content", []) or []):
                out = self._format_content_part(p, item_id=iid, response_id=response_id, content_index=idx)
                if out is not None:
                    parts.append(out)
            return {
                "role": "assistant",
                "content": parts,
                "refusal": None,
                "annotations": [],
                "function_call": None,
                "tool_calls": None,
            }

        return None


    # def _on_response_complete(self, rec: TurnRecord) -> None:
    #     if not rec.response_id:
    #         logger.warning("_on_response_complete: missing response_id; cannot finish call")
    #         return
    #     resp = self.state.get_response(rec.response_id)
    #     if not resp:
    #         logger.warning("_on_response_complete: response missing")
    #         return
    #
    #     # Skip exports for non-message-only responses (e.g., pure function_call turns)
    #     has_assistant_message = any(isinstance(it, models.ResponseMessageItem) and it.role == "assistant" for it in resp.output)
    #     if not has_assistant_message:
    #         logger.debug("_on_response_complete: no assistant message in output; skipping export for response_id=%s", rec.response_id)
    #         return
    #
    #     # Export turn payload if configured
    #     # Finish the weave call for this response. If the call does not exist yet
    #     # but inputs are already complete, create it here and immediately finish.
    #     sess = self.state.session
    #     if not sess:
    #         logger.warning("_on_response_complete: no session; cannot create/finish call for response_id=%s", rec.response_id)
    #         return
    #     call = self._weave_calls.get(rec.response_id)
    #     try:
    #         import weave
    #         with weave.thread(sess.id):
    #             from weave.trace.context.weave_client_context import get_weave_client
    #             client = get_weave_client()
    #             if not client:
    #                 logger.warning("_on_response_complete: no weave client in context; skipping finish for response_id=%s", rec.response_id)
    #                 return
    #             # Create call on-demand if missing but inputs are complete
    #             if call is None and rec.inputs_complete:
    #                 inputs = self._build_inputs_payload(rec)
    #                 try:
    #                     from sessions import conversation_turn  # type: ignore
    #                 except Exception as e:
    #                     logger.warning("_on_response_complete: failed to import conversation_turn op: %s", e)
    #                     return
    #                 call = client.create_call(op=conversation_turn, inputs=inputs)
    #                 self._weave_calls[rec.response_id] = call
    #             if call is None:
    #                 logger.warning("_on_response_complete: call still None; cannot finish for response_id=%s", rec.response_id)
    #                 return
    #             outputs = self._build_output_payload(rec)
    #             client.finish_call(call, output=outputs)
    #     except Exception as e:
    #         logger.error(f"Error submitting call in _on_response_complete - {e}")
    #         return
    #
    # def _handle_error(self, msg: models.ErrorMessage) -> None:
    #     # Let the client handle api errors
    #     pass

    def _handle_rate_limits_updated(self, msg: models.RateLimitsUpdatedMessage) -> None:
        # Log rate limits for informational purposes
        logger.debug("Rate limits updated: %s", msg.rate_limits)


# Formatting helpers
    def _format_content_part(
        self,
        part: object,
        *,
        item_id: Optional[models.ItemID] = None,
        response_id: Optional[models.ResponseID] = None,
        content_index: Optional[int] = None,
    ) -> Optional[dict[str, object]]:
        """Normalize an item content part to a stable schema.

        Returns a dict shaped as one of:
        - {"type": "text", "text": str}
        - {"type": "audio", "audio": {"transcript": str, "data": Content|None, "format": str}}

        Unknown/unsupported parts return None.
        """
        ptype = getattr(part, "type", None)

        # Text-like parts
        if ptype in ("input_text", "text"):
            text = getattr(part, "text", None)
            if text is None:
                return None
            return {"type": "text", "text": text}

        # User input audio
        if ptype == "input_audio":
            # Prefer the transcript stored on the part, fall back to accumulated transcripts
            transcript = getattr(part, "transcript", None)
            if transcript is None and item_id is not None:
                # attempt to reconstruct from state if present
                # We don't know content_index for user items reliably here, so best-effort only
                pass
            # Encode the PCM slice for the full spoken span of this item if available
            data: Optional[Content] = None
            if item_id is not None:
                try:
                    seg = self.get_audio_segment(item_id)
                    if seg:
                        data = Content.from_bytes(pcm_to_wav(seg), extension=".wav")
                except Exception:
                    data = None
            return {
                "type": "audio",
                "audio": {
                    "transcript": transcript or "",
                    "data": data,
                    "format": "audio/wav",
                },
            }

        # Assistant output audio
        if ptype == "audio":
            transcript = getattr(part, "transcript", None) or ""
            data: Optional[Content] = None
            if response_id is not None and item_id is not None and content_index is not None:
                try:
                    buf = self.resp_audio_bytes.get((response_id, item_id, content_index))
                    if buf:
                        data = Content.from_bytes(pcm_to_wav(bytes(buf)), extension=".wav")
                except Exception:
                    data = None
            return {
                "type": "audio",
                "audio": {
                    "transcript": transcript,
                    "data": data,
                    "format": 'audio/wav',
                },
            }

        return None
