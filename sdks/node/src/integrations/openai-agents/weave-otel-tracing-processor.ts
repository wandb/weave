import type {Span, Trace, TracingProcessor} from '../openai.agent.types';

/**
 * OTel-emitting TracingProcessor for the OpenAI Agents SDK.
 *
 * Emits one OpenTelemetry span per OpenAI Agents span using GenAI semantic
 * conventions where they apply:
 *
 * - (TODO) `invoke_agent {gen_ai.agent.name}` (https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/#invoke-agent-client-span)
 * - (TODO) `execute_tool {gen_ai.tool.name}` (https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/#execute-tool-span)
 * - (TODO) `chat {gen_ai.request.model}` (https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/#inference)
 *
 * Span types without a clean semantic mapping emit with a descriptive operation name
 * and `weave.openai_agents.*` attributes:
 *
 * - (TODO) `handoff {from} -> {to}`
 * - (TODO) `guardrail {name}`
 * - (TODO) `transcription`
 * - (TODO) `speech`
 * - (TODO) `speech_group`
 * - (TODO) `mcp_list_tools`
 * - (TODO) `{custom}`
 */
export class WeaveOtelTracingProcessor implements TracingProcessor {
  async onTraceStart(_trace: Trace) {}

  async onTraceEnd(_trace: Trace) {}

  async onSpanStart(_span: Span) {}

  async onSpanEnd(_span: Span) {}

  async shutdown(_timeout: number) {}

  async forceFlush() {}
}
