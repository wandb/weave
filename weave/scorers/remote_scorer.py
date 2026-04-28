"""Customer-hosted remote HTTP scorer configuration."""

from typing import Any
from urllib.parse import urlparse

from pydantic import Field, field_validator

from weave.flow.scorer import Scorer
from weave.trace.objectify import register_object
from weave.trace.op import op


@register_object
class RemoteScorer(Scorer):
    """Scorer backed by a customer-managed HTTPS endpoint.

    The Python SDK stores configuration for publication with monitors. Remote
    scoring is **invoked from the Weave scoring worker**, which performs the
    outbound ``POST`` and feedback writes; it does not run by calling
    :meth:`score` in user code.

    **Authentication** is not modeled on this object in the current iteration:
    the deployment supplies credentials (e.g. a static bearer via
    ``WF_SCORING_WORKER_REMOTE_SCORER_BEARER_TOKEN`` in the worker). Object-level
    auth, OAuth, and secret indirection are planned in follow-up work.

    Attributes:
        endpoint_url: http(s) URL for the remote scoring ``POST`` endpoint.
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

    @op
    def score(self, *, output: Any, **kwargs: Any) -> Any:
        """Override for the Scorer.score function containing a more specific error.

        Not used for remote scoring; the Weave scoring worker performs the HTTP request.
        """
        raise NotImplementedError(
            "RemoteScorer is run by the Weave scoring worker against your HTTPS "
            "endpoint; score() is not part of that path."
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
