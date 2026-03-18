"""Anthropic Claude Agent SDK — OTel instrumentation coming soon.

The official OpenTelemetry instrumentation for the Claude Agent SDK
(opentelemetry-instrumentation-claude-agent-sdk) is currently in active
development in the opentelemetry-python-contrib repository. As of March 2026
the package exists but the actual patching logic is still a stub — the
`_instrument()` method does not yet wrap any SDK calls.

Relevant links:
  - Package skeleton (merged):
    https://github.com/open-telemetry/opentelemetry-python-contrib/tree/main/instrumentation-genai/opentelemetry-instrumentation-claude-agent-sdk
  - Anthropic issue tracking the SDK instrumentation (last 3 weeks):
    https://github.com/anthropics/claude-agent-sdk-python/issues/611

Once the instrumentation is complete you should be able to do:

    pip install opentelemetry-instrumentation-claude-agent-sdk claude-agent-sdk
    from opentelemetry.instrumentation.claude_agent_sdk import ClaudeAgentSDKInstrumentor
    ClaudeAgentSDKInstrumentor().instrument(tracer_provider=provider)

In the meantime, Anthropic API calls made through the plain `anthropic` Python
client can be traced using the Traceloop instrumentor:

    pip install opentelemetry-instrumentation-anthropic
    from opentelemetry.instrumentation.anthropic import AnthropicInstrumentor
    AnthropicInstrumentor().instrument(tracer_provider=provider)

This captures individual `messages.create` calls with input/output content
but does not produce agent-level or tool-call spans.
"""
