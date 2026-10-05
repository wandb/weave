"""Tests for the conversation/agent OTel tracing setup in weave_init.

The agent-trace exporter carries its target project in the ``project_id``
header (not the immutable OTel Resource) so it can follow a second
``weave.init()`` to a different project. Regression coverage for agent
spans bleeding into the first-initialized project.

Routing and TLS are read off the requests session weave hands the exporter,
and off the requests that session sends: the exporter's own attributes differ
between opentelemetry-exporter-otlp-proto-http releases.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path

import pytest
import requests
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExportResult
from opentelemetry.util._once import Once

from weave.evaluation.otel_eval_linker import EvalLinkSpanProcessor
from weave.trace import weave_init
from weave.trace.otel_op_linker import OpLinkSpanProcessor
from weave.trace.urls import otel_traces_endpoint
from weave.version import VERSION
from weave.wandb_interface import auth as wandb_auth

_TRACE_SERVER_URL = "https://trace.wandb.test"

# Read by the exporter or by requests when weave builds the session.
_EXPORT_ENV_VARS = (
    "WEAVE_INSECURE_DISABLE_SSL",
    "REQUESTS_CA_BUNDLE",
    "CURL_CA_BUNDLE",
    "OTEL_EXPORTER_OTLP_CERTIFICATE",
    "OTEL_EXPORTER_OTLP_TRACES_CERTIFICATE",
    "OTEL_EXPORTER_OTLP_HEADERS",
    "OTEL_EXPORTER_OTLP_TRACES_HEADERS",
)

SentRequest = tuple[requests.PreparedRequest, dict[str, object]]


@pytest.fixture(autouse=True)
def _reset_global_tracer_provider(monkeypatch: pytest.MonkeyPatch):
    """Isolate OTel's set-once global provider and weave's provider globals."""
    monkeypatch.setattr(otel_trace, "_TRACER_PROVIDER", None)
    monkeypatch.setattr(otel_trace, "_TRACER_PROVIDER_SET_ONCE", Once())
    monkeypatch.setattr(weave_init, "_conversation_tracer_provider", None)
    monkeypatch.setattr(weave_init, "_conversation_span_exporter", None)
    monkeypatch.setattr(weave_init, "_conversation_export_session", None)
    monkeypatch.setattr(
        weave_init.env, "weave_trace_server_url", lambda: _TRACE_SERVER_URL
    )
    for name in _EXPORT_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def _basic(api_key: str) -> str:
    return "Basic " + base64.b64encode(f"api:{api_key}".encode()).decode()


def _capture_sends(monkeypatch: pytest.MonkeyPatch) -> list[SentRequest]:
    """Answer every request the stored session sends with a 200 and record it."""
    session = weave_init._conversation_export_session
    assert session is not None
    sent: list[SentRequest] = []

    def _send(request: requests.PreparedRequest, **kwargs: object) -> requests.Response:
        sent.append((request, kwargs))
        response = requests.Response()
        response.status_code = 200
        response.reason = "OK"
        response._content = b""
        response.request = request
        return response

    monkeypatch.setattr(session, "send", _send)
    return sent


def _export_span() -> None:
    """Push one span through the exporter weave installed."""
    exporter = weave_init._conversation_span_exporter
    assert exporter is not None
    span = TracerProvider(shutdown_on_exit=False).get_tracer("test").start_span("x")
    span.end()
    assert exporter.export([span]) == SpanExportResult.SUCCESS


@pytest.mark.trace_server
def test_conversation_tracing_reroutes_project_on_reinit(
    monkeypatch: pytest.MonkeyPatch,
):
    """A second init to a new project reroutes the live exporter, not the Resource."""
    credentials = wandb_auth.ApiKeyCredentials("sekret")
    weave_init._setup_conversation_tracing("ent", "proj-a", credentials)

    provider = otel_trace.get_tracer_provider()
    exporter = weave_init._conversation_span_exporter
    session = weave_init._conversation_export_session
    assert isinstance(provider, TracerProvider)
    assert provider is weave_init._conversation_tracer_provider
    assert exporter is not None
    assert isinstance(session, weave_init._ConversationExportSession)

    # Project routing stays in the header because the Resource is immutable.
    assert session.headers["project_id"] == "ent/proj-a"
    assert session.headers["Authorization"] == _basic("sekret")
    assert provider.resource.attributes["service.name"] == "weave-conversation-sdk"
    assert {
        key: value
        for key, value in provider.resource.attributes.items()
        if key.startswith(("weave.", "wandb."))
    } == {
        "wandb.sdk.name": "weave",
        "wandb.sdk.version": VERSION,
        "wandb.sdk.language": "python",
    }

    # Re-init to a different project: same provider, exporter and session
    # (OTel's global provider is set-once), header now points at the new project.
    weave_init._setup_conversation_tracing("ent", "proj-b", credentials)
    assert otel_trace.get_tracer_provider() is provider
    assert weave_init._conversation_span_exporter is exporter
    assert weave_init._conversation_export_session is session
    assert session.headers["project_id"] == "ent/proj-b"
    assert session.headers["Authorization"] == _basic("sekret")


def test_conversation_tracing_reroute_reaches_send(
    monkeypatch: pytest.MonkeyPatch,
):
    """The new project and key are on the wire, not only in the session's map."""
    weave_init._setup_conversation_tracing(
        "ent", "proj-a", wandb_auth.ApiKeyCredentials("key-a")
    )
    sent = _capture_sends(monkeypatch)
    _export_span()

    weave_init._setup_conversation_tracing(
        "ent", "proj-b", wandb_auth.ApiKeyCredentials("key-b")
    )
    _export_span()

    endpoint = otel_traces_endpoint(_TRACE_SERVER_URL)
    assert [
        (
            request.url,
            request.headers["project_id"],
            request.headers["Authorization"],
            request.headers["Content-Type"],
        )
        for request, _ in sent
    ] == [
        (endpoint, "ent/proj-a", _basic("key-a"), "application/x-protobuf"),
        (endpoint, "ent/proj-b", _basic("key-b"), "application/x-protobuf"),
    ]


def test_conversation_tracing_reroutes_credentials_on_reinit(
    monkeypatch: pytest.MonkeyPatch,
):
    """Re-init with a new api key reroutes creds too, not just the project.

    The exporter's project_id and Authorization are one logical unit; a stale
    Authorization would export the new project's spans with the old account's
    credentials (cross-account attribution / 403s).
    """
    weave_init._setup_conversation_tracing(
        "ent", "proj-a", wandb_auth.ApiKeyCredentials("key-a")
    )
    session = weave_init._conversation_export_session
    assert session is not None
    auth_a = session.headers["Authorization"]
    assert auth_a == _basic("key-a")

    weave_init._setup_conversation_tracing(
        "ent", "proj-b", wandb_auth.ApiKeyCredentials("key-b")
    )
    assert weave_init._conversation_export_session is session
    assert session.headers["project_id"] == "ent/proj-b"
    assert session.headers["Authorization"] == _basic("key-b")
    assert session.headers["Authorization"] != auth_a

    # Re-init without a key drops the stale Authorization rather than keeping it.
    weave_init._setup_conversation_tracing("ent", "proj-c", None)
    assert session.headers["project_id"] == "ent/proj-c"
    assert "Authorization" not in session.headers
    assert session.auth is None


def test_conversation_tracing_refreshes_bearer_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class RotatingCredentials(wandb_auth.WandbCredentials):
        def __init__(self) -> None:
            self.request_count = 0

        def authorization_header(self) -> str:
            self.request_count += 1
            return f"Bearer token-{self.request_count}"

        def bearer_token(self) -> str:
            return "unused"

        def wal_seed(self) -> str:
            return "stable"

    credentials = RotatingCredentials()
    weave_init._setup_conversation_tracing("ent", "proj", credentials)
    session = weave_init._conversation_export_session
    assert session is not None
    assert session.headers["Authorization"] == "Bearer token-1"
    assert session.auth is not None

    sent = _capture_sends(monkeypatch)
    _export_span()
    _export_span()

    assert [request.headers["Authorization"] for request, _ in sent] == [
        "Bearer token-2",
        "Bearer token-3",
    ]


def test_conversation_tracing_flush_semantics_on_reinit(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    """Flush precedes reheader; same project skips it; a timed-out flush still reroutes (warns)."""
    weave_init._setup_conversation_tracing(
        "ent", "proj-a", wandb_auth.ApiKeyCredentials("key-a")
    )
    provider = weave_init._conversation_tracer_provider
    session = weave_init._conversation_export_session
    assert provider is not None
    assert session is not None

    flushed_project_ids: list[str | None] = []
    flush_ok = True

    def _spy_flush(*args: object, **kwargs: object) -> bool:
        # Capture project_id visible at flush time to prove flush precedes reheader.
        flushed_project_ids.append(session.headers.get("project_id"))
        return flush_ok

    monkeypatch.setattr(provider, "force_flush", _spy_flush)

    credentials_b = wandb_auth.ApiKeyCredentials("key-b")
    weave_init._setup_conversation_tracing("ent", "proj-b", credentials_b)
    assert flushed_project_ids == ["ent/proj-a"]
    assert session.headers["project_id"] == "ent/proj-b"

    # Same project + creds: no reroute work, no blocking flush.
    weave_init._setup_conversation_tracing("ent", "proj-b", credentials_b)
    assert flushed_project_ids == ["ent/proj-a"]

    # A timed-out flush still reroutes (queued spans misroute to the new project) and warns.
    flush_ok = False
    with caplog.at_level(logging.WARNING):
        weave_init._setup_conversation_tracing(
            "ent", "proj-c", wandb_auth.ApiKeyCredentials("key-c")
        )
    assert flushed_project_ids == ["ent/proj-a", "ent/proj-b"]
    assert session.headers["project_id"] == "ent/proj-c"
    assert "flush timed out" in caplog.text


def test_conversation_tracing_drops_credentials_in_same_project(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    """A same-project re-init without a key stops authenticating.

    The early exit compares the Authorization marker on the session, so an
    unchanged project alone must not keep the previous account's auth.
    """
    # With no session auth, requests falls back to ~/.netrc for the host.
    monkeypatch.setenv("NETRC", str(tmp_path / "netrc"))
    weave_init._setup_conversation_tracing(
        "ent", "proj-a", wandb_auth.ApiKeyCredentials("key-a")
    )
    session = weave_init._conversation_export_session
    assert session is not None
    sent = _capture_sends(monkeypatch)

    weave_init._setup_conversation_tracing("ent", "proj-a", None)
    _export_span()

    assert session.auth is None
    assert "Authorization" not in session.headers
    assert [request.headers["project_id"] for request, _ in sent] == ["ent/proj-a"]
    assert "Authorization" not in sent[0][0].headers


@pytest.mark.parametrize(
    "ca_bundle", [False, True], ids=["no-ca-bundle", "requests-ca-bundle"]
)
def test_conversation_tracing_insecure_flag_disables_verify_on_send(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    ca_bundle: bool,
):
    """WEAVE_INSECURE_DISABLE_SSL reaches the send as verify=False, over any bundle."""
    monkeypatch.setenv("WEAVE_INSECURE_DISABLE_SSL", "true")
    if ca_bundle:
        monkeypatch.setenv("REQUESTS_CA_BUNDLE", str(tmp_path / "bundle.pem"))
    weave_init._setup_conversation_tracing(
        "ent", "proj-a", wandb_auth.ApiKeyCredentials("key-a")
    )
    sent = _capture_sends(monkeypatch)
    _export_span()

    assert [kwargs["verify"] for _, kwargs in sent] == [False]


@pytest.mark.parametrize(
    ("env_files", "verify_file"),
    [
        ({}, None),
        ({"REQUESTS_CA_BUNDLE": "bundle.pem"}, "bundle.pem"),
        (
            {
                "REQUESTS_CA_BUNDLE": "bundle.pem",
                "OTEL_EXPORTER_OTLP_TRACES_CERTIFICATE": "otel-ca.pem",
            },
            "otel-ca.pem",
        ),
    ],
    ids=["default", "requests-ca-bundle", "otel-certificate-over-ca-bundle"],
)
def test_conversation_tracing_verifies_tls_without_insecure_flag(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    env_files: dict[str, str],
    verify_file: str | None,
):
    """Without the flag, verify is not forced off and the OTel certificate wins."""
    for name, file_name in env_files.items():
        monkeypatch.setenv(name, str(tmp_path / file_name))
    weave_init._setup_conversation_tracing(
        "ent", "proj-a", wandb_auth.ApiKeyCredentials("key-a")
    )
    sent = _capture_sends(monkeypatch)
    _export_span()

    expected = True if verify_file is None else str(tmp_path / verify_file)
    assert [kwargs["verify"] for _, kwargs in sent] == [expected]


def test_conversation_tracing_drops_foreign_otlp_headers(
    monkeypatch: pytest.MonkeyPatch,
):
    """Headers meant for another collector are not sent to Weave.

    Exporter 1.42 copies OTEL_EXPORTER_OTLP_HEADERS onto the session.
    Exporter 1.45 merges them into the dict it passes on each request.
    """
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", "x-collector-key=abc")
    weave_init._setup_conversation_tracing(
        "ent", "proj-a", wandb_auth.ApiKeyCredentials("key-a")
    )
    sent = _capture_sends(monkeypatch)
    _export_span()

    headers = sent[0][0].headers
    assert "x-collector-key" not in headers
    assert headers["project_id"] == "ent/proj-a"
    assert headers["Content-Type"] == "application/x-protobuf"


@pytest.mark.parametrize(
    "env_name",
    ["OTEL_EXPORTER_OTLP_HEADERS", "OTEL_EXPORTER_OTLP_TRACES_HEADERS"],
)
def test_conversation_tracing_env_authorization_does_not_leak(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    env_name: str,
):
    """A collector's Authorization does not ride along to Weave.

    The session owns that header. On 1.45 the exporter repeats the env value
    on every request, which would otherwise override the session.
    """
    monkeypatch.setenv("NETRC", str(tmp_path / "netrc"))
    monkeypatch.setenv(env_name, "authorization=Bearer-leak")
    weave_init._setup_conversation_tracing(
        "ent", "proj-a", wandb_auth.ApiKeyCredentials("key-a")
    )
    sent = _capture_sends(monkeypatch)
    _export_span()

    assert sent[0][0].headers["Authorization"] == _basic("key-a")

    weave_init._setup_conversation_tracing("ent", "proj-a", None)
    _export_span()

    assert "Authorization" not in sent[1][0].headers


def test_conversation_tracing_keeps_exporter_content_encoding(
    monkeypatch: pytest.MonkeyPatch,
):
    """The exporter's own compression header survives the collector-header filter."""
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_COMPRESSION", "gzip")
    weave_init._setup_conversation_tracing(
        "ent", "proj-a", wandb_auth.ApiKeyCredentials("key-a")
    )
    sent = _capture_sends(monkeypatch)
    _export_span()

    assert sent[0][0].headers["Content-Encoding"] == "gzip"


def test_conversation_tracing_disowns_provider_if_set_once_refused(
    monkeypatch: pytest.MonkeyPatch,
):
    """If OTel refuses our provider (set-once lost), shut it down and don't own it."""
    shutdowns: list[bool] = []
    orig_shutdown = TracerProvider.shutdown

    def _spy_shutdown(self: TracerProvider, *args: object, **kwargs: object) -> None:
        shutdowns.append(True)
        orig_shutdown(self, *args, **kwargs)

    monkeypatch.setattr(TracerProvider, "shutdown", _spy_shutdown)
    # Simulate losing the set-once race: our set_tracer_provider call is ignored.
    monkeypatch.setattr(otel_trace, "set_tracer_provider", lambda provider: None)

    weave_init._setup_conversation_tracing(
        "ent", "proj-a", wandb_auth.ApiKeyCredentials("key-a")
    )

    assert shutdowns == [True]
    assert weave_init._conversation_tracer_provider is None
    assert weave_init._conversation_span_exporter is None
    assert weave_init._conversation_export_session is None


def test_conversation_tracing_leaves_foreign_provider_untouched(
    monkeypatch: pytest.MonkeyPatch,
):
    """A user-installed provider is not hijacked and no exporter is created."""
    user_provider = TracerProvider()
    monkeypatch.setattr(otel_trace, "_TRACER_PROVIDER", user_provider)

    weave_init._setup_conversation_tracing(
        "ent", "proj-a", wandb_auth.ApiKeyCredentials("sekret")
    )

    assert otel_trace.get_tracer_provider() is user_provider
    assert weave_init._conversation_span_exporter is None
    assert weave_init._conversation_tracer_provider is None
    assert weave_init._conversation_export_session is None


def test_conversation_tracing_installs_both_link_processors():
    """The eval and op link processors ride the provider weave installs.

    Every linking test builds its own provider by hand, so this is the only
    place that proves the processors are attached in production. The order is
    load-bearing: processors write attributes in registration order and OTel
    evicts the oldest first, so the op link must precede the eval link to keep
    a crowded span from dropping eval metadata.
    """
    weave_init._setup_conversation_tracing(
        "ent", "proj-a", wandb_auth.ApiKeyCredentials("sekret")
    )

    provider = weave_init._conversation_tracer_provider
    assert provider is not None
    processors = provider._active_span_processor._span_processors
    assert [type(p) for p in processors] == [
        BatchSpanProcessor,
        OpLinkSpanProcessor,
        EvalLinkSpanProcessor,
    ]
