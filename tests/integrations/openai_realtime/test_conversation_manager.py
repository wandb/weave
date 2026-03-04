import asyncio

import weave.integrations.openai_realtime.conversation_manager as cm_mod


class DummyState:
    def __init__(self):
        self.calls: list[str] = []

    # Define all handler names ConversationManager registers
    def handle_session_created(self, msg):
        self.calls.append(msg["type"])

    def handle_session_update(self, msg):
        self.calls.append(msg["type"])

    def handle_session_updated(self, msg):
        self.calls.append(msg["type"])

    def handle_input_audio_append(self, msg):
        self.calls.append(msg["type"])

    def handle_input_audio_cleared(self, msg):
        self.calls.append(msg["type"])

    def handle_input_audio_committed(self, msg):
        self.calls.append(msg["type"])

    def handle_speech_started(self, msg):
        self.calls.append(msg["type"])

    def handle_speech_stopped(self, msg):
        self.calls.append(msg["type"])

    def handle_item_created(self, msg):
        self.calls.append(msg["type"])

    def handle_item_deleted(self, msg):
        self.calls.append(msg["type"])

    def handle_item_input_audio_transcription_completed(self, msg):
        self.calls.append(msg["type"])

    def handle_response_created(self, msg):
        self.calls.append(msg["type"])

    def handle_response_done(self, msg):
        self.calls.append(msg["type"])

    def handle_response_audio_delta(self, msg):
        self.calls.append(msg["type"])

    def handle_response_audio_done(self, msg):
        self.calls.append(msg["type"])


def test_conversation_manager_dispatch_sync(monkeypatch):
    # Patch StateExporter used by ConversationManager to our dummy
    monkeypatch.setattr(cm_mod, "StateExporter", DummyState)
    mgr = cm_mod.ConversationManager()

    msg = {
        "type": "session.updated",
        "event_id": "event_1",
        "session": {
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
        },
    }
    mgr.process_event(msg)
    assert "session.updated" in mgr.state.calls


def test_conversation_manager_worker_queue(monkeypatch):
    monkeypatch.setattr(cm_mod, "StateExporter", DummyState)
    mgr = cm_mod.ConversationManager()

    msg = {"type": "input_audio_buffer.cleared", "event_id": "event_1"}

    async def run():
        await mgr.submit_event(msg)
        # Wait until worker drains queue
        mgr._queue.join()

    asyncio.run(run())
    assert "input_audio_buffer.cleared" in mgr.state.calls
