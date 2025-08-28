# Koog

[Koog](https://docs.koog.ai/) is a Kotlin-based framework for building single-run and complex workflow agents. Koog includes built-in OpenTelemetry (OTEL) support and can export traces directly to W&B Weave, giving you rich visibility into prompts, completions, tool calls, and end-to-end agent execution.

With the Weave exporter enabled, Koog forwards OpenTelemetry spans to your Weave project so you can debug, analyze performance, and iterate faster.

## Prerequisites

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

Learn more about installing Koog [here](https://docs.koog.ai/).

## Enable Weave export (OpenTelemetry)

Install Koog’s OpenTelemetry feature and add the [Weave exporter](https://api.koog.ai/agents/agents-features/agents-features-opentelemetry/ai.koog.agents.features.opentelemetry.integration.weave/add-weave-exporter.html?query=fun%20OpenTelemetryConfig.addWeaveExporter(weaveOtelBaseUrl:%20String?%20=%20null,%20weaveEntity:%20String?%20=%20null,%20weaveProjectName:%20String?%20=%20null,%20weaveApiKey:%20String?%20=%20null,%20timeout:%20Duration%20=%2010.seconds)). Doing so will use Weave’s OpenTelemetry endpoint under the hood. Learn about Weave's OTEL support [here](../tracking/otel.md)

For more information on Koog OTEL configuration and concepts, see the [Koog OpenTelemetry support docs](https://docs.koog.ai/opentelemetry-support/).

```kotlin
fun main() = runBlocking {
    val apiKey = "api-key"
    val entity = System.getenv()["WEAVE_ENTITY"] ?: throw IllegalArgumentException("WEAVE_ENTITY is not set")
    val projectName = System.getenv()["WEAVE_PROJECT_NAME"] ?: "koog-tracing"

    val agent = AIAgent(
        executor = simpleOpenAIExecutor(apiKey),
        llmModel = OpenAIModels.CostOptimized.GPT4oMini,
        systemPrompt = "You are a code assistant. Provide concise code examples."
    ) {
        install(OpenTelemetry) {
            addWeaveExporter()
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

