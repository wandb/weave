"""Tests for the conversation/agent OTel tracing setup in weave_init.

The agent-trace exporter carries its target project in the ``project_id``
header (not the immutable OTel Resource) so it can follow a second
``weave.init()`` to a different project. Regression coverage for agent
spans bleeding into the first-initialized project.
"""

from __future__ import annotations

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
