"""Tests for Session SDK OTel tracer lifecycle."""

from __future__ import annotations

import pytest

from weave.session.otel_setup import (
    get_tracer,
    reset_tracer_provider,
    setup_tracer_provider,
)


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    reset_tracer_provider()


class TestTracerLifecycle:
    def test_get_tracer_without_setup_returns_noop(self) -> None:
        tracer = get_tracer()
        span = tracer.start_span("test")
        span.end()  # should not raise

    def test_setup_and_get_tracer(self) -> None:
        setup_tracer_provider(endpoint="http://localhost:4318/otel/v1/genai/traces")
        tracer = get_tracer()
        span = tracer.start_span("test")
        assert span.is_recording()
        span.end()

    def test_setup_with_api_key(self) -> None:
        setup_tracer_provider(
            endpoint="http://localhost:4318/otel/v1/genai/traces",
            api_key="test-key-123",
        )
        tracer = get_tracer()
        span = tracer.start_span("test")
        assert span.is_recording()
        span.end()

    def test_reset_clears_provider(self) -> None:
        setup_tracer_provider(endpoint="http://localhost:4318/otel/v1/genai/traces")
        reset_tracer_provider()
        tracer = get_tracer()
        span = tracer.start_span("test")
        assert not span.is_recording()
        span.end()

    def test_setup_twice_replaces_provider(self) -> None:
        setup_tracer_provider(endpoint="http://localhost:4318/v1")
        setup_tracer_provider(endpoint="http://localhost:4318/v2")
        tracer = get_tracer()
        span = tracer.start_span("test")
        assert span.is_recording()
        span.end()
