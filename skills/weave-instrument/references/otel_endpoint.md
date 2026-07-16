# Export OTEL directly to Weave (the raw-OTEL path)

This is the most generic path. If the app *already emits* OpenTelemetry GenAI spans, whether from its
own `TracerProvider` or from a third-party instrumentor such as OpenInference, OpenLLMetry, or Logfire,
you do not need the Weave SDK at all. Point that OTel pipeline at Weave's agents endpoint. The spans
must carry the GenAI semantic conventions (a `gen_ai.operation.name` of `invoke_agent`, `chat`, or
`execute_tool`) to land agent-shaped.

## Transport (endpoint, auth, and routing)

- **Endpoint:** `https://trace.wandb.ai/agents/otel/v1/traces` (the path is `/agents/otel/v1/traces`).
  In code, use `from weave.trace.urls import otel_traces_endpoint` and call `otel_traces_endpoint()`.
- **Auth:** HTTP Basic, with user `api` and the W&B API key as the password. This gives the header
  `Authorization: Basic <base64("api:" + WANDB_API_KEY)>`.
- **Routing:** the project comes from the resource attributes `wandb.entity=<entity>` and
  `wandb.project=<project>`. Without them, spans do not reach the right project.
- **Identity isolation:** if the process already uses `WANDB_API_KEY` for another W&B client or
  proxy, keep the tracing key in a dedicated application setting and build only this exporter's
  Authorization header from it. Do not replace the process-wide identity.
- **Policy:** the exporter sends every span it receives. Enforce per-request no-trace or
  metadata-only policy where the spans are created; exporter setup is not a consent gate.

## Case A — generic env-var config (any language or framework, no code change)

```bash
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT="https://trace.wandb.ai/agents/otel/v1/traces"
export OTEL_EXPORTER_OTLP_TRACES_HEADERS="Authorization=Basic <base64(api:$WANDB_API_KEY)>"
export OTEL_RESOURCE_ATTRIBUTES="wandb.entity=<entity>,wandb.project=<project>"
```

Build the header value once, for example:
`python -c 'import base64,os;print(base64.b64encode(("api:"+os.environ["WANDB_API_KEY"]).encode()).decode())'`.

## Case B — the app builds its own TracerProvider (in code)

`weave.init()` **backs off if a real `TracerProvider` already exists**. It adds no exporter, so the
app's spans **never reach Weave** unless you add Weave's exporter yourself. Add a second span processor
to their provider:

```python
import base64, os
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from weave.trace.urls import otel_traces_endpoint

token = base64.b64encode(f"api:{os.environ['WANDB_API_KEY']}".encode()).decode()

provider.add_span_processor(...)                       # the app's existing processor(s)
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(
    endpoint=otel_traces_endpoint(),
    headers={"Authorization": f"Basic {token}"},
)))
```

The provider's `Resource` must carry `wandb.entity` and `wandb.project` (or you can set them through
`OTEL_RESOURCE_ATTRIBUTES`) so that spans route to the right project. This keeps the app's existing
export *and* fans out to Weave, which is the right move whenever the app owns its OTel setup.

For a multi-identity service, substitute its dedicated tracing setting when constructing `token`;
leave the existing `WANDB_API_KEY` untouched. Verify both exporters still receive the intended spans
and temporary tracing configuration does not remain in the process environment.
