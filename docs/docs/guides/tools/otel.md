# Send OpenTelemetry Traces to Weave 

## Overview
You can use the OTEL Trace API to send OpenTelemetry-compatible trace data to Weave. This allows you to integrate observability from any OTEL-instrumented application—like GenAI apps, backend services, or external APIs—into Weave's ecosystem.

Once ingested, trace data can be used to visualize, compare, and correlate with other Weave data.

**Use Cases:**
- Monitor OpenAI calls alongside frontend or backend performance
- Trace long-running chains and identify bottlenecks
- Compare traces across deployments or versions

## Get started
1. Get your API key from [wandb.ai/authorize](https://wandb.ai/authorize).
2. Define your `project_id` and OTEL endpoint.
3. Ensure that you have write access to the project.
4. Review the [API endpoint details](#api-endpoint-details).
5. Generate the [required authorization headers](#generate-authorization-headers) and set up your OTLP HTTP exporter using the provided values.
6. Try an example use case.

## API endpoint details
- **URL**: `https://api.wandb.ai/otel/v1/traces`
- **Method**: `POST`
- **Content-Type**: `application/x-protobuf`
- **Body**: A serialized `ExportTraceServiceRequest` protobuf

### Required headers

:::tip
You can generate the required authorization headers using [this script](#generate-authorization-headers).
:::

- `content-type: application/x-protobuf`
- `project_id: <your_entity>/<your_project_name>`
- `Authorization=Basic <Base64 Encoding of api:$WANDB_API_KEY>`

### Optional headers
- `content-encoding: gzip` or `deflate` (for compressed data)

### Response
If successful, the endpoint returns `200 OK` with an empty `ExportTraceServiceResponse` body.

### Error codes
- `401 Unauthorized` – Invalid or missing API key. Ensure you are using a valid API key.
- `403 Forbidden` – You don’t have permission to write to the project. Ensure your API key has write access.
- `400 Bad Request` – Headers are missing or the data format is invalid. Ensure that you've included [required headers](#required-headers) and that your data is correctly formatted.

## Limitations
- All traces in a single request must belong to the same project
- Maximum request size is defined by your server configuration.

## Generate authorization headers 

The following Python script generates the headers for performing trace exports to the `AwesomeProject` under the `ExampleCorp` entity. 

The recommended usage for this script is as follows:
1. Run the script once to generate the authorization headers.
2. Store the definitions in a secure place.
3. Load into your project environment.

To use this script, replace `ExampleCorp/AwesomeProject` and `YOUR_WANDB_API_KEY` with your actual W&B project name and API key.

```python
import base64

WANDB_BASE_URL = 'https://api.wandb.ai'
PROJECT_ID = "ExampleCorp/AwesomeProject"
WANDB_PASSWORD = "YOUR_WANDB_API_KEY"

AUTH = base64.b64encode(f"api:{WANDB_PASSWORD}".encode()).decode()

HEADER_DEFINITION = f"OTEL_EXPORTER_OTLP_HEADERS=\"Authorization=Basic {AUTH},project_id={PROJECT_ID}\""
ENDPOINT_DEFINITION = f"OTEL_EXPORTER_OTLP_ENDPOINT=\"{WANDB_BASE_URL}/otel/v1/traces\""

print(f"Place the following in your .env file:\n{HEADER_DEFINITION}\n{ENDPOINT_DEFINITION}")
```

## Example usage

### Create a basic OTLP exporter

The following code sample configures the OTLP exporter to send traces to Weave. Additional SDK configuration depends on your OpenTelemetry usage and environment. 

```python
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
import os

os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = "Authorization=Basic <ENCODED>,project_id=ExampleCorp/AwesomeProject"
otlp_exporter = OTLPSpanExporter(endpoint="https://api.wandb.ai/otel/v1/traces")

# Your additional configurations depend on your environment
```

### Use OpenLLMetry's `OpenAIInstrumentor`

The following code sample uses OpenLLMetry's `OpenAIInstrumentor` to automatically export OTEL Traces:

```python
import os
import openai
from dotenv import load_dotenv
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk import trace as trace_sdk
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.instrumentation.openai import OpenAIInstrumentor

load_dotenv()

tracer_provider = trace_sdk.TracerProvider()
# Export spans to the OTLP endpoint
tracer_provider.add_span_processor(SimpleSpanProcessor(
    OTLPSpanExporter(os.environ['OTEL_EXPORTER_OTLP_ENDPOINT'])
))
# Optionally, log the spans to console.
tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

# Set up the instrumentation for OpenAI
OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)

def main():
    client = openai.OpenAI()
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Describe OTEL in a single sentence."}],
        max_tokens=20,
        stream=True,
        stream_options={"include_usage": True},
    )
    for chunk in response:
        if chunk.choices and (content := chunk.choices[0].delta.content):
            print(content, end="")

if __name__ == "__main__":
    main()
```

To use this code sample, run the following commands in your terminal:

```bash
uv init
uv add dotenv openai opentelemetry-api opentelemetry-exporter-otlp opentelemetry-exporter-otlp-proto-http opentelemetry-instrumentation-openai opentelemetry-sdk
uv run script.py
```

### Use OpenInference's `OpenAIInstrumentor`

The following code sample uses OpenInference's `OpenAIInstrumentor` to automatically export OTEL Traces:

```python
import os
import openai
from dotenv import load_dotenv
from openinference.instrumentation.openai import OpenAIInstrumentor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk import trace as trace_sdk
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

load_dotenv()

endpoint = os.environ['OTEL_EXPORTER_OTLP_ENDPOINT']

tracer_provider = trace_sdk.TracerProvider()
tracer_provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter(endpoint)))
# Optionally, print the spans to the console.
tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)

def main():
    client = openai.OpenAI()
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Describe OTEL in a single sentence."}],
        max_tokens=20,
        stream=True,
        stream_options={"include_usage": True},
    )
    for chunk in response:
        if chunk.choices and (content := chunk.choices[0].delta.content):
            print(content, end="")
if __name__ == "__main__":
    main()
```

To use this code sample, run the following commands in your terminal:

```bash
uv init
uv add dotenv openai openinference-instrumentation-openai openinference-semantic-conventions opentelemetry-exporter-otlp-proto-http opentelemetry-instrumentation-openai
uv run script.py
```