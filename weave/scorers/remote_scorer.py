"""Customer-hosted remote HTTP scorer configuration."""

from typing import Annotated, Any, ClassVar, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing_extensions import Self

from weave.flow.scorer import Scorer
from weave.trace.objectify import register_object
from weave.trace.op import op
from weave.trace.vals import WeaveObject


class StaticBearerAuthConfig(BaseModel):
    """Static bearer auth backed by an entity secret-store reference."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["static_bearer"]
    bearer_secret_name: str = Field(
        ...,
        description="Name of the entity secret containing the bearer token.",
    )

    @field_validator("bearer_secret_name")
    @classmethod
    def validate_bearer_secret_name(cls, v: str) -> str:
        return _validate_non_empty_secret_name(v, "bearer_secret_name")


class OAuthClientCredentialsConfig(BaseModel):
    """OAuth 2.0 client credentials auth backed by secret-store references."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["oauth_client_credentials"]
    token_endpoint_url: str = Field(
        ...,
        description=(
            "http(s) URL of the OAuth token endpoint. The SDK validates URL "
            "shape only; the worker enforces deployment HTTPS and host policy."
        ),
    )
    client_id: str = Field(..., description="OAuth client identifier.")
    client_secret_name: str = Field(
        ...,
        description="Name of the entity secret containing the OAuth client secret.",
    )
    scope: str | None = Field(default=None, description="Optional OAuth scope.")

    @field_validator("token_endpoint_url", mode="before")
    @classmethod
    def strip_token_endpoint_url_whitespace(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("token_endpoint_url")
    @classmethod
    def validate_token_endpoint_url_shape(cls, v: str) -> str:
        try:
            parsed = urlparse(v)
        except Exception as exc:
            raise ValueError("token_endpoint_url must be a valid URL string") from exc
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("token_endpoint_url must use http or https")
        if not (parsed.hostname or "").strip():
            raise ValueError("token_endpoint_url must include a host")
        return v

    @field_validator("client_secret_name")
    @classmethod
    def validate_client_secret_name(cls, v: str) -> str:
        return _validate_non_empty_secret_name(v, "client_secret_name")


RemoteScorerAuthConfig = Annotated[
    StaticBearerAuthConfig | OAuthClientCredentialsConfig,
    Field(discriminator="mode"),
]


@register_object
class RemoteScorer(Scorer):
    """Scorer backed by a customer-managed HTTPS endpoint.

    The Python SDK stores configuration for publication with monitors. Remote
    scoring is **invoked from the Weave scoring worker**, which performs the
    outbound ``POST`` and feedback writes; it does not run by calling
    :meth:`score` in user code.

    **Authentication** can be configured with ``auth_config`` using secret-store
    references only. The SDK validates URL shape only; the worker enforces
    deployment URL policy at scoring time. If ``auth_config`` is omitted, the
    worker preserves its deployment-level fallback behavior while rollout
    continues.

    Attributes:
        endpoint_url: http(s) URL for the remote scoring ``POST`` endpoint.
        auth_config: Optional per-scorer authentication configuration. Secret
            fields store secret names, never raw credential values.
        config: Optional customer-defined JSON-serializable mapping; surfaced on
            the wire as ``scorer.config`` in the remote scorer contract.

    Examples:
        >>> rs = RemoteScorer(
        ...     name="policy_remote",
        ...     endpoint_url="https://scoring.example.com/v1/score",
        ...     config={"threshold": 0.9},
        ... )
        >>> rs.endpoint_url
        'https://scoring.example.com/v1/score'
    """

    # score()/summarize() are never executed in user code (the scoring worker
    # POSTs to endpoint_url), so don't serialize them as op refs on publish.
    # See pydantic_object_record / WB-33909.
    _weave_exclude_ops_from_record: ClassVar[bool] = True

    @field_validator("endpoint_url", mode="before")
    @classmethod
    def strip_endpoint_url_whitespace(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("endpoint_url")
    @classmethod
    def validate_endpoint_url_shape(cls, v: str) -> str:
        return _validate_remote_scorer_endpoint_url(v)

    endpoint_url: str = Field(
        ...,
        description=(
            "http(s) URL of the customer remote scoring endpoint (``http`` is allowed for "
            "local development, e.g. http://127.0.0.1:8000/score)."
        ),
    )
    config: dict[str, Any] | None = Field(
        default=None,
        description="Optional customer-defined JSON-serializable configuration.",
    )
    auth_config: RemoteScorerAuthConfig | None = Field(
        default=None,
        description=(
            "Optional per-scorer authentication configuration using entity "
            "secret-store references."
        ),
    )

    @op
    def score(self, *, output: Any, **kwargs: Any) -> Any:
        """Override for the Scorer.score function containing a more specific error.

        Not used for remote scoring; the Weave scoring worker performs the HTTP request.
        """
        raise NotImplementedError(
            "RemoteScorer is run by the Weave scoring worker against your HTTPS "
            "endpoint; score() is not part of that path."
        )

    @classmethod
    def from_obj(cls, obj: WeaveObject) -> Self:
        """Rebuild a RemoteScorer from its stored representation.

        ``unwrap()`` converts the stored object — including nested fields such
        as ``auth_config`` — back into plain Python values before validation.
        Without it, a nested ``auth_config`` arrives wrapped and fails to
        validate.

        Only known model fields are kept: stored objects can carry extra fields
        the model doesn't declare (e.g. ``is_traced`` on UI-created scorers), and
        ``Object`` is ``extra="forbid"``, so those must be dropped rather than
        rejected.
        """
        data = obj.unwrap()
        return cls.model_validate(
            {k: v for k, v in data.items() if k in cls.model_fields}
        )


def _validate_remote_scorer_endpoint_url(v: str) -> str:
    """Ensure ``endpoint_url`` is a usable http(s) URL with a host (dev-friendly)."""
    try:
        parsed = urlparse(v)
    except Exception as exc:
        raise ValueError("endpoint_url must be a valid URL string") from exc
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("endpoint_url must use the http or https scheme")
    host = (parsed.hostname or "").strip()
    if not host:
        raise ValueError(
            "endpoint_url must include a host, e.g. https://scoring.example.com/v1"
        )
    return v


def _validate_non_empty_secret_name(v: str, field_name: str) -> str:
    secret_name = v.strip()
    if not secret_name:
        raise ValueError(f"{field_name} must not be empty")
    return secret_name
