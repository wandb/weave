import asyncio
import json

from weave.integrations.openai_realtime.connection import (
    WeaveAsyncWebsocketConnection,
    WeaveMediaConnection,
)


class DummyWSApp:
    def __init__(
        self,
        url,
        header=None,
        on_open=None,
        on_message=None,
        on_error=None,
        on_close=None,
        **kwargs,
    ):
        self.url = url
        self.header = header
        self.on_open = on_open
        self.on_message = on_message
        self.on_error = on_error
        self.on_close = on_close
        self.sent: list[tuple[bytes | str, int]] = []

    def send(self, data, opcode=None):
        self.sent.append((data, opcode))

    def run_forever(self, **kwargs):
        return None

    def close(self, **kwargs):
        return None


class DummyWeaveClient:
    def create_call(self, op=None, inputs=None, parent=None):
        from weave.trace.call import Call

        return Call(
            _op_name=op or "",
            trace_id="dummy",
            project_id="dummy",
            parent_id=None,
            inputs=inputs or {},
        )

    def finish_call(self, call, output=None):
        pass


def test_weave_media_connection_wrapping_sends_and_receives(monkeypatch):
    import weave.integrations.openai_realtime.state_exporter as se

    monkeypatch.setattr(se, "require_weave_client", lambda: DummyWeaveClient())

    mc = WeaveMediaConnection(
        url="ws://example",
        original_websocket_app=DummyWSApp,
        on_message=lambda ws, msg: None,
    )

    # Outgoing: user message -> should be parsed and fed to conversation manager without error
    user_msg = {"type": "input_audio_buffer.append", "audio": "AAA="}
    mc.send(json.dumps(user_msg))
    # Incoming: server message -> should be parsed and processed
    server_msg = {
        "type": "session.created",
        "event_id": "event_1",
        "session": {
            "id": "sess_1",
            "model": "gpt-test",
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
    # Simulate on_message callback invoked by websocket client
    mc.wrapped_on_message(mc.ws, json.dumps(server_msg))

    # Verify session propagated into state
    assert mc.conversation_manager.state.session_span is not None

    # Prevent atexit handler from firing after monkeypatch restores require_weave_client
    mc._exit_ran = True


class DummyAsyncConn:
    class ConnectionClosed(Exception):
        pass

    def __init__(self):
        self._messages = []

    async def send(self, data):
        self._messages.append(data)

    async def recv(self):
        # Provide a single message
        if self._messages:
            # echo a server message after any send
            msg = {
                "type": "session.updated",
                "event_id": "event_2",
                "session": {
                    "id": "sess_2",
                    "model": "gpt-test",
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
            return json.dumps(msg)
        raise self.ConnectionClosed()


def test_async_wrapper_basic(monkeypatch):
    import weave.integrations.openai_realtime.state_exporter as se

    monkeypatch.setattr(se, "require_weave_client", lambda: DummyWeaveClient())

    async def _drive_async_wrapper():
        conn = WeaveAsyncWebsocketConnection(DummyAsyncConn())
        await conn.send(json.dumps({"type": "response.create"}))
        # Try to receive once
        try:
            await conn.recv()
        except Exception:
            pass
        # Session should be set from received message
        assert conn.conversation_manager.state.session_span is not None

        # Prevent atexit handler from firing after monkeypatch restores require_weave_client
        conn._exit_ran = True

    asyncio.run(_drive_async_wrapper())
