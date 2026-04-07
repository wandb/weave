"""LiveSpanProcessor — ships span-start notifications for real-time UI.

Implements the OTel SpanProcessor interface. On ``on_start`` it fires a
lightweight POST to the trace server so the frontend can show spans as
they open. The full span data is still exported normally via
``BatchSpanProcessor`` on ``on_end``.

Usage::

    from weave.otel.live_processor import LiveSpanProcessor

    provider.add_span_processor(LiveSpanProcessor(
        endpoint="http://localhost:6345/otel/v1/genai/span/start",
        headers={"wandb-api-key": api_key},
    ))
    provider.add_span_processor(BatchSpanProcessor(OTLPHTTPSpanExporter(...)))
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

import requests
from opentelemetry.context import Context
from opentelemetry.sdk.trace import ReadableSpan, Span, SpanProcessor

logger = logging.getLogger(__name__)


class LiveSpanProcessor(SpanProcessor):
    """Sends lightweight span-start events for live agent visibility."""

    def __init__(
        self,
        endpoint: str,
        headers: dict[str, str] | None = None,
        max_workers: int = 2,
    ) -> None:
        self._endpoint = endpoint
        self._headers = headers or {}
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="live-span"
        )

    def on_start(self, span: Span, parent_context: Context | None = None) -> None:
        """Fire-and-forget POST of span identity to the start endpoint."""
        try:
            ctx = span.get_span_context()
            if ctx is None or not ctx.is_valid:
                return

            trace_id = format(ctx.trace_id, "032x")
            span_id = format(ctx.span_id, "016x")

            parent_span_id = ""
            parent = getattr(span, "parent", None)
            if parent and hasattr(parent, "span_id"):
                parent_span_id = format(parent.span_id, "016x")

            attrs = {}
            if hasattr(span, "_attributes") and span._attributes:
                attrs = dict(span._attributes)

            resource = getattr(span, "resource", None)
            project_id = ""
            if resource:
                entity = resource.attributes.get("wandb.entity", "")
                project = resource.attributes.get("wandb.project", "")
                if entity and project:
                    project_id = f"{entity}/{project}"

            if not project_id:
                return

            start_time = datetime.now(timezone.utc)
            if hasattr(span, "start_time") and span.start_time:
                ns = span.start_time
                start_time = datetime.fromtimestamp(ns / 1e9, tz=timezone.utc)

            payload = {
                "project_id": project_id,
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id,
                "span_name": span.name or "",
                "operation_name": str(attrs.get("gen_ai.operation.name", "")),
                "agent_name": str(attrs.get("gen_ai.agent.name", "")),
                "request_model": str(attrs.get("gen_ai.request.model", "")),
                "started_at": start_time.isoformat(),
            }

            self._executor.submit(self._send, payload)

        except Exception:
            logger.debug("LiveSpanProcessor.on_start failed", exc_info=True)

    def on_end(self, span: ReadableSpan) -> None:
        """No-op — full export handled by BatchSpanProcessor."""

    def _on_ending(self, span: ReadableSpan) -> None:
        """No-op — required by some OTel SDK versions."""

    def shutdown(self) -> None:
        """Shut down the thread pool."""
        self._executor.shutdown(wait=False)

    def force_flush(self, timeout_millis: int | None = None) -> bool:
        """No-op flush."""
        return True

    def _send(self, payload: dict[str, Any]) -> None:
        try:
            requests.post(
                self._endpoint,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    **self._headers,
                },
                timeout=5,
            )
        except Exception:
            logger.debug("LiveSpanProcessor POST failed", exc_info=True)
