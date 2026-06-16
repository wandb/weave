from unittest.mock import patch

import pytest
from pydantic import ValidationError

import weave
from weave.flow.scorer import Scorer
from weave.scorers.remote_scorer import (
    OAuthClientCredentialsConfig,
    RemoteScorer,
    StaticBearerAuthConfig,
    _validate_remote_scorer_endpoint_url,
)
from weave.trace.api import publish
from weave.trace.object_record import pydantic_object_record
from weave.trace_server import trace_server_interface as tsi

pytestmark = pytest.mark.trace_server


def test_remote_scorer_fields() -> None:
    rs = RemoteScorer(
        name="policy_remote",
        endpoint_url="https://scoring.example.com/v1/score",
        config={"threshold": 0.9},
    )
    assert rs.endpoint_url == "https://scoring.example.com/v1/score"
    assert rs.config == {"threshold": 0.9}
    assert rs.auth_config is None


def test_remote_scorer_record_excludes_op_methods() -> None:
    """WB-33909: RemoteScorer must not serialize score/summarize as op refs.

    Publishing those embeds CustomWeaveType(Op) payloads that the scoring worker
    rejects (``_assert_safe_scorer_payload``). RemoteScorer opts out via
    ``_weave_exclude_ops_from_record``; a normal Scorer subclass still records
    its ops.
    """
    rs = RemoteScorer(name="remote", endpoint_url="https://x.example.com/score")
    record = pydantic_object_record(rs)
    assert "score" not in record.__dict__
    assert "summarize" not in record.__dict__
    assert record.endpoint_url == "https://x.example.com/score"
    assert record._class_name == "RemoteScorer"

    class _PlainScorer(Scorer):
        pass

    plain_record = pydantic_object_record(_PlainScorer(name="plain"))
    assert "score" in plain_record.__dict__
    assert "summarize" in plain_record.__dict__


@pytest.mark.parametrize(
    ("auth_config", "expected_cls"),
    [
        (
            {
                "mode": "oauth_client_credentials",
                "token_endpoint_url": "https://idp.example.com/oauth2/token",
                "client_id": "weave-remote-scorer",
                "client_secret_name": "REMOTE_SCORER_CLIENT_SECRET",
                "scope": "remote-score",
            },
            OAuthClientCredentialsConfig,
        ),
        (
            {
                "mode": "static_bearer",
                "bearer_secret_name": "REMOTE_SCORER_BEARER_TOKEN",
            },
            StaticBearerAuthConfig,
        ),
    ],
)
def test_remote_scorer_auth_config_serializes_and_deserializes(
    auth_config: dict[str, str],
    expected_cls: type,
) -> None:
    rs = RemoteScorer(
        name="policy_remote",
        endpoint_url="https://scoring.example.com/v1/score",
        auth_config=auth_config,
    )

    assert isinstance(rs.auth_config, expected_cls)
    dumped = rs.model_dump()
    assert dumped["auth_config"] == auth_config

    round_tripped = RemoteScorer.model_validate(dumped)
    assert isinstance(round_tripped.auth_config, expected_cls)
    assert round_tripped.auth_config == rs.auth_config


@pytest.mark.parametrize(
    ("token_endpoint_url", "expected"),
    [
        (
            "https://idp.example.com/oauth2/token",
            "https://idp.example.com/oauth2/token",
        ),
        ("http://127.0.0.1:8000/token", "http://127.0.0.1:8000/token"),
        ("http://localhost:3000/token", "http://localhost:3000/token"),
        # Leading/trailing whitespace is stripped.
        (
            "  https://idp.example.com/oauth2/token\n",
            "https://idp.example.com/oauth2/token",
        ),
    ],
)
def test_oauth_token_endpoint_url_accepts_http_s_with_host(
    token_endpoint_url: str,
    expected: str,
) -> None:
    rs = RemoteScorer(
        endpoint_url="https://scoring.example.com/v1/score",
        auth_config={
            "mode": "oauth_client_credentials",
            "token_endpoint_url": token_endpoint_url,
            "client_id": "weave-remote-scorer",
            "client_secret_name": "REMOTE_SCORER_CLIENT_SECRET",
        },
    )
    assert isinstance(rs.auth_config, OAuthClientCredentialsConfig)
    assert rs.auth_config.token_endpoint_url == expected


@pytest.mark.parametrize(
    ("token_endpoint_url", "match_substr"),
    [
        ("", "http or https"),
        ("https://", "include a host"),
        ("http://", "include a host"),
        ("ftp://idp.example.com/token", "http or https"),
        ("not-a-url", "http or https"),
        # Non-string input bypasses whitespace-stripping and fails string coercion.
        (12345, None),
    ],
)
def test_oauth_token_endpoint_url_rejects_malformed(
    token_endpoint_url: object, match_substr: str | None
) -> None:
    with pytest.raises(ValidationError, match=match_substr):
        RemoteScorer(
            endpoint_url="https://scoring.example.com/v1/score",
            auth_config={
                "mode": "oauth_client_credentials",
                "token_endpoint_url": token_endpoint_url,
                "client_id": "weave-remote-scorer",
                "client_secret_name": "REMOTE_SCORER_CLIENT_SECRET",
            },
        )


def test_oauth_token_endpoint_url_urlparse_exception_path() -> None:
    from weave.scorers import remote_scorer as remote_scorer_module

    def boom(_: str) -> None:
        raise RuntimeError("urlparse blew up")

    with patch.object(remote_scorer_module, "urlparse", boom):
        with pytest.raises(ValidationError, match="must be a valid URL string"):
            RemoteScorer(
                endpoint_url="https://scoring.example.com/v1/score",
                auth_config={
                    "mode": "oauth_client_credentials",
                    "token_endpoint_url": "https://idp.example.com/oauth2/token",
                    "client_id": "weave-remote-scorer",
                    "client_secret_name": "REMOTE_SCORER_CLIENT_SECRET",
                },
            )


@pytest.mark.parametrize(
    "auth_config",
    [
        {"mode": "static_bearer"},
        {
            "mode": "oauth_client_credentials",
            "client_id": "weave-remote-scorer",
            "client_secret_name": "REMOTE_SCORER_CLIENT_SECRET",
        },
        {
            "mode": "oauth_client_credentials",
            "token_endpoint_url": "https://idp.example.com/oauth2/token",
            "client_secret_name": "REMOTE_SCORER_CLIENT_SECRET",
        },
        {
            "mode": "oauth_client_credentials",
            "token_endpoint_url": "https://idp.example.com/oauth2/token",
            "client_id": "weave-remote-scorer",
        },
    ],
)
def test_remote_scorer_auth_config_missing_required_fields_fail_validation(
    auth_config: dict[str, str],
) -> None:
    with pytest.raises(ValidationError, match="Field required"):
        RemoteScorer(
            endpoint_url="https://scoring.example.com/v1/score",
            auth_config=auth_config,
        )


@pytest.mark.parametrize(
    "auth_config",
    [
        {
            "mode": "static_bearer",
            "bearer_secret_name": "",
        },
        {
            "mode": "static_bearer",
            "bearer_secret_name": "   ",
        },
        {
            "mode": "oauth_client_credentials",
            "token_endpoint_url": "https://idp.example.com/oauth2/token",
            "client_id": "weave-remote-scorer",
            "client_secret_name": "",
        },
        {
            "mode": "oauth_client_credentials",
            "token_endpoint_url": "https://idp.example.com/oauth2/token",
            "client_id": "weave-remote-scorer",
            "client_secret_name": "   ",
        },
    ],
)
def test_remote_scorer_auth_config_secret_names_must_not_be_empty(
    auth_config: dict[str, str],
) -> None:
    with pytest.raises(ValidationError, match="must not be empty"):
        RemoteScorer(
            endpoint_url="https://scoring.example.com/v1/score",
            auth_config=auth_config,
        )


@pytest.mark.parametrize(
    "auth_config",
    [
        {
            "mode": "static_bearer",
            "bearer_secret_name": "REMOTE_SCORER_BEARER_TOKEN",
            "bearer_token": "raw-token-value",
        },
        {
            "mode": "oauth_client_credentials",
            "token_endpoint_url": "https://idp.example.com/oauth2/token",
            "client_id": "weave-remote-scorer",
            "client_secret_name": "REMOTE_SCORER_CLIENT_SECRET",
            "client_secret": "raw-client-secret",
        },
    ],
)
def test_remote_scorer_auth_config_rejects_raw_secret_fields(
    auth_config: dict[str, str],
) -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        RemoteScorer(
            endpoint_url="https://scoring.example.com/v1/score",
            auth_config=auth_config,
        )

    assert "bearer_token" not in StaticBearerAuthConfig.model_fields
    assert "client_secret" not in OAuthClientCredentialsConfig.model_fields


@pytest.mark.parametrize(
    ("endpoint_url", "expected"),
    [
        # http is allowed for local dev.
        ("http://127.0.0.1:8000/v1/score", "http://127.0.0.1:8000/v1/score"),
        ("http://localhost:3000/score", "http://localhost:3000/score"),
        # Surrounding whitespace, newlines, and tabs are stripped.
        ("  https://scoring.example.com/v1  ", "https://scoring.example.com/v1"),
        ("\thttps://scoring.example.com/v1\n", "https://scoring.example.com/v1"),
    ],
)
def test_remote_scorer_endpoint_url_normalizes(
    endpoint_url: str, expected: str
) -> None:
    rs = RemoteScorer(endpoint_url=endpoint_url)
    assert rs.endpoint_url == expected


@pytest.mark.parametrize(
    "url",
    [
        "https://scoring.example.com/v1/score",
        "http://127.0.0.1:8000/score",
        "https://scoring.example.com:8443/p",
    ],
)
def test_validate_remote_scorer_endpoint_url_accepts_http_s_with_host(
    url: str,
) -> None:
    assert _validate_remote_scorer_endpoint_url(url) == url


@pytest.mark.parametrize(
    ("url", "message_substr"),
    [
        ("", "http or https"),
        ("https://", "include a host"),
        ("http://", "include a host"),
        ("http:///no-netloc", "include a host"),
        ("ftp://example.com/score", "http or https"),
        ("file:///tmp/score", "http or https"),
        ("not-a-url", "http or https"),
    ],
)
def test_validate_remote_scorer_endpoint_url_rejects(
    url: str,
    message_substr: str,
) -> None:
    with pytest.raises(ValueError, match=message_substr):
        _validate_remote_scorer_endpoint_url(url)


def test_validate_remote_scorer_endpoint_url_urlparse_exception_is_wrapped() -> None:
    with patch(
        "weave.scorers.remote_scorer.urlparse", side_effect=OSError("parse failed")
    ):
        with pytest.raises(
            ValueError, match="endpoint_url must be a valid URL string"
        ) as exc_info:
            _validate_remote_scorer_endpoint_url("https://example.com/x")
    assert exc_info.value.__cause__ is not None


@pytest.mark.parametrize(
    ("bad_url", "match_substr"),
    [
        ("ftp://example.com/score", "http or https"),
        ("https://", "host"),
        ("not-a-url", "http or https"),
    ],
)
def test_remote_scorer_endpoint_url_rejects_malformed(
    bad_url: str, match_substr: str
) -> None:
    with pytest.raises(ValidationError, match=match_substr):
        RemoteScorer(endpoint_url=bad_url)


def test_remote_scorer_score_raises_not_implemented() -> None:
    rs = RemoteScorer(endpoint_url="https://scoring.example.com/v1/score")
    with pytest.raises(NotImplementedError) as exc_info:
        rs.score(output="x")
    assert str(exc_info.value) == (
        "RemoteScorer is run by the Weave scoring worker against your HTTPS "
        "endpoint; score() is not part of that path."
    )


def test_remote_scorer_with_auth_config_round_trips_via_publish(client) -> None:
    """Publishing a RemoteScorer with auth_config must reconstruct the typed
    auth_config on read.

    Regression: the base ``Scorer.from_obj`` leaves the nested ``auth_config`` as
    a ``WeaveObject`` that the ``extra="forbid"`` union rejects, so ``ref.get()``
    (and the scoring worker) raised a ``ValidationError``. ``RemoteScorer.from_obj``
    unwraps it instead.
    """
    scorer = RemoteScorer(
        name="rs_auth",
        endpoint_url="http://127.0.0.1:8765/score",
        auth_config=OAuthClientCredentialsConfig(
            mode="oauth_client_credentials",
            token_endpoint_url="http://127.0.0.1:8765/token",
            client_id="cid",
            client_secret_name="SEC",
            scope="s",
        ),
    )
    ref = publish(scorer, name="rs_auth")

    gotten = ref.get()
    assert isinstance(gotten, RemoteScorer)
    assert isinstance(gotten.auth_config, OAuthClientCredentialsConfig)
    assert gotten.auth_config.client_id == "cid"
    assert gotten.auth_config.client_secret_name == "SEC"
    # Secret values are never embedded — only the secret name.
    assert gotten.endpoint_url == "http://127.0.0.1:8765/score"


def test_remote_scorer_from_ui_shape_with_extra_fields_loads(client) -> None:
    """A UI-created RemoteScorer carries extra fields and a plain auth_config dict.

    The UI persists ``is_traced`` (not a RemoteScorer field) and ``auth_config``
    as a plain dict. ``from_obj`` must drop unknown fields and type the
    auth_config so the scoring worker can load it. Regression: ``model_validate``
    on the raw unwrapped val rejected ``is_traced`` under ``extra="forbid"``.
    """
    object_id = "remote_ui_scorer"
    val = {
        "_type": "RemoteScorer",
        "_class_name": "RemoteScorer",
        "_bases": ["RemoteScorer", "Scorer", "Object", "BaseModel"],
        "name": object_id,
        "description": "created from the UI",
        "column_map": None,
        "endpoint_url": "http://127.0.0.1:8765/score",
        "config": None,
        "is_traced": True,  # extra field the model does not declare
        "auth_config": {
            "mode": "oauth_client_credentials",
            "token_endpoint_url": "http://127.0.0.1:8765/token",
            "client_id": "cid",
            "client_secret_name": "SEC",
            "scope": "s",
        },
    }
    res = client.server.obj_create(
        tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=client.project_id, object_id=object_id, val=val
            )
        )
    )
    uri = f"weave:///{client.entity}/{client.project}/object/{object_id}:{res.digest}"

    gotten = weave.ref(uri).get()
    assert isinstance(gotten, RemoteScorer)
    assert isinstance(gotten.auth_config, OAuthClientCredentialsConfig)
    assert gotten.auth_config.client_id == "cid"
    assert not hasattr(gotten, "is_traced")
