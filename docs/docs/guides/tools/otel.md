import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Send OpenTelemetry Traces to Weave

## Overview
Weave supports ingestion of OpenTelemetry compatible trace data through a dedicated endpoint. This endpoint allows you to send OTLP (OpenTelemetry Protocol) formatted trace data directly to your Weave project.

## Endpoint details

**Path**: `/otel/v1/traces`
**Method**: POST
**Content-Type**: `application/x-protobuf`

## Authentication
Standard W&B authentication is used. You must have write permissions to the project where you're sending trace data.

## Required Headers
- `project_id: <your_entity>/<your_project_name>`
- `Authorization=Basic <Base64 Encoding of api:$WANDB_API_KEY>`

## Examples

The following section provides examples of OpenTelemetry with Weave for Python and TypeScript.

<Tabs groupId="programming-language" queryString>
  <TabItem value="python" label="Python" default>
    ## Prequisites

    You must modify the following fields before you can run the code samples below:
    1. `WANDB_API_KEY`: You can get this from [https://wandb.ai/authorize](https://wandb.ai/authorize).
    2. Entity: You can only log traces to the project under an entity that you have access to. You can find your entity name by visiting your W&N dashboard at [https://wandb.ai/home], and checking the **Teams** field in the left sidebar.
    3. Project Name: Choose a fun name!
    4. `OPENAI_API_KEY`: You can obtain this from the [OpenAI dashboard](https://platform.openai.com/api-keys).

    ### OpenInference Instrumentation:

    This example shows how to use the OpenAI instrumentation. There are many more available which you can find in the official repository: https://github.com/Arize-ai/openinference

    First, install the required dependencies:

    ```bash
    pip install openai openinference-instrumentation-openai opentelemetry-exporter-otlp-proto-http
    ```

    Next, paste the following code into a python file such as `openinference_example.py`

    ```python
    import base64
    import openai
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk import trace as trace_sdk
    from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
    from openinference.instrumentation.openai import OpenAIInstrumentor

    OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
    WANDB_BASE_URL = "https://trace.wandb.ai"
    PROJECT_ID = "<your-entity>/<your-project>"

    OTEL_EXPORTER_OTLP_ENDPOINT = f"{WANDB_BASE_URL}/otel/v1/traces"

    # Can be found at https://wandb.ai/authorize
    WANDB_API_KEY = "<your-wandb-api-key>"
    AUTH = base64.b64encode(f"api:{WANDB_API_KEY}".encode()).decode()

    OTEL_EXPORTER_OTLP_HEADERS = {
        "Authorization": f"Basic {AUTH}",
        "project_id": PROJECT_ID,
    }

    tracer_provider = trace_sdk.TracerProvider()

    # Configure the OTLP exporter
    exporter = OTLPSpanExporter(
        endpoint=OTEL_EXPORTER_OTLP_ENDPOINT,
        headers=OTEL_EXPORTER_OTLP_HEADERS,
    )

    # Add the exporter to the tracer provider
    tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))

    # Optionally, print the spans to the console.
    tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)

    def main():
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
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

    Finally, once you have set the fields specified above to their correct values, run the code:

    ```bash
    python openinference_example.py
    ```

    ### OpenLLMetry instrumentation:

    The following example shows how to use the OpenAI instrumentation. Additional examples are available at [https://github.com/traceloop/openllmetry/tree/main/packages](https://github.com/traceloop/openllmetry/tree/main/packages).

    First install the required dependencies:

    ```bash
    pip install openai opentelemetry-instrumentation-openai opentelemetry-exporter-otlp-proto-http
    ```

    Next, paste the following code into a python file such as `openllmetry_example.py`. Note that this is the same code as above, except the `OpenAIInstrumentor` is imported from `opentelemetry.instrumentation.openai` instead of `openinference.instrumentation.openai`

    ```python
    import base64
    import openai
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk import trace as trace_sdk
    from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
    from opentelemetry.instrumentation.openai import OpenAIInstrumentor

    OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
    WANDB_BASE_URL = "https://trace.wandb.ai"
    PROJECT_ID = "<your-entity>/<your-project>"

    OTEL_EXPORTER_OTLP_ENDPOINT = f"{WANDB_BASE_URL}/otel/v1/traces"

    # Can be found at https://wandb.ai/authorize
    WANDB_API_KEY = "<your-wandb-api-key>"
    AUTH = base64.b64encode(f"api:{WANDB_API_KEY}".encode()).decode()

    OTEL_EXPORTER_OTLP_HEADERS = {
        "Authorization": f"Basic {AUTH}",
        "project_id": PROJECT_ID,
    }

    tracer_provider = trace_sdk.TracerProvider()

    # Configure the OTLP exporter
    exporter = OTLPSpanExporter(
        endpoint=OTEL_EXPORTER_OTLP_ENDPOINT,
        headers=OTEL_EXPORTER_OTLP_HEADERS,
    )

    # Add the exporter to the tracer provider
    tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))

    # Optionally, print the spans to the console.
    tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)

    def main():
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
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

    Finally, once you have set the fields specified above to their correct values, run the code:

    ```bash
    python openllmetry_example.py
    ```

    ### Without instrumentation

    If you would prefer to use OTEL directly instead of an instrumentation package, you may do so. Span attributes will be parsed according to the OpenTelemetry semantic conventions described at [https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/).

    First, install the required dependencies:

    ```bash
    pip install openai opentelemetry-sdk opentelemetry-api opentelemetry-exporter-otlp-proto-http
    ```

    Next, paste the following code into a python file such as `opentelemetry_example.py`

    ```python
    import json
    import base64
    import openai
    from opentelemetry import trace
    from opentelemetry.sdk import trace as trace_sdk
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

    OPENAI_API_KEY = "YOUR_OPENAI_API_KEY"
    WANDB_BASE_URL = "https://trace.wandb.ai"
    PROJECT_ID = "<your-entity>/<your-project>"

    OTEL_EXPORTER_OTLP_ENDPOINT = f"{WANDB_BASE_URL}/otel/v1/traces"

    # Can be found at https://wandb.ai/authorize
    WANDB_API_KEY = "<your-wandb-api-key>"
    AUTH = base64.b64encode(f"api:{WANDB_API_KEY}".encode()).decode()

    OTEL_EXPORTER_OTLP_HEADERS = {
        "Authorization": f"Basic {AUTH}",
        "project_id": PROJECT_ID,
    }

    tracer_provider = trace_sdk.TracerProvider()

    # Configure the OTLP exporter
    exporter = OTLPSpanExporter(
        endpoint=OTEL_EXPORTER_OTLP_ENDPOINT,
        headers=OTEL_EXPORTER_OTLP_HEADERS,
    )

    # Add the exporter to the tracer provider
    tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))

    # Optionally, print the spans to the console.
    tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(tracer_provider)
    # Creates a tracer from the global tracer provider
    tracer = trace.get_tracer(__name__)
    tracer.start_span('name=standard-span')

    def my_function():
        with tracer.start_as_current_span("outer_span") as outer_span:
            client = openai.OpenAI()
            input_messages=[{"role": "user", "content": "Describe OTEL in a single sentence."}]
            # This will only appear in the side panel
            outer_span.set_attribute("input.value", json.dumps(input_messages))
            # This follows conventions and will appear in the dashboard
            outer_span.set_attribute("gen_ai.system", 'openai')
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=input_messages,
                max_tokens=20,
                stream=True,
                stream_options={"include_usage": True},
            )
            out = ""
            for chunk in response:
                if chunk.choices and (content := chunk.choices[0].delta.content):
                    out += content
            # This will only appear in the side panel
            outer_span.set_attribute("output.value", json.dumps({"content": out}))

    if __name__ == "__main__":
        my_function()
    ```

    Finally, once you have set the fields specified above to their correct values, run the code:

    ```bash
    python opentelemetry_example.py
    ```

    The span attribute prefixes `gen_ai` and `openinference` are used to determine which convention to use, if any, when interpreting the trace. If neither key is detected, then all span attributes are visible in the trace view. The full span is available in the side panel when you select a trace.

  </TabItem>
  <TabItem value="typescript" label="TypeScript">

1. First, install the necessary packages:

```bash
npm install weave opentelemetry-sdk-node @opentelemetry/exporter-trace-otlp-http @opentelemetry/resources @opentelemetry/semantic-conventions @opentelemetry/sdk-trace-base
```

2. Configure the OTEL Exporter by creating a TypeScript file (`e.g., weave-otel-integration.ts`) with the following code:

```typescript
import * as weave from 'weave';  
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';  
import { Resource } from '@opentelemetry/resources';  
import { SemanticResourceAttributes } from '@opentelemetry/semantic-conventions';  
import { SimpleSpanProcessor, TracerProvider } from '@opentelemetry/sdk-trace-base';  
  
// Weave configuration  
const WANDB_BASE_URL = 'https://trace.wandb.ai';  
const PROJECT_ID = '<your-entity>/<your-project>';  
const WANDB_API_KEY = '<your-wandb-api-key>'; // Get from https://wandb.ai/authorize  
  
// Create base64 encoded auth header  
const AUTH = Buffer.from(`api:${WANDB_API_KEY}`).toString('base64');  
  
// Configure OTLP exporter  
const exporter = new OTLPTraceExporter({  
  url: `${WANDB_BASE_URL}/otel/v1/traces`,  
  headers: {  
    'Authorization': `Basic ${AUTH}`,  
    'project_id': PROJECT_ID,  
  },  
});  
  
// Create a tracer provider  
const provider = new TracerProvider({  
  resource: new Resource({  
    [SemanticResourceAttributes.SERVICE_NAME]: 'my-typescript-service',  
  }),  
});  
  
// Add the exporter to the provider  
provider.addSpanProcessor(new SimpleSpanProcessor(exporter));  
  
// Register the provider  
provider.register();  
  
// Get a tracer  
const tracer = provider.getTracer('my-app-tracer');  
  
// Initialize Weave  
async function initWeave() {  
  await weave.init(PROJECT_ID.split('/')[1]);  
  console.log('Weave initialized');  
}  
  
export { tracer, initWeave };
```

3. Now, you can use the tracer to create spans in your application:

```typescript
import { tracer, initWeave } from './weave-otel-integration';  
import { context, trace } from '@opentelemetry/api';  
import OpenAI from 'openai';  
import * as weave from 'weave';  
  
async function main() {  
  // Initialize Weave  
  await initWeave();  
    
  // Create OpenAI client and wrap with Weave  
  const openai = weave.wrapOpenAI(new OpenAI({  
    apiKey: process.env.OPENAI_API_KEY,  
  }));  
  
  // Create a span  
  const span = tracer.startSpan('openai-request');  
    
  // Set span attributes following OpenTelemetry semantic conventions  
  span.setAttribute('gen_ai.system', 'openai');  
    
  // Use the context with this span to make the OpenAI request  
  await context.with(trace.setSpan(context.active(), span), async () => {  
    try {  
      const messages = [{ role: 'user', content: 'Describe OTEL in a single sentence.' }];  
        
      // Add input to span  
      span.setAttribute('input.value', JSON.stringify(messages));  
        
      // Make the OpenAI request  
      const response = await openai.chat.completions.create({  
        model: 'gpt-3.5-turbo',  
        messages: messages,  
        max_tokens: 20,  
      });  
        
      // Add output to span  
      span.setAttribute('output.value', JSON.stringify({  
        content: response.choices[0].message.content  
      }));  
        
      console.log(response.choices[0].message.content);  
    } catch (error) {  
      // Record error  
      span.recordException(error);  
      span.setStatus({ code: 2, message: error.message });  
      console.error('Error:', error);  
    } finally {  
      // End the span  
      span.end();  
    }  
  });  
}  
  
main().catch(console.error);
```

4. Compile and run the application:

npx tsc weave-otel-integration.ts  
node weave-otel-integration.js
Integrating with OpenAI in TypeScript
The example above shows how to combine Weave's TypeScript SDK with OpenTelemetry to trace OpenAI API calls. Here's a more specific example focusing on OpenAI integration:

```typescript
import * as weave from 'weave';  
import OpenAI from 'openai';  
import { tracer } from './weave-otel-integration';  
  
async function queryOpenAI(prompt: string) {  
  const span = tracer.startSpan('openai-query');  
    
  try {  
    // Set span attributes  
    span.setAttribute('gen_ai.system', 'openai');  
    span.setAttribute('input.value', JSON.stringify({ prompt }));  
      
    // Initialize Weave and wrap OpenAI client  
    await weave.init('my-project');  
    const client = weave.wrapOpenAI(new OpenAI());  
      
    // Make the API call  
    const response = await client.chat.completions.create({  
      model: 'gpt-4',  
      messages: [{ role: 'user', content: prompt }],  
      temperature: 0.7,  
      max_tokens: 100,  
    });  
      
    const content = response.choices[0].message.content;  
      
    // Record the output  
    span.setAttribute('output.value', JSON.stringify({ content }));  
      
    return content;  
  } catch (error) {  
    span.recordException(error);  
    span.setStatus({ code: 2, message: error.message });  
    throw error;  
  } finally {  
    span.end();  
  }  
}  
  
// Usage  
queryOpenAI('Explain quantum computing in simple terms')  
  .then(console.log)  
  .catch(console.error);
```

Notes
The TypeScript implementation is based on adapting the Python examples from the Weave OTEL documentation (docs/docs/guides/tools/otel.md) to TypeScript.

The Weave TypeScript SDK supports wrapping OpenAI clients with weave.wrapOpenAI() as shown in the documentation (docs/docs/guides/integrations/openai.md and docs/docs/quickstart.md).

The OpenTelemetry integration follows the standard OTLP HTTP exporter pattern, configured to send traces to Weave's OTEL endpoint.

The span attribute prefixes gen_ai and openinference are used to determine which convention to use when interpreting the trace, as mentioned in the documentation.

While the documentation doesn't provide direct TypeScript examples for OTEL integration, the implementation follows the patterns shown in the TypeScript SDK examples for other features.

Wiki pages you might want to explore:
  </TabItem>
</Tabs>

