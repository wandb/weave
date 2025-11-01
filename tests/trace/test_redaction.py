import dataclasses

import weave
from weave.trace.weave_client import redact_sensitive_keys
from weave.utils import sanitize


def test_code_capture_redacts_sensitive_values(client):
    api_key = "123"

    @weave.op
    def func(x: int) -> int:
        cap = api_key
        return x + 1

    ref = weave.publish(func)
    op = ref.get()

    captured_code = op.get_captured_code()

    assert 'api_key = "REDACTED"' in captured_code


def test_redact_dataclass_fields() -> None:
    """Test that dataclass fields are redacted when their names are in the redact set."""
    original_keys = sanitize.get_redact_keys()

    try:
        sanitize.add_redact_key("api_key")

        @dataclasses.dataclass
        class UserConfig:
            api_key: str
            username: str
            api_token: str

        config = UserConfig(
            api_key="secret-key-123",
            username="testuser",
            api_token="token-456",
        )

        redacted = redact_sensitive_keys(config)

        # The api_key field should be redacted
        assert redacted.api_key == sanitize.REDACTED_VALUE
        # api_token should not be redacted (not in redact set)
        assert redacted.api_token == "token-456"
        # username should not be redacted
        assert redacted.username == "testuser"

    finally:
        sanitize._REDACT_KEYS = original_keys


def test_redact_dataclass_nested() -> None:
    """Test that nested dataclasses are redacted correctly."""
    original_keys = sanitize.get_redact_keys()

    try:
        sanitize.add_redact_key("secret")

        @dataclasses.dataclass
        class InnerConfig:
            secret: str
            public: str

        @dataclasses.dataclass
        class OuterConfig:
            inner: InnerConfig
            name: str

        config = OuterConfig(
            inner=InnerConfig(secret="hidden", public="visible"),
            name="test",
        )

        redacted = redact_sensitive_keys(config)

        # Nested dataclass field should be redacted
        assert redacted.inner.secret == sanitize.REDACTED_VALUE
        assert redacted.inner.public == "visible"
        assert redacted.name == "test"

    finally:
        sanitize._REDACT_KEYS = original_keys


def test_redact_dataclass_in_list() -> None:
    """Test that dataclasses in lists are redacted."""
    original_keys = sanitize.get_redact_keys()

    try:
        sanitize.add_redact_key("api_key")

        @dataclasses.dataclass
        class Credential:
            api_key: str
            username: str

        credentials = [
            Credential(api_key="key1", username="user1"),
            Credential(api_key="key2", username="user2"),
        ]

        redacted = redact_sensitive_keys(credentials)

        # All dataclass instances in the list should have api_key redacted
        assert redacted[0].api_key == sanitize.REDACTED_VALUE
        assert redacted[0].username == "user1"
        assert redacted[1].api_key == sanitize.REDACTED_VALUE
        assert redacted[1].username == "user2"

    finally:
        sanitize._REDACT_KEYS = original_keys
