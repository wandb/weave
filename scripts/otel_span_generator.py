#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "opentelemetry-api>=1.27.0",
#     "opentelemetry-sdk>=1.27.0",
#     "opentelemetry-exporter-otlp-proto-http>=1.27.0",
#     "typer>=0.16.0",
# ]
# ///
"""Weave OTEL span generator.

Emits synthetic spans to a Weave OTLP/HTTP ingest endpoint. Useful for
smoke-testing the v1 and v2 ingest routes end-to-end.

    uv run scripts/otel_span_generator.py --entity ENTITY --project PROJECT --variant v2

API key is read from --api-key, $WANDB_API_KEY, or ~/.netrc (api.wandb.ai).
"""

from __future__ import annotations

import base64
import netrc
import sys
import time
import uuid
from enum import Enum
from typing import Annotated
from urllib.parse import quote

import typer
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

DEFAULT_BASE_URL = "https://trace.wandb.ai"
# v1: generic OTLP, lands in the `calls` table -> "Traces" UI tab.
# v2: GenAI ingest, lands in the `agents` table -> "Agents" UI tab.
# Sending the wrong shape (plain spans to v2, GenAI spans to v1) returns
# 200 but doesn't surface usefully, so --variant picks both at once.
V1_PATH = "/otel/v1/traces"
V2_PATH = "/agents/otel/v1/traces"


class Variant(str, Enum):
    v1 = "v1"
    v2 = "v2"


def _api_key_from_netrc() -> str | None:
    try:
        entry = netrc.netrc().authenticators("api.wandb.ai")
    except (FileNotFoundError, netrc.NetrcParseError):
        return None
    return entry[2] if entry else None


def _emit_v1_trace(tracer: trace.Tracer, idx: int, children: int) -> None:
    with tracer.start_as_current_span("generator.parent", attributes={"trace_idx": idx}):
        for i in range(children):
            with tracer.start_as_current_span(f"generator.child.{i}"):
                time.sleep(0.005)


def _emit_v2_trace(tracer: trace.Tracer, idx: int, children: int) -> None:
    conv = uuid.uuid4().hex
    with tracer.start_as_current_span(
        "invoke_agent generator-agent",
        attributes={
            "gen_ai.operation.name": "invoke_agent",
            "gen_ai.agent.name": "generator-agent",
            "gen_ai.conversation.id": conv,
            "gen_ai.request.model": "synthetic-model-v1",
            "trace_idx": idx,
        },
    ):
        with tracer.start_as_current_span(
            "chat synthetic-model-v1",
            attributes={
                "gen_ai.operation.name": "chat",
                "gen_ai.request.model": "synthetic-model-v1",
                "gen_ai.conversation.id": conv,
                "gen_ai.usage.input_tokens": 42,
                "gen_ai.usage.output_tokens": 17,
            },
        ):
            time.sleep(0.01)
        for i in range(max(0, children - 1)):
            with tracer.start_as_current_span(
                f"execute_tool synthetic_tool_{i}",
                attributes={
                    "gen_ai.operation.name": "execute_tool",
                    "gen_ai.tool.name": f"synthetic_tool_{i}",
                },
            ):
                time.sleep(0.005)


def main(
    entity: Annotated[str, typer.Option(envvar="WANDB_ENTITY")],
    project: Annotated[str, typer.Option(envvar="WANDB_PROJECT")],
    variant: Annotated[Variant, typer.Option(case_sensitive=False)] = Variant.v2,
    num_traces: Annotated[int, typer.Option(min=1)] = 1,
    spans_per_trace: Annotated[int, typer.Option(min=1)] = 3,
    api_key: Annotated[str | None, typer.Option(envvar="WANDB_API_KEY")] = None,
    base_url: Annotated[str, typer.Option(envvar="WF_TRACE_SERVER_URL")] = DEFAULT_BASE_URL,
    dry_run: Annotated[bool, typer.Option()] = False,
) -> None:
    """Generate synthetic OTEL spans and export them to a Weave OTLP endpoint."""
    api_key = api_key or _api_key_from_netrc()
    if not api_key and not dry_run:
        typer.echo(
            "error: no API key (set WANDB_API_KEY, pass --api-key, or run `wandb login`)",
            err=True,
        )
        raise typer.Exit(2)

    base = base_url.rstrip("/")
    endpoint = f"{base}{V1_PATH if variant is Variant.v1 else V2_PATH}"
    app_url = base.replace("://trace.", "://", 1)
    tab = "agents" if variant is Variant.v2 else "traces"
    view = f"{app_url}/{entity}/{quote(project)}/weave/{tab}"

    typer.echo(f"endpoint : {endpoint}")
    typer.echo(f"project  : {entity}/{project}")
    typer.echo(f"variant  : {variant.value} ({num_traces} x {spans_per_trace} spans)")
    typer.echo(f"view     : {view}")
    if dry_run:
        typer.echo("dry-run: no spans sent")
        return

    token = base64.b64encode(f"api:{api_key}".encode()).decode()
    resource = Resource.create(
        {"service.name": "weave-otel-span-generator", "wandb.entity": entity, "wandb.project": project}
    )
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(
                endpoint=endpoint,
                headers={
                    "Authorization": f"Basic {token}",
                    "project_id": f"{entity}/{project}",
                },
            )
        )
    )
    trace.set_tracer_provider(provider)
    tracer = trace.get_tracer("weave.otel_span_generator")

    emit = _emit_v2_trace if variant is Variant.v2 else _emit_v1_trace
    for i in range(num_traces):
        emit(tracer, i, spans_per_trace)

    # BatchSpanProcessor queues spans asynchronously — force_flush drains
    # the queue before the interpreter exits. Without it, spans are lost.
    if not provider.force_flush(timeout_millis=10_000):
        typer.echo("warning: force_flush timed out; some spans may be lost", err=True)
        sys.exit(1)
    provider.shutdown()
    typer.echo(f"ok: flushed {num_traces} trace(s) to {variant.value} endpoint")
    typer.echo(f"view: {view}")


if __name__ == "__main__":
    typer.run(main)
