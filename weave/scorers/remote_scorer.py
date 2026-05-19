"""Customer-hosted remote HTTP scorer configuration."""

from typing import Any
from urllib.parse import urlparse

from pydantic import Field, field_validator

from weave.flow.scorer import Scorer
from weave.trace.objectify import register_object


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

    def score(self, *, output: Any, **kwargs: Any) -> Any:
        """Local invocation is not supported; raise to make the contract explicit.

        Not used for remote scoring; the Weave scoring worker performs the HTTP request.

        Intentionally NOT decorated with ``@op``: during publish, the Weave SDK
        walks each ``@op`` method on the object and serializes it as an op ref.
        Following that ref later (e.g. in the scoring worker's
        ``_assert_safe_scorer_payload`` check) yields a ``CustomWeaveType(Op)``
        payload, which the worker rejects as unsafe and the monitor is skipped.
        Since RemoteScorer's score/summarize are never executed locally, leaving
        them as plain methods keeps them out of the published object's fields
        (matching the UI-created payload shape). See WB-33909.
        """
        raise NotImplementedError(
            "RemoteScorer is run by the Weave scoring worker against your HTTPS "
            "endpoint; score() is not part of that path."
        )

    def summarize(self, score_rows: list) -> dict | None:
        """Local invocation is not supported; raise to make the contract explicit.

        Intentionally NOT decorated with ``@op`` for the same reason as
        :meth:`score`. The base ``Scorer.summarize`` is an op; overriding it
        with a plain method prevents it from being picked up by
        ``getmembers(obj, is_op)`` during publish. See WB-33909.
        """
        raise NotImplementedError(
            "RemoteScorer summaries are computed by the Weave scoring worker; "
            "summarize() is not part of that path."
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
