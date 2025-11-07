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
        sanitize.add_redact_key("api_token")

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

        # Both api_key (default) and api_token (added) should be redacted
        assert redacted.api_key == sanitize.REDACTED_VALUE
        assert redacted.api_token == sanitize.REDACTED_VALUE
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


def test_redact_dataclass_add_field_to_redact_list() -> None:
    """Test that adding a field name to the redact list causes it to be redacted."""
    original_keys = sanitize.get_redact_keys()

    try:
        # Create a dataclass with a field "foo" that is not in the redact list
        @dataclasses.dataclass
        class TestConfig:
            foo: str
            bar: str

        config = TestConfig(foo="sensitive-value", bar="public-value")

        # Initially, "foo" should not be redacted
        assert "foo" not in sanitize.get_redact_keys()

        # Before adding to redact list, foo should not be redacted
        redacted_before = redact_sensitive_keys(config)
        assert redacted_before.foo == "sensitive-value"
        assert redacted_before.bar == "public-value"

        # Add "foo" to the redact list
        sanitize.add_redact_key("foo")

        # Now "foo" should be redacted
        assert "foo" in sanitize.get_redact_keys()
        redacted_after = redact_sensitive_keys(config)

        # After adding to redact list, foo should be redacted
        assert redacted_after.foo == sanitize.REDACTED_VALUE
        assert redacted_after.bar == "public-value"

    finally:
        sanitize._REDACT_KEYS = original_keys


def test_redact_dataclass_nested_add_field_to_redact_list() -> None:
    """Test that nested dataclasses redact fields after adding them to the redact list."""
    original_keys = sanitize.get_redact_keys()

    try:
        # Create nested dataclasses with a field "foo" that is not in the redact list
        @dataclasses.dataclass
        class InnerConfig:
            foo: str
            public: str

        @dataclasses.dataclass
        class OuterConfig:
            inner: InnerConfig
            name: str

        config = OuterConfig(
            inner=InnerConfig(foo="sensitive-nested-value", public="visible"),
            name="test",
        )

        # Initially, "foo" should not be redacted
        assert "foo" not in sanitize.get_redact_keys()

        # Before adding to redact list, foo should not be redacted
        redacted_before = redact_sensitive_keys(config)
        assert redacted_before.inner.foo == "sensitive-nested-value"
        assert redacted_before.inner.public == "visible"
        assert redacted_before.name == "test"

        # Add "foo" to the redact list
        sanitize.add_redact_key("foo")

        # Now "foo" should be redacted in nested dataclass
        redacted_after = redact_sensitive_keys(config)

        # After adding to redact list, foo should be redacted
        assert redacted_after.inner.foo == sanitize.REDACTED_VALUE
        assert redacted_after.inner.public == "visible"
        assert redacted_after.name == "test"

    finally:
        sanitize._REDACT_KEYS = original_keys
