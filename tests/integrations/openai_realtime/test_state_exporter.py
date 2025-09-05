import base64
import time
from types import ModuleType

from weave.integrations.openai_realtime import models
from weave.integrations.openai_realtime.state_exporter import StateExporter


class DummyCall:
    def __init__(self, op):
        self.op = op


class DummyWeaveClient:
    def __init__(self):
        self.created: list[str] = []
        self.finished: list[str] = []

    def create_call(self, op, inputs=None, parent=None):
        self.created.append(op)
        return DummyCall(op)

    def finish_call(self, call, output=None):
        # call.op is the response id
        self.finished.append(call.op)


def install_require_weave_client(monkeypatch, client: DummyWeaveClient):
    # Ensure the in-function import gets our stub
    mod = ModuleType("weave.trace.context.weave_client_context")
    mod.require_weave_client = lambda: client
    monkeypatch.setitem(
        __import__("sys").modules, "weave.trace.context.weave_client_context", mod
    )


def make_session_text():
    return models.Session(
        id="sess_1",
        model="m",
        modalities={"text"},
        instructions="",
        voice="alloy",
        input_audio_format="pcm16",
        output_audio_format="pcm16",
        input_audio_transcription=None,
        turn_detection=models.NoTurnDetection(),
        tools=[],
        tool_choice="auto",
        temperature=0.6,
        max_response_output_tokens=None,
    )


def test_response_audio_delta_and_done(monkeypatch):
    exp = StateExporter()

    # Append two deltas and then done
    payload = base64.b64encode(b"\x01\x02\x03\x04").decode()
    rid = "resp_1"
    item_id = "item_1"

    exp.handle_response_audio_delta(
        models.ResponseAudioDeltaMessage(
            type="response.audio.delta",
            event_id="event_1",
            response_id=rid,
            item_id=item_id,
            output_index=0,
            content_index=0,
            delta=payload,
        )
    )
    exp.handle_response_audio_delta(
        models.ResponseAudioDeltaMessage(
            type="response.audio.delta",
            event_id="event_2",
            response_id=rid,
            item_id=item_id,
            output_index=0,
            content_index=0,
            delta=payload,
        )
    )
    # Finish audio
    exp.handle_response_audio_done(
        models.ResponseAudioDoneMessage(
            type="response.audio.done",
            event_id="event_3",
            response_id=rid,
            item_id=item_id,
            output_index=0,
            content_index=0,
        )
    )
    # Buffer cleared and audio stored
    assert item_id in exp.response_audio
    assert len(exp.output_buffer.buffer) == 0


def test_fifo_completion_orders_responses_by_arrival(monkeypatch):
    client = DummyWeaveClient()
    install_require_weave_client(monkeypatch, client)

    # Stub Content.from_bytes to simplify assertions
    import weave.integrations.openai_realtime.state_exporter as se

    monkeypatch.setattr(
        se.Content,
        "from_bytes",
        staticmethod(lambda b, extension: {"len": len(b), "ext": extension}),
    )

    exp = StateExporter()
    # Active session with text modality -> transcripts gating applies
    exp.handle_session_updated(
        models.SessionUpdatedMessage(
            type="session.updated", event_id="event_0", session=make_session_text()
        )
    )

    # User items
    user1 = models.ServerUserMessageItem(
        id="item_u1",
        object="realtime.item",
        role="user",
        content=[
            models.InputAudioContentPart(type="input_audio", audio="", transcript=None)
        ],
    )
    user2 = models.ServerUserMessageItem(
        id="item_u2",
        object="realtime.item",
        role="user",
        content=[
            models.InputAudioContentPart(type="input_audio", audio="", transcript=None)
        ],
    )
    exp.items[user1.id] = user1
    exp.items[user2.id] = user2

    # Assistant outputs
    out1 = models.ResponseMessageItem(
        id="item_a1",
        status="completed",
        role="assistant",
        content=[models.ResponseItemAudioContentPart(type="audio")],
    )
    out2 = models.ResponseMessageItem(
        id="item_a2",
        status="completed",
        role="assistant",
        content=[models.ResponseItemAudioContentPart(type="audio")],
    )

    # Link outputs to previous user items for input resolution
    exp.prev_by_item[out1.id] = user1.id
    exp.prev_by_item[out2.id] = user2.id

    # Mark that response audio was produced (so export doesn't fail looking up bytes)
    exp.response_audio[out1.id] = b"\x00\x01"
    exp.response_audio[out2.id] = b"\x02\x03"

    # Create responses
    resp1 = models.Response(
        id="resp_1",
        status="completed",
        status_details=None,
        output=[out1],
        usage=None,
        conversation_id=None,
    )
    resp2 = models.Response(
        id="resp_2",
        status="completed",
        status_details=None,
        output=[out2],
        usage=None,
        conversation_id=None,
    )

    # Signal created (sets pending_response, used for context)
    exp.handle_response_created(
        models.ResponseCreatedMessage(
            type="response.created", event_id="event_1", response=resp1
        )
    )
    # Done arrives for resp1 first, but transcript for user1 not ready yet
    exp.handle_response_done(
        models.ResponseDoneMessage(
            type="response.done", event_id="event_2", response=resp1
        )
    )

    # Now second response created and done; user2 transcript is ready immediately
    exp.handle_response_created(
        models.ResponseCreatedMessage(
            type="response.created", event_id="event_3", response=resp2
        )
    )
    exp.transcript_completed.add(user2.id)
    exp.handle_response_done(
        models.ResponseDoneMessage(
            type="response.done", event_id="event_4", response=resp2
        )
    )

    # Allow timers to run once
    time.sleep(0.12)
    # Even though resp2 was ready, nothing should finish yet due to FIFO head (resp1) not ready
    assert client.finished == []

    # Complete transcript for user1; head should finish, then resp2 should follow
    exp.handle_item_input_audio_transcription_completed(
        models.ItemInputAudioTranscriptionCompletedMessage(
            type="conversation.item.input_audio_transcription.completed",
            event_id="event_5",
            item_id=user1.id,
            content_index=0,
            transcript="ok",
        )
    )

    # Allow timer to fire
    time.sleep(0.12)
    assert client.finished == ["resp_1", "resp_2"]


def test_transcripts_not_required_when_text_modality_absent(monkeypatch):
    client = DummyWeaveClient()
    install_require_weave_client(monkeypatch, client)
    import weave.integrations.openai_realtime.state_exporter as se

    monkeypatch.setattr(
        se.Content, "from_bytes", staticmethod(lambda b, extension: {"ok": True})
    )

    exp = StateExporter()
    # Session without text modality -> no gating
    session = models.Session(
        id="sess_2",
        model="m",
        modalities={"audio"},
        instructions="",
        voice="alloy",
        input_audio_format="pcm16",
        output_audio_format="pcm16",
        input_audio_transcription=None,
        turn_detection=models.NoTurnDetection(),
        tools=[],
        tool_choice="auto",
        temperature=0.6,
        max_response_output_tokens=None,
    )
    exp.handle_session_updated(
        models.SessionUpdatedMessage(
            type="session.updated", event_id="event_0", session=session
        )
    )

    out = models.ResponseMessageItem(
        id="item_a",
        status="completed",
        role="assistant",
        content=[models.ResponseItemTextContentPart(type="text", text="hi")],
    )
    resp = models.Response(
        id="resp_x",
        status="completed",
        status_details=None,
        output=[out],
        usage=None,
        conversation_id=None,
    )
    exp.handle_response_created(
        models.ResponseCreatedMessage(
            type="response.created", event_id="event_1", response=resp
        )
    )
    exp.handle_response_done(
        models.ResponseDoneMessage(
            type="response.done", event_id="event_2", response=resp
        )
    )

    # Should finish quickly without waiting for any transcripts
    time.sleep(0.08)
    assert client.finished == ["resp_x"]
