import dataclasses

import weave
from weave.trace.weave_client import redact_sensitive_keys
from weave.utils import sanitize


def test_code_capture_redacts_sensitive_values(weave_active):
    api_key = "123"

    @weave.op
    def func(x: int) -> int:
        cap = api_key
        return x + 1

    ref = weave.publish(func)
    op = ref.get()

    captured_code = op.get_captured_code()

    assert 'api_key = "REDACTED"' in captured_code


def test_redact_dataclass_structures() -> None:
    """Redaction covers flat, nested, and list-of-dataclass containers."""
    original_keys = sanitize.get_redact_keys()

    try:
        sanitize.add_redact_key("api_token")
        sanitize.add_redact_key("secret")

        flat = UserConfig(
            api_key="secret-key-123", username="testuser", api_token="token-456"
        )
        redacted_flat = redact_sensitive_keys(flat)
        # api_key (default) and api_token (added) redacted; username untouched
        assert redacted_flat.api_key == sanitize.REDACTED_VALUE
        assert redacted_flat.api_token == sanitize.REDACTED_VALUE
        assert redacted_flat.username == "testuser"

        nested = OuterSecretConfig(
            inner=InnerSecretConfig(secret="hidden", public="visible"), name="test"
        )
        redacted_nested = redact_sensitive_keys(nested)
        assert redacted_nested.inner.secret == sanitize.REDACTED_VALUE
        assert redacted_nested.inner.public == "visible"
        assert redacted_nested.name == "test"

        credentials = [
            Credential(api_key="key1", username="user1"),
            Credential(api_key="key2", username="user2"),
        ]
        redacted_list = redact_sensitive_keys(credentials)
        assert redacted_list[0].api_key == sanitize.REDACTED_VALUE
        assert redacted_list[0].username == "user1"
        assert redacted_list[1].api_key == sanitize.REDACTED_VALUE
        assert redacted_list[1].username == "user2"

    finally:
        sanitize._REDACT_KEYS = original_keys


def test_redact_dataclass_add_field_to_redact_list() -> None:
    """Adding a field name to the redact list redacts it in flat and nested dataclasses."""
    original_keys = sanitize.get_redact_keys()

    try:
        flat = FooConfig(foo="sensitive-value", bar="public-value")
        nested = OuterFooConfig(
            inner=InnerFooConfig(foo="sensitive-nested-value", public="visible"),
            name="test",
        )

        assert "foo" not in sanitize.get_redact_keys()

        before_flat = redact_sensitive_keys(flat)
        assert before_flat.foo == "sensitive-value"
        assert before_flat.bar == "public-value"
        before_nested = redact_sensitive_keys(nested)
        assert before_nested.inner.foo == "sensitive-nested-value"
        assert before_nested.inner.public == "visible"
        assert before_nested.name == "test"

        sanitize.add_redact_key("foo")
        assert "foo" in sanitize.get_redact_keys()

        after_flat = redact_sensitive_keys(flat)
        assert after_flat.foo == sanitize.REDACTED_VALUE
        assert after_flat.bar == "public-value"
        after_nested = redact_sensitive_keys(nested)
        assert after_nested.inner.foo == sanitize.REDACTED_VALUE
        assert after_nested.inner.public == "visible"
        assert after_nested.name == "test"

    finally:
        sanitize._REDACT_KEYS = original_keys


@dataclasses.dataclass
class UserConfig:
    api_key: str
    username: str
    api_token: str


@dataclasses.dataclass
class InnerSecretConfig:
    secret: str
    public: str


@dataclasses.dataclass
class OuterSecretConfig:
    inner: InnerSecretConfig
    name: str


@dataclasses.dataclass
class Credential:
    api_key: str
    username: str


@dataclasses.dataclass
class FooConfig:
    foo: str
    bar: str


@dataclasses.dataclass
class InnerFooConfig:
    foo: str
    public: str


@dataclasses.dataclass
class OuterFooConfig:
    inner: InnerFooConfig
    name: str
