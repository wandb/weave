import {
  Attributes,
  type Context as OtelContext,
  type Span as OtelSpan,
  SpanStatusCode,
  context as otelContext,
  trace as otelTrace,
} from '@opentelemetry/api';

import {getWeaveTracer} from '../../genai/provider';
import {
  ATTR_GEN_AI_AGENT_NAME,
  ATTR_GEN_AI_CONVERSATION_ID,
  ATTR_GEN_AI_OPERATION_NAME,
  ATTR_GEN_AI_PROVIDER_NAME,
  ATTR_GEN_AI_TOOL_CALL_ARGUMENTS,
  ATTR_GEN_AI_TOOL_CALL_RESULT,
  ATTR_GEN_AI_TOOL_NAME,
} from '../../genai/semconv';
import type {
  AgentSpanData,
  FunctionSpanData,
  Span,
  Trace,
  TracingProcessor,
} from '../openai.agent.types';

const TRACER_NAME = 'weave.openai_agents';
const WEAVE_ATTR_PREFIX = 'weave.openai_agents';
const PROVIDER_NAME = 'openai';

/**
 * Descriptive OTel span name. AgentSpan uses the conventional
 * `invoke_agent <subject>` shape; other types fall back to a basic
 * `<kind> <subject>` for trace-viewer readability until later increments
 * add proper semconv mappings.
 */
function otelSpanName(span: Span): string {
  switch (span.spanData.type) {
    case 'agent':
      return `invoke_agent ${span.spanData.name}`;

    case 'function':
      return `execute_tool ${span.spanData.name}`;

    default:
      const name = (span.spanData as {name?: string}).name ?? '';
      return name ? `${span.spanData.type} ${name}` : span.spanData.type;
  }
}

function isoToMs(iso: string | null): number | undefined {
  if (!iso) return undefined;
  const ms = Date.parse(iso);
  return Number.isFinite(ms) ? ms : undefined;
}

function invokeAgentAttrs(
  spanData: AgentSpanData,
  conversationId: string
): Attributes {
  const attrs: Attributes = {
    [ATTR_GEN_AI_OPERATION_NAME]: 'invoke_agent',
    [ATTR_GEN_AI_AGENT_NAME]: spanData.name ?? '',
    [ATTR_GEN_AI_PROVIDER_NAME]: PROVIDER_NAME,
  };
  if (conversationId) {
    attrs[ATTR_GEN_AI_CONVERSATION_ID] = conversationId;
  }
  if (spanData.tools && spanData.tools.length > 0) {
    attrs[`${WEAVE_ATTR_PREFIX}.agent.tools`] = spanData.tools;
  }
  if (spanData.handoffs && spanData.handoffs.length > 0) {
    attrs[`${WEAVE_ATTR_PREFIX}.agent.handoffs`] = spanData.handoffs;
  }
  if (spanData.output_type) {
    attrs[`${WEAVE_ATTR_PREFIX}.agent.output_type`] = spanData.output_type;
  }
  return attrs;
}

function attrsForSpan(span: Span, conversationId: string): Attributes {
  switch (span.spanData.type) {
    case 'agent':
      return invokeAgentAttrs(span.spanData, conversationId);

    case 'function':
      return executeToolAttrs(span.spanData, conversationId);

    default:
      // Remaining span types still emit OTel spans with the openai
      // trace_id/span_id attributes set in onSpanStart, but no semconv
      // attributes yet — per-type mappings land in later increments.
      return {};
  }

  function executeToolAttrs(
    spanData: FunctionSpanData,
    conversationId: string
  ): Attributes {
    const attrs: Attributes = {
      [ATTR_GEN_AI_OPERATION_NAME]: 'execute_tool',
      [ATTR_GEN_AI_TOOL_NAME]: spanData.name ?? '',
    };
    if (conversationId) {
      attrs[ATTR_GEN_AI_CONVERSATION_ID] = conversationId;
    }
    if (spanData.input) {
      attrs[ATTR_GEN_AI_TOOL_CALL_ARGUMENTS] = spanData.input;
    }
    if (spanData.output) {
      attrs[ATTR_GEN_AI_TOOL_CALL_RESULT] = spanData.output;
    }
    return attrs;
  }
}

/**
 * OTel-emitting TracingProcessor for the OpenAI Agents SDK.
 *
 * Emits one OpenTelemetry span per OpenAI Agents span using GenAI semantic
 * conventions where they apply:
 *
 * - `invoke_agent {gen_ai.agent.name}` (https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/#invoke-agent-client-span)
 * - `execute_tool {gen_ai.tool.name}` (https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/#execute-tool-span)
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
  private spansById = new Map<string, OtelSpan>();
  private conversationIdsByTraceId = new Map<string, string>();
  // Used to sweep through opened spans `onTraceEnd` so we don't leak when
  // the SDK ends a trace without closing every span.
  private openSpanIdsByTraceId = new Map<string, string[]>();

  private tracer() {
    return getWeaveTracer(TRACER_NAME);
  }

  /**
   * Build an OTel context bound to this span's parent. Returns `undefined`
   * when no parent OTel span exists — the new span then becomes the OTel
   * root for the trace.
   */
  private parentContext(span: Span): OtelContext | undefined {
    if (!span.parentId) return undefined;
    const parent = this.spansById.get(span.parentId);
    if (!parent) return undefined;
    return otelTrace.setSpan(otelContext.active(), parent);
  }

  async onTraceStart(trace: Trace): Promise<void> {
    this.conversationIdsByTraceId.set(
      trace.traceId,
      trace.groupId ?? trace.traceId
    );
    if (!this.openSpanIdsByTraceId.has(trace.traceId)) {
      this.openSpanIdsByTraceId.set(trace.traceId, []);
    }
  }

  async onTraceEnd(trace: Trace): Promise<void> {
    const openSpanIds = this.openSpanIdsByTraceId.get(trace.traceId) ?? [];
    this.openSpanIdsByTraceId.delete(trace.traceId);
    // Sweep in LIFO order so child spans end before their parents.
    for (const spanId of openSpanIds.reverse()) {
      const otelSpan = this.spansById.get(spanId);
      if (!otelSpan) continue;

      this.spansById.delete(spanId);
      if (otelSpan.isRecording()) {
        otelSpan.end();
      }
    }
    this.conversationIdsByTraceId.delete(trace.traceId);
  }

  async onSpanStart(span: Span): Promise<void> {
    const parentCtx = this.parentContext(span);
    const otelSpan = this.tracer().startSpan(
      otelSpanName(span),
      {startTime: isoToMs(span.startedAt)},
      parentCtx
    );
    otelSpan.setAttribute(`${WEAVE_ATTR_PREFIX}.span_id`, span.spanId);
    otelSpan.setAttribute(`${WEAVE_ATTR_PREFIX}.trace_id`, span.traceId);
    this.spansById.set(span.spanId, otelSpan);

    const openSpanIds = this.openSpanIdsByTraceId.get(span.traceId);
    if (openSpanIds) {
      openSpanIds.push(span.spanId);
    } else {
      this.openSpanIdsByTraceId.set(span.traceId, [span.spanId]);
    }
  }

  async onSpanEnd(span: Span): Promise<void> {
    const otelSpan = this.spansById.get(span.spanId);
    this.spansById.delete(span.spanId);
    if (!otelSpan) return;

    const openSpanIds = this.openSpanIdsByTraceId.get(span.traceId);
    if (openSpanIds) {
      const idx = openSpanIds.indexOf(span.spanId);
      if (idx >= 0) openSpanIds.splice(idx, 1);
    }

    // Enrich-then-end. The enrichment block dispatches on span-data type
    // and may touch SDK payloads that could throw on unexpected shapes. End
    // the OTel span on any failure or it leaks: dropped from our map above
    // but never exported.
    try {
      // Re-compute the span name now that we have the full data. Later
      // increments will use this for chat spans (the openai Response's
      // model is only available on onSpanEnd, so the chat span starts as
      // "chat" and gains the model suffix here).
      otelSpan.updateName(otelSpanName(span));

      const conversationId =
        this.conversationIdsByTraceId.get(span.traceId) ?? '';
      const attrs = attrsForSpan(span, conversationId);
      otelSpan.setAttributes(attrs);

      if (span.error) {
        otelSpan.setStatus({
          code: SpanStatusCode.ERROR,
          message: span.error.message,
        });
        if (span.error.data) {
          otelSpan.setAttribute(
            `${WEAVE_ATTR_PREFIX}.error.data`,
            JSON.stringify(span.error.data)
          );
        }
      }
    } catch (err) {
      otelSpan.setStatus({
        code: SpanStatusCode.ERROR,
        message: `weave enrichment failed: ${String(err)}`,
      });
    } finally {
      otelSpan.end(isoToMs(span.endedAt));
    }
  }

  async shutdown(_timeout?: number): Promise<void> {
    this.endOpenSpans();
  }

  async forceFlush(): Promise<void> {
    this.endOpenSpans();
  }

  private endOpenSpans(): void {
    for (const otelSpan of this.spansById.values()) {
      if (otelSpan.isRecording()) {
        otelSpan.end();
      }
    }
    this.spansById.clear();
    this.conversationIdsByTraceId.clear();
    this.openSpanIdsByTraceId.clear();
  }
}
