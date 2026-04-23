"""Unit tests for GenAI agent schema models."""

import pytest
from pydantic import ValidationError

from weave.trace_server.agents.schema import NormalizedMessage


def test_normalized_message_requires_role_and_content() -> None:
    with pytest.raises(ValidationError):
        NormalizedMessage()
    with pytest.raises(ValidationError):
        NormalizedMessage(role="user")

    msg = NormalizedMessage(role="assistant", content="")
    assert msg.finish_reason == ""
