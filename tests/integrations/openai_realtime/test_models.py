import pytest

from weave.integrations.openai_realtime import models


def test_create_user_and_server_messages_and_unknown():
    user_msg_dict = {"type": "input_audio_buffer.append", "audio": "AAA="}
    user_msg = models.create_user_message_from_dict(user_msg_dict)
    assert isinstance(user_msg, models.InputAudioBufferAppendMessage)
    assert user_msg.audio == "AAA="

    server_msg_dict = {
        "type": "session.created",
        "event_id": "event_1",
        "session": {
            "id": "sess_1",
            "model": "gpt-test",
            "modalities": ["text"],
            "instructions": "hi",
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
    server_msg = models.create_server_message_from_dict(server_msg_dict)
    assert isinstance(server_msg, models.SessionCreatedMessage)
    assert server_msg.session.id == "sess_1"

    # Unknown type falls back to Unknown
    unknown_user = models.create_user_message_from_dict({"type": "nope"})
    assert isinstance(unknown_user, models.UnknownClientMessage)
    unknown_server = models.create_server_message_from_dict(
        {"type": "nope", "event_id": "event_2"}
    )
    assert isinstance(unknown_server, models.UnknownServerMessage)


def test_item_id_helpers_direct_and_nested():
    # Direct item_id
    msg_direct = models.ItemDeletedMessage(
        type="conversation.item.deleted", event_id="event_3", item_id="item_1"
    )
    assert models.has_item_id(msg_direct) is True
    assert models.get_item_id(msg_direct) == "item_1"

    # Nested item.id
    item = models.ServerUserMessageItem(
        id="item_2", role="user", content=[], object="realtime.item"
    )
    msg_nested = models.ItemCreatedMessage(
        type="conversation.item.created",
        event_id="event_4",
        previous_item_id=None,
        item=item,
    )
    assert models.has_item_id(msg_nested) is True
    assert models.get_item_id(msg_nested) == "item_2"

    # No item id raises
    with pytest.raises(ValueError):
        models.get_item_id(
            models.UnknownServerMessage(type="unknown", event_id="event_5")
        )


def test_get_prev_and_response_output_ids():
    assert (
        models.get_prev_item_id(
            models.ItemCreatedMessage(
                type="conversation.item.created",
                event_id="event_6",
                previous_item_id=None,
                item=models.ServerAssistantMessageItem(
                    id="item_a", role="assistant", content=[], object="realtime.item"
                ),
            )
        )
        is None
    )

    resp = models.Response(
        id="resp_1",
        status="completed",
        status_details=None,
        output=[
            models.ResponseMessageItem(
                id="item_x", status="completed", role="assistant", content=[]
            )
        ],
        usage=None,
        conversation_id=None,
    )
    assert models.get_response_output_item_ids(resp) == ["item_x"]
