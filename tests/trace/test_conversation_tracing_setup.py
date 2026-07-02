"""Tests for the conversation/agent OTel tracing setup in weave_init.

The agent-trace exporter carries its target project in the ``project_id``
header (not the immutable OTel Resource) so it can follow a second
``weave.init()`` to a different project. Regression coverage for agent
spans bleeding into the first-initialized project.
"""

from __future__ import annotations

import base64
import logging

import pytest
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.util._once import Once

from weave.trace import weave_init


@pytest.fixture(autouse=True)
def _reset_global_tracer_provider(monkeypatch: pytest.MonkeyPatch):
    """Isolate OTel's set-once global provider and weave's provider globals."""
    monkeypatch.setattr(otel_trace, "_TRACER_PROVIDER", None)
    monkeypatch.setattr(otel_trace, "_TRACER_PROVIDER_SET_ONCE", Once())
    monkeypatch.setattr(weave_init, "_conversation_tracer_provider", None)
    monkeypatch.setattr(weave_init, "_conversation_span_exporter", None)
    monkeypatch.setattr(
        weave_init.env, "weave_trace_server_url", lambda: "https://trace.wandb.test"
    )


def test_conversation_tracing_reroutes_project_on_reinit(
    monkeypatch: pytest.MonkeyPatch,
):
    """A second init to a new project reroutes the live exporter, not the Resource."""
    weave_init._setup_conversation_tracing("ent", "proj-a", "sekret")

    provider = otel_trace.get_tracer_provider()
    exporter = weave_init._conversation_span_exporter
    assert isinstance(provider, TracerProvider)
    assert provider is weave_init._conversation_tracer_provider
    assert exporter is not None

    # Project rides the header; the Resource carries only service.name (an
    # immutable Resource can't follow a re-init).
    assert exporter._session.headers["project_id"] == "ent/proj-a"
    assert exporter._session.headers["Authorization"].startswith("Basic ")
    assert provider.resource.attributes["service.name"] == "weave-conversation-sdk"
    assert "wandb.project" not in provider.resource.attributes
    assert "wandb.entity" not in provider.resource.attributes

    # Re-init to a different project: same provider + exporter objects (OTel's
    # global provider is set-once), header now points at the new project.
    weave_init._setup_conversation_tracing("ent", "proj-b", "sekret")
    assert otel_trace.get_tracer_provider() is provider
    assert weave_init._conversation_span_exporter is exporter
    assert exporter._session.headers["project_id"] == "ent/proj-b"
    assert exporter._session.headers["Authorization"].startswith("Basic ")


def test_conversation_tracing_reroutes_credentials_on_reinit(
    monkeypatch: pytest.MonkeyPatch,
):
    """Re-init with a new api key reroutes creds too, not just the project.

    The exporter's project_id and Authorization are one logical unit; a stale
    Authorization would export the new project's spans with the old account's
    credentials (cross-account attribution / 403s).
    """
    weave_init._setup_conversation_tracing("ent", "proj-a", "key-a")
    exporter = weave_init._conversation_span_exporter
    assert exporter is not None
    auth_a = exporter._session.headers["Authorization"]
    assert auth_a == "Basic " + base64.b64encode(b"api:key-a").decode()

    weave_init._setup_conversation_tracing("ent", "proj-b", "key-b")
    assert weave_init._conversation_span_exporter is exporter
    assert exporter._session.headers["project_id"] == "ent/proj-b"
    assert exporter._session.headers["Authorization"] == (
        "Basic " + base64.b64encode(b"api:key-b").decode()
    )
    assert exporter._session.headers["Authorization"] != auth_a

    # Re-init without a key drops the stale Authorization rather than keeping it.
    weave_init._setup_conversation_tracing("ent", "proj-c", None)
    assert exporter._session.headers["project_id"] == "ent/proj-c"
    assert "Authorization" not in exporter._session.headers


def test_conversation_tracing_flush_semantics_on_reinit(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    """Flush precedes reheader; same project skips it; a timed-out flush still reroutes (warns)."""
    weave_init._setup_conversation_tracing("ent", "proj-a", "key-a")
    provider = weave_init._conversation_tracer_provider
    exporter = weave_init._conversation_span_exporter
    assert provider is not None
    assert exporter is not None

    flushed_project_ids: list[str | None] = []
    flush_ok = True

    def _spy_flush(*args: object, **kwargs: object) -> bool:
        # Capture project_id visible at flush time to prove flush precedes reheader.
        flushed_project_ids.append(exporter._session.headers.get("project_id"))
        return flush_ok

    monkeypatch.setattr(provider, "force_flush", _spy_flush)

    weave_init._setup_conversation_tracing("ent", "proj-b", "key-b")
    assert flushed_project_ids == ["ent/proj-a"]
    assert exporter._session.headers["project_id"] == "ent/proj-b"

    # Same project + creds: no reroute work, no blocking flush.
    weave_init._setup_conversation_tracing("ent", "proj-b", "key-b")
    assert flushed_project_ids == ["ent/proj-a"]

    # A timed-out flush still reroutes (queued spans misroute to the new project) and warns.
    flush_ok = False
    with caplog.at_level(logging.WARNING):
        weave_init._setup_conversation_tracing("ent", "proj-c", "key-c")
    assert flushed_project_ids == ["ent/proj-a", "ent/proj-b"]
    assert exporter._session.headers["project_id"] == "ent/proj-c"
    assert "flush timed out" in caplog.text


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

    weave_init._setup_conversation_tracing("ent", "proj-a", "key-a")

    assert shutdowns == [True]
    assert weave_init._conversation_tracer_provider is None
    assert weave_init._conversation_span_exporter is None


def test_conversation_tracing_leaves_foreign_provider_untouched(
    monkeypatch: pytest.MonkeyPatch,
):
    """A user-installed provider is not hijacked and no exporter is created."""
    user_provider = TracerProvider()
    monkeypatch.setattr(otel_trace, "_TRACER_PROVIDER", user_provider)

    weave_init._setup_conversation_tracing("ent", "proj-a", "sekret")

    assert otel_trace.get_tracer_provider() is user_provider
    assert weave_init._conversation_span_exporter is None
    assert weave_init._conversation_tracer_provider is None
