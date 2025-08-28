# Koog

[Koog](https://docs.koog.ai/) is a Kotlin-based framework for building single-run and complex workflow agents. Koog includes built-in OpenTelemetry (OTEL) support and can export traces directly to W&B Weave, giving you rich visibility into prompts, completions, tool calls, and end-to-end agent execution.

With the Weave exporter enabled, Koog forwards OpenTelemetry spans to your Weave project so you can debug, analyze performance, and iterate faster.

## Prerequisites

- A W&B account and Weave access
- API key and workspace details

Set the following environment variables before running your agent:

```bash
export WEAVE_API_KEY="<your-api-key>"
export WEAVE_ENTITY="<your-entity>"           # your W&B team/entity
export WEAVE_PROJECT_NAME="koog-tracing"      # any project name; created on first use
```

## Install Koog (Gradle)

Add Koog to your Kotlin project (Kotlin DSL shown):

```kotlin
dependencies {
    implementation("ai.koog:koog-agents:LATEST_VERSION")
}
```

Ensure `mavenCentral()` is listed in your repositories.

Learn more about installing Koog [here](https://docs.koog.ai/).

## Enable Weave export (OpenTelemetry)

Install Koog’s OpenTelemetry feature and add the Weave exporter. Koog uses Weave’s OpenTelemetry endpoint under the hood. For general Koog OTEL configuration and concepts, see the [Koog OpenTelemetry support docs](https://docs.koog.ai/opentelemetry-support/).

```kotlin
fun main() = runBlocking {
    val entity = System.getenv()["WEAVE_ENTITY"] ?: throw IllegalArgumentException("WEAVE_ENTITY is not set")
    val projectName = System.getenv()["WEAVE_PROJECT_NAME"] ?: "koog-tracing"

    val agent = AIAgent(
        executor = simpleOpenAIExecutor(ApiKeyService.openAIApiKey),
        llmModel = OpenAIModels.CostOptimized.GPT4oMini,
        systemPrompt = "You are a code assistant. Provide concise code examples."
    ) {
        install(OpenTelemetry) {
            addWeaveExporter(
                weaveEntity = entity,
                weaveProjectName = projectName
            )
        }
    }

    println("Running agent with Weave tracing")

    val result = agent.run("Tell me a joke about programming")

    println("Result: $result\nSee traces on https://wandb.ai/$entity/$projectName/weave/traces")
}
```

## What gets traced

When enabled, Koog’s Weave exporter captures the same spans as Koog’s general OTEL integration, including:

- Agent lifecycle events (start, stop, errors)
- LLM interactions (prompts, completions, token usage, latency)
- Tool and API calls (function calls and external requests)
- System context (model name, Koog version, environment metadata)

You can visualize these traces in the Weave UI to understand performance and quality.

## Troubleshooting

- No traces appear: confirm `WEAVE_API_KEY`, `WEAVE_ENTITY`, and `WEAVE_PROJECT_NAME` are set and valid.
- Authentication errors: ensure the API key has permission to write traces to the specified entity.
- Connection issues: verify your environment can reach W&B’s OTEL ingestion endpoints.

## Learn more

- Weave OpenTelemetry guide: [/guides/tracking/otel](/guides/tracking/otel)
- Weave Tracing overview: [/guides/tracking/tracing](/guides/tracking/tracing)
- Koog documentation: `https://docs.koog.ai/`


