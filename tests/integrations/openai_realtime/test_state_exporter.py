import base64
import time

from weave.integrations.openai_realtime.state_exporter import StateExporter


class DummyWeaveClient:
    def __init__(self):
        self.created: list[str] = []
        self.finished: list[str] = []
        self.thread_ids: list[str | None] = []

    def create_call(self, op, inputs=None, parent=None):
        from weave.trace.call import Call
        from weave.trace.context.call_context import get_thread_id

        self.created.append(op)
        self.thread_ids.append(get_thread_id())
        return Call(
            _op_name=op,
            trace_id="trace",
            project_id="proj",
            parent_id=None,
            inputs=inputs or {},
        )

    def finish_call(self, call, output=None):
        # Track by response ID from output dict for meaningful assertions
        rid = output.get("id") if isinstance(output, dict) else None
        self.finished.append(rid or call._op_name)


def install_require_weave_client(monkeypatch, client: DummyWeaveClient):
    import weave.integrations.openai_realtime.state_exporter as se
    import weave.trace.context.weave_client_context as wcc

    # Patch module-level import in state_exporter (used by SessionSpan methods)
    monkeypatch.setattr(se, "require_weave_client", lambda: client)
    # Patch the original module (used by late/local imports in _handle_response_done_inner)
    monkeypatch.setattr(wcc, "require_weave_client", lambda: client)


def make_session_text():
    return {
        "id": "sess_1",
        "model": "m",
        "modalities": ["text"],
        "instructions": "",
        "voice": "alloy",
        "input_audio_format": "pcm16",
        "output_audio_format": "pcm16",
        "input_audio_transcription": None,
        "turn_detection": {"type": "none"},
        "tools": [],
        "tool_choice": "auto",
        "temperature": 0.6,
        "max_response_output_tokens": None,
    }


def make_user_item(item_id):
    return {
        "id": item_id,
        "type": "message",
        "object": "realtime.item",
        "role": "user",
        "content": [{"type": "input_audio", "audio": "", "transcript": None}],
    }


def make_assistant_output(item_id, content=None):
    return {
        "id": item_id,
        "type": "message",
        "status": "completed",
        "role": "assistant",
        "content": content or [{"type": "audio"}],
    }


def make_response(resp_id, output):
    return {
        "id": resp_id,
        "status": "completed",
        "status_details": None,
        "output": [output],
        "usage": None,
        "conversation_id": None,
    }


def test_response_audio_delta_and_done():
    exp = StateExporter()

    # Append two deltas and then done
    payload = base64.b64encode(b"\x01\x02\x03\x04").decode()
    rid = "resp_1"
    item_id = "item_1"

    exp.handle_response_audio_delta(
        {
            "type": "response.audio.delta",
            "event_id": "event_1",
            "response_id": rid,
            "item_id": item_id,
            "output_index": 0,
            "content_index": 0,
            "delta": payload,
        }
    )
    exp.handle_response_audio_delta(
        {
            "type": "response.audio.delta",
            "event_id": "event_2",
            "response_id": rid,
            "item_id": item_id,
            "output_index": 0,
            "content_index": 0,
            "delta": payload,
        }
    )
    # Finish audio
    exp.handle_response_audio_done(
        {
            "type": "response.audio.done",
            "event_id": "event_3",
            "response_id": rid,
            "item_id": item_id,
            "output_index": 0,
            "content_index": 0,
        }
    )
    # Buffer cleared and audio stored
    assert item_id in exp.response_audio
    assert len(exp.audio_output_buffer.buffer) == 0


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
        {
            "type": "session.updated",
            "event_id": "event_0",
            "session": make_session_text(),
        }
    )

    # User items
    user1 = make_user_item("item_u1")
    user2 = make_user_item("item_u2")
    exp.items[user1["id"]] = user1
    exp.items[user2["id"]] = user2

    # Assistant outputs
    out1 = make_assistant_output("item_a1")
    out2 = make_assistant_output("item_a2")

    # Link outputs to previous user items for input resolution
    exp.prev_by_item[out1["id"]] = user1["id"]
    exp.prev_by_item[out2["id"]] = user2["id"]

    # Mark that response audio was produced (so export doesn't fail looking up bytes)
    exp.response_audio[out1["id"]] = b"\x00\x01"
    exp.response_audio[out2["id"]] = b"\x02\x03"

    # Create responses
    resp1 = make_response("resp_1", out1)
    resp2 = make_response("resp_2", out2)

    # Signal created (sets pending_response, used for context)
    exp.handle_response_created(
        {"type": "response.created", "event_id": "event_1", "response": resp1}
    )
    # Done arrives for resp1 first, but transcript for user1 not ready yet
    exp.handle_response_done(
        {"type": "response.done", "event_id": "event_2", "response": resp1}
    )

    # Now second response created and done; user2 transcript is ready immediately
    exp.handle_response_created(
        {"type": "response.created", "event_id": "event_3", "response": resp2}
    )
    exp.transcript_completed.add(user2["id"])
    exp.handle_response_done(
        {"type": "response.done", "event_id": "event_4", "response": resp2}
    )

    # Allow timers to run once
    time.sleep(0.12)
    # Even though resp2 was ready, nothing should finish yet due to FIFO head (resp1) not ready
    assert client.finished == []

    # Complete transcript for user1; head should finish, then resp2 should follow
    exp.handle_item_input_audio_transcription_completed(
        {
            "type": "conversation.item.input_audio_transcription.completed",
            "event_id": "event_5",
            "item_id": user1["id"],
            "content_index": 0,
            "transcript": "ok",
        }
    )

    # Allow timer to fire
    time.sleep(0.12)
    assert client.finished == ["resp_1", "resp_2"]


def test_response_calls_have_thread_id_set_to_conversation_id(monkeypatch):
    """Each realtime.response call should be created with thread_id = conversation_id."""
    client = DummyWeaveClient()
    install_require_weave_client(monkeypatch, client)
    import weave.integrations.openai_realtime.state_exporter as se

    monkeypatch.setattr(
        se.Content, "from_bytes", staticmethod(lambda b, extension: {"ok": True})
    )

    exp = StateExporter()
    session = {
        "id": "sess_1",
        "model": "m",
        "modalities": ["audio"],
        "instructions": "",
        "voice": "alloy",
        "input_audio_format": "pcm16",
        "output_audio_format": "pcm16",
        "input_audio_transcription": None,
        "turn_detection": {"type": "none"},
        "tools": [],
        "tool_choice": "auto",
        "temperature": 0.6,
        "max_response_output_tokens": None,
    }
    exp.handle_session_updated(
        {"type": "session.updated", "event_id": "event_0", "session": session}
    )

    conv_id = "conv_abc123"
    out = make_assistant_output("item_a", content=[{"type": "text", "text": "hi"}])
    resp = {
        "id": "resp_1",
        "status": "completed",
        "status_details": None,
        "output": [out],
        "usage": None,
        "conversation_id": conv_id,
    }
    exp.handle_response_created(
        {"type": "response.created", "event_id": "event_1", "response": resp}
    )
    exp.handle_response_done(
        {"type": "response.done", "event_id": "event_2", "response": resp}
    )

    time.sleep(0.08)

    # Find the thread_id captured when realtime.response was created
    response_indices = [
        i for i, op in enumerate(client.created) if op == "realtime.response"
    ]
    assert len(response_indices) == 1
    assert client.thread_ids[response_indices[0]] == conv_id

    # Conversation call should NOT have thread_id set
    conv_indices = [
        i for i, op in enumerate(client.created) if op == "realtime.conversation"
    ]
    assert len(conv_indices) == 1
    assert client.thread_ids[conv_indices[0]] is None


def test_response_without_conversation_id_has_no_thread_id(monkeypatch):
    """When conversation_id is None (Beta API), no thread_id should be set."""
    client = DummyWeaveClient()
    install_require_weave_client(monkeypatch, client)
    import weave.integrations.openai_realtime.state_exporter as se

    monkeypatch.setattr(
        se.Content, "from_bytes", staticmethod(lambda b, extension: {"ok": True})
    )

    exp = StateExporter()
    session = {
        "id": "sess_1",
        "model": "m",
        "modalities": ["audio"],
        "instructions": "",
        "voice": "alloy",
        "input_audio_format": "pcm16",
        "output_audio_format": "pcm16",
        "input_audio_transcription": None,
        "turn_detection": {"type": "none"},
        "tools": [],
        "tool_choice": "auto",
        "temperature": 0.6,
        "max_response_output_tokens": None,
    }
    exp.handle_session_updated(
        {"type": "session.updated", "event_id": "event_0", "session": session}
    )

    out = make_assistant_output("item_a", content=[{"type": "text", "text": "hi"}])
    resp = make_response("resp_1", out)  # conversation_id is None
    exp.handle_response_created(
        {"type": "response.created", "event_id": "event_1", "response": resp}
    )
    exp.handle_response_done(
        {"type": "response.done", "event_id": "event_2", "response": resp}
    )

    time.sleep(0.08)

    # All calls should have None thread_id
    response_indices = [
        i for i, op in enumerate(client.created) if op == "realtime.response"
    ]
    assert len(response_indices) == 1
    assert client.thread_ids[response_indices[0]] is None


def test_transcripts_not_required_when_text_modality_absent(monkeypatch):
    client = DummyWeaveClient()
    install_require_weave_client(monkeypatch, client)
    import weave.integrations.openai_realtime.state_exporter as se

    monkeypatch.setattr(
        se.Content, "from_bytes", staticmethod(lambda b, extension: {"ok": True})
    )

    exp = StateExporter()
    # Session without text modality -> no gating
    session = {
        "id": "sess_2",
        "model": "m",
        "modalities": ["audio"],
        "instructions": "",
        "voice": "alloy",
        "input_audio_format": "pcm16",
        "output_audio_format": "pcm16",
        "input_audio_transcription": None,
        "turn_detection": {"type": "none"},
        "tools": [],
        "tool_choice": "auto",
        "temperature": 0.6,
        "max_response_output_tokens": None,
    }
    exp.handle_session_updated(
        {"type": "session.updated", "event_id": "event_0", "session": session}
    )

    out = make_assistant_output("item_a", content=[{"type": "text", "text": "hi"}])
    resp = make_response("resp_x", out)
    exp.handle_response_created(
        {"type": "response.created", "event_id": "event_1", "response": resp}
    )
    exp.handle_response_done(
        {"type": "response.done", "event_id": "event_2", "response": resp}
    )

    # Should finish quickly without waiting for any transcripts
    time.sleep(0.08)
    assert client.finished == ["resp_x"]
