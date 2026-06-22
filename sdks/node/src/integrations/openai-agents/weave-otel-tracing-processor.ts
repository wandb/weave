import {
  type Attributes,
  type Context as OtelContext,
  type Span as OtelSpan,
  SpanStatusCode,
  context as otelContext,
  trace as otelTrace,
} from '@opentelemetry/api';

import {getWeaveTracer} from '../../genai/provider';
import {
  serializeInputMessages,
  serializeOutputMessages,
  messagesFromChatCompletions,
  outputFromResponseSpan,
  inputFromResponseSpan,
  hasChatCompletionInput,
  hasChatCompletionOutput,
  hasResponsesOutput,
  hasResponsesInput,
} from './messages';
import {
  ATTR_GEN_AI_AGENT_NAME,
  ATTR_GEN_AI_CONVERSATION_ID,
  ATTR_GEN_AI_INPUT_MESSAGES,
  ATTR_GEN_AI_OPERATION_NAME,
  ATTR_GEN_AI_OUTPUT_MESSAGES,
  ATTR_GEN_AI_OUTPUT_TYPE,
  ATTR_GEN_AI_PROVIDER_NAME,
  ATTR_GEN_AI_REQUEST_CHOICE_COUNT,
  ATTR_GEN_AI_REQUEST_FREQUENCY_PENALTY,
  ATTR_GEN_AI_REQUEST_MAX_TOKENS,
  ATTR_GEN_AI_REQUEST_MODEL,
  ATTR_GEN_AI_REQUEST_PRESENCE_PENALTY,
  ATTR_GEN_AI_REQUEST_SEED,
  ATTR_GEN_AI_REQUEST_STOP_SEQUENCES,
  ATTR_GEN_AI_REQUEST_TEMPERATURE,
  ATTR_GEN_AI_REQUEST_TOP_P,
  ATTR_GEN_AI_RESPONSE_ID,
  ATTR_GEN_AI_RESPONSE_MODEL,
  ATTR_GEN_AI_TOOL_CALL_ARGUMENTS,
  ATTR_GEN_AI_TOOL_CALL_RESULT,
  ATTR_GEN_AI_TOOL_NAME,
  ATTR_GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS,
  ATTR_GEN_AI_USAGE_INPUT_TOKENS,
  ATTR_GEN_AI_USAGE_OUTPUT_TOKENS,
  ATTR_GEN_AI_USAGE_REASONING_OUTPUT_TOKENS,
} from '../../genai/semconv';
import type {
  AgentSpanData,
  CustomSpanData,
  FunctionSpanData,
  GenerationSpanData,
  GuardrailSpanData,
  HandoffSpanData,
  MCPListToolsSpanData,
  ResponseSpanData,
  Span,
  SpanData,
  SpeechGroupSpanData,
  SpeechSpanData,
  Trace,
  TracingProcessor,
  TranscriptionSpanData,
} from '@openai/agents';
import type OpenAI from 'openai';
import type {GenerationUsageData} from '@openai/agents';

const TRACER_NAME = 'weave.openai_agents';
const WEAVE_ATTR_PREFIX = 'weave.openai_agents';
const PROVIDER_NAME = 'openai';
const DEFAULT_CHAT_OUTPUT_TYPE = 'text';

function otelSpanName(span: Span<SpanData>): string {
  switch (span.spanData.type) {
    case 'agent':
      return `invoke_agent ${span.spanData.name}`;

    case 'function':
      return `execute_tool ${span.spanData.name}`;

    case 'response':
      return hasResponsesOutput(span.spanData)
        ? `chat ${span.spanData._response.model}`
        : `chat`;

    case 'generation':
      return `chat ${span.spanData.model ?? ''}`.trimEnd();

    case 'handoff':
      const from = span.spanData.from_agent || '?';
      const to = span.spanData.to_agent || '?';
      return `handoff ${from} -> ${to}`;

    case 'guardrail':
      return `guardrail ${span.spanData.name}`.trimEnd();

    case 'transcription':
      return 'transcription';

    case 'speech':
      return 'speech';

    case 'speech_group':
      return 'speech_group';

    case 'mcp_tools':
      return 'mcp_list_tools';

    case 'custom':
      const name = span.spanData.name ?? '';
      return name || 'custom';

    default:
      const spanData = span.spanData as {type: string; name?: string};
      return spanData.name
        ? `${spanData.type} ${spanData.name}`
        : spanData.type;
  }
}

function isoToMs(iso: string | null): number | undefined {
  if (!iso) return undefined;
  const ms = Date.parse(iso);
  return Number.isFinite(ms) ? ms : undefined;
}

function invokeAgentAttrs(spanData: AgentSpanData): Attributes {
  const attrs: Attributes = {
    [ATTR_GEN_AI_OPERATION_NAME]: 'invoke_agent',
    [ATTR_GEN_AI_AGENT_NAME]: spanData.name ?? '',
    [ATTR_GEN_AI_PROVIDER_NAME]: PROVIDER_NAME,
  };
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

function executeToolAttrs(spanData: FunctionSpanData): Attributes {
  const attrs: Attributes = {
    [ATTR_GEN_AI_OPERATION_NAME]: 'execute_tool',
    [ATTR_GEN_AI_TOOL_NAME]: spanData.name ?? '',
  };
  if (spanData.input) {
    attrs[ATTR_GEN_AI_TOOL_CALL_ARGUMENTS] = spanData.input;
  }
  if (spanData.output) {
    attrs[ATTR_GEN_AI_TOOL_CALL_RESULT] = spanData.output;
  }
  return attrs;
}

function responseUsageAttrs(
  usage: OpenAI.Responses.ResponseUsage | undefined
): Attributes | undefined {
  if (!usage) return;

  return {
    [ATTR_GEN_AI_USAGE_INPUT_TOKENS]: usage.input_tokens,
    [ATTR_GEN_AI_USAGE_OUTPUT_TOKENS]: usage.output_tokens,
    [ATTR_GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS]:
      usage.input_tokens_details?.cached_tokens,
    [ATTR_GEN_AI_USAGE_REASONING_OUTPUT_TOKENS]:
      usage.output_tokens_details?.reasoning_tokens,
  };
}

function generationSpanUsageAttrs(
  usage: GenerationUsageData | undefined
): Attributes | undefined {
  if (!usage) return;

  return {
    [ATTR_GEN_AI_USAGE_INPUT_TOKENS]: usage.input_tokens,
    [ATTR_GEN_AI_USAGE_OUTPUT_TOKENS]: usage.output_tokens,
    [ATTR_GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS]: usage.details
      ?.cached_tokens as number,
    [ATTR_GEN_AI_USAGE_REASONING_OUTPUT_TOKENS]: usage.details
      ?.reasoning_tokens as number,
  };
}

/**
 * `chat` attrs for a ResponseSpan. Pulls data from Agents-SDK populated `_response`
 * attribute when present.
 */
function responseChatAttrs(spanData: ResponseSpanData): Attributes {
  let attrs: Attributes = {
    [ATTR_GEN_AI_OPERATION_NAME]: 'chat',
    [ATTR_GEN_AI_RESPONSE_ID]: spanData.response_id,
    [ATTR_GEN_AI_PROVIDER_NAME]: PROVIDER_NAME,
    [ATTR_GEN_AI_OUTPUT_TYPE]: DEFAULT_CHAT_OUTPUT_TYPE,
  };

  if (hasResponsesInput(spanData)) {
    const {messages, attachments} = inputFromResponseSpan(spanData);

    attrs = {
      ...attrs,
      [ATTR_GEN_AI_INPUT_MESSAGES]: serializeInputMessages(
        messages,
        attachments
      ),
    };
  }

  if (hasResponsesOutput(spanData)) {
    const {messages, reasoning} = outputFromResponseSpan(spanData);
    const response = spanData._response;

    attrs = {
      ...attrs,
      [ATTR_GEN_AI_REQUEST_MODEL]: response.model,
      [ATTR_GEN_AI_RESPONSE_MODEL]: response.model,
      [ATTR_GEN_AI_RESPONSE_ID]: attrs[ATTR_GEN_AI_RESPONSE_ID] ?? response.id,
      [ATTR_GEN_AI_OUTPUT_MESSAGES]: serializeOutputMessages(
        messages,
        reasoning
      ),
      ...responseUsageAttrs(response.usage),
    };
  }

  return attrs;
}

/**
 * `chat` attrs for a GenerationSpan.
 */
function generationChatAttrs(spanData: GenerationSpanData): Attributes {
  const attrs: Attributes = {
    [ATTR_GEN_AI_OPERATION_NAME]: 'chat',
    [ATTR_GEN_AI_PROVIDER_NAME]: PROVIDER_NAME,
    [ATTR_GEN_AI_OUTPUT_TYPE]: DEFAULT_CHAT_OUTPUT_TYPE,
    [ATTR_GEN_AI_REQUEST_MODEL]: spanData.model,
  };

  if (hasChatCompletionInput(spanData) && spanData.input.length > 0) {
    const messages = messagesFromChatCompletions(spanData.input);
    attrs[ATTR_GEN_AI_INPUT_MESSAGES] = serializeInputMessages(messages, []);
  }

  if (hasChatCompletionOutput(spanData) && spanData.output.length > 0) {
    const messages = messagesFromChatCompletions(spanData.output);
    attrs[ATTR_GEN_AI_OUTPUT_MESSAGES] = serializeOutputMessages(messages, '');
  }

  return {
    ...attrs,
    ...generationSpanUsageAttrs(spanData.usage),
    ...modelConfigAttrs(spanData.model_config),
  };
}

/**
 * Allowlist of `GenerationSpanData.model_config` keys mapped to their
 * GenAI semconv attribute names. Only these keys are forwarded; everything
 * else on `model_config` is openai-specific and doesn't map cleanly to
 * GenAI semconv.
 */
const MODEL_CONFIG_KEY_MAP = {
  temperature: ATTR_GEN_AI_REQUEST_TEMPERATURE,
  top_p: ATTR_GEN_AI_REQUEST_TOP_P,
  frequency_penalty: ATTR_GEN_AI_REQUEST_FREQUENCY_PENALTY,
  presence_penalty: ATTR_GEN_AI_REQUEST_PRESENCE_PENALTY,
  max_tokens: ATTR_GEN_AI_REQUEST_MAX_TOKENS,
  seed: ATTR_GEN_AI_REQUEST_SEED,
  stop: ATTR_GEN_AI_REQUEST_STOP_SEQUENCES,
  n: ATTR_GEN_AI_REQUEST_CHOICE_COUNT,
};

/**
 * Extract `gen_ai.request.*` attrs from a GenerationSpanData.model_config.
 *
 * Keys not in the allowlist are dropped. Null/undefined values are dropped.
 * `stop` is normalized to an array (openai accepts a single string OR a
 * list); semconv requires `stop_sequences` to be a list of strings, so a
 * bare string becomes a single-element array and anything that's neither
 * string nor array is dropped.
 */
function modelConfigAttrs(
  modelConfig: GenerationSpanData['model_config']
): Attributes {
  if (!modelConfig) {
    return {};
  }

  const out: Attributes = {};
  for (const [key, attr] of Object.entries(MODEL_CONFIG_KEY_MAP)) {
    const value = modelConfig[key];
    if (value === null || value === undefined) {
      continue;
    }

    if (attr === ATTR_GEN_AI_REQUEST_STOP_SEQUENCES) {
      if (typeof value === 'string') {
        out[attr] = [value];
      } else if (Array.isArray(value)) {
        out[attr] = value;
      }
      continue;
    }

    out[attr] = value;
  }
  return out;
}

function handoffAttrs(spanData: HandoffSpanData): Attributes {
  return {
    [`${WEAVE_ATTR_PREFIX}.handoff.from_agent`]: spanData.from_agent ?? '',
    [`${WEAVE_ATTR_PREFIX}.handoff.to_agent`]: spanData.to_agent ?? '',
  };
}

function transcriptionAttrs(spanData: TranscriptionSpanData): Attributes {
  return {
    [`${WEAVE_ATTR_PREFIX}.transcription.model`]: spanData.model ?? '',
    [`${WEAVE_ATTR_PREFIX}.transcription.input`]: spanData.input?.data ?? '',
    [`${WEAVE_ATTR_PREFIX}.transcription.input_format`]:
      spanData.input?.format ?? '',
    [`${WEAVE_ATTR_PREFIX}.transcription.output`]: spanData.output ?? '',
  };
}

function guardrailAttrs(spanData: GuardrailSpanData): Attributes {
  return {
    [`${WEAVE_ATTR_PREFIX}.guardrail.name`]: spanData.name ?? '',
    [`${WEAVE_ATTR_PREFIX}.guardrail.triggered`]: Boolean(spanData.triggered),
  };
}

function speechAttrs(spanData: SpeechSpanData): Attributes {
  return {
    [`${WEAVE_ATTR_PREFIX}.speech.model`]: spanData.model ?? '',
    [`${WEAVE_ATTR_PREFIX}.speech.input`]: spanData.input ?? '',
    [`${WEAVE_ATTR_PREFIX}.speech.output`]: spanData.output?.data ?? '',
    [`${WEAVE_ATTR_PREFIX}.speech.output_format`]:
      spanData.output?.format ?? '',
  };
}

function speechGroupAttrs(spanData: SpeechGroupSpanData): Attributes {
  return {
    [`${WEAVE_ATTR_PREFIX}.speech_group.input`]: spanData.input ?? '',
  };
}

function mcpListToolsAttrs(spanData: MCPListToolsSpanData): Attributes {
  return {
    [`${WEAVE_ATTR_PREFIX}.mcp.server`]: spanData.server ?? '',
    [`${WEAVE_ATTR_PREFIX}.mcp.result`]: spanData.result ?? [],
  };
}

/**
 * Surface CustomSpan data under `weave.openai_agents.custom.*`. Each
 * non-null key in `spanData.data` becomes its own attribute so users can
 * filter / aggregate on individual fields. Null/undefined values are
 * dropped to keep the wire format clean.
 */
function customAttrs(spanData: CustomSpanData): Attributes {
  const out: Attributes = {};
  for (const [key, value] of Object.entries(spanData.data ?? {})) {
    if (value === null || value === undefined) continue;
    out[`${WEAVE_ATTR_PREFIX}.custom.${key}`] = value;
  }
  return out;
}

function attrsForSpan(span: Span<SpanData>): Attributes {
  switch (span.spanData.type) {
    case 'agent':
      return invokeAgentAttrs(span.spanData);

    case 'function':
      return executeToolAttrs(span.spanData);

    case 'response':
      return responseChatAttrs(span.spanData);

    case 'generation':
      return generationChatAttrs(span.spanData);

    case 'handoff':
      return handoffAttrs(span.spanData);

    case 'guardrail':
      return guardrailAttrs(span.spanData);

    case 'transcription':
      return transcriptionAttrs(span.spanData);

    case 'speech':
      return speechAttrs(span.spanData);

    case 'speech_group':
      return speechGroupAttrs(span.spanData);

    case 'mcp_tools':
      return mcpListToolsAttrs(span.spanData);

    case 'custom':
      return customAttrs(span.spanData);

    default:
      // Unknown span type — still emits an OTel span with the openai
      // trace_id/span_id attrs from onSpanStart, but no per-type semconv.
      // Most likely cause: a new SpanData subtype was added to the SDK that
      // this processor doesn't yet handle.
      return {};
  }
}

type TraceInfo = {
  conversationId: string;

  // Used to sweep through opened spans `onTraceEnd` so we don't leak when
  // the SDK ends a trace without closing every span.
  openSpanIds: string[];
};

type SpanInfo = {
  otelSpan: OtelSpan;
  agentName: string | undefined;
};

/**
 * OTel-emitting TracingProcessor for the OpenAI Agents SDK.
 *
 * Emits one OpenTelemetry span per OpenAI Agents span using GenAI semantic
 * conventions where they apply:
 *
 * - `invoke_agent {gen_ai.agent.name}` (https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/#invoke-agent-client-span)
 * - `execute_tool {gen_ai.tool.name}` (https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/#execute-tool-span)
 * - `chat {gen_ai.request.model}` (https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/#inference)
 *
 * Span types without a clean semantic mapping emit with a descriptive operation name
 * and `weave.openai_agents.*` attributes:
 *
 * - `handoff {from} -> {to}`
 * - `guardrail {name}`
 * - `transcription`
 * - `speech`
 * - `speech_group`
 * - `mcp_list_tools`
 * - `{custom}`
 */
export class WeaveOtelTracingProcessor implements TracingProcessor {
  private spansById = new Map<string, SpanInfo>();
  private tracesById = new Map<string, TraceInfo>();

  private getTraceInfo(traceId: string): TraceInfo {
    let traceInfo = this.tracesById.get(traceId);

    if (!traceInfo) {
      traceInfo = {conversationId: traceId, openSpanIds: []};
      this.tracesById.set(traceId, traceInfo);
    }

    return traceInfo;
  }

  private tracer() {
    return getWeaveTracer(TRACER_NAME);
  }

  /**
   * Build an OTel context bound to this span's parent. Returns `undefined`
   * when no parent OTel span exists — the new span then becomes the OTel
   * root for the trace.
   */
  private parentContext(span: Span<SpanData>): OtelContext | undefined {
    if (!span.parentId) return undefined;
    const parent = this.spansById.get(span.parentId);
    if (!parent) return undefined;
    return otelTrace.setSpan(otelContext.active(), parent.otelSpan);
  }

  async onTraceStart(trace: Trace): Promise<void> {
    const traceInfo = this.getTraceInfo(trace.traceId);
    traceInfo.conversationId = trace.groupId ?? trace.traceId;
  }

  async onTraceEnd(trace: Trace): Promise<void> {
    const traceInfo = this.getTraceInfo(trace.traceId);
    const openSpanIds = traceInfo.openSpanIds;
    // Sweep in LIFO order so child spans end before their parents.
    for (const spanId of openSpanIds.reverse()) {
      const span = this.spansById.get(spanId);
      if (!span) continue;

      this.spansById.delete(spanId);
      if (span.otelSpan.isRecording()) {
        span.otelSpan.end();
      }
    }
    this.tracesById.delete(trace.traceId);
  }

  async onSpanStart(span: Span<SpanData>): Promise<void> {
    const parentCtx = this.parentContext(span);
    const otelSpan = this.tracer().startSpan(
      otelSpanName(span),
      {startTime: isoToMs(span.startedAt)},
      parentCtx
    );
    otelSpan.setAttribute(`${WEAVE_ATTR_PREFIX}.span_id`, span.spanId);
    otelSpan.setAttribute(`${WEAVE_ATTR_PREFIX}.trace_id`, span.traceId);

    this.spansById.set(span.spanId, {
      otelSpan,
      agentName: this.resolveAgentName(span),
    });

    const traceInfo = this.getTraceInfo(span.traceId);
    traceInfo.openSpanIds.push(span.spanId);
  }

  private resolveAgentName(span: Span<SpanData>): string | undefined {
    if (span.spanData.type === 'agent') {
      return span.spanData.name;
    }

    if (span.parentId) {
      const parentSpanInfo = this.spansById.get(span.parentId);
      if (parentSpanInfo) {
        return parentSpanInfo.agentName;
      }
    }
  }

  async onSpanEnd(span: Span<SpanData>): Promise<void> {
    const spanInfo = this.spansById.get(span.spanId);
    if (!spanInfo) return;
    const {otelSpan, agentName} = spanInfo;

    this.spansById.delete(span.spanId);

    const traceInfo = this.getTraceInfo(span.traceId);

    traceInfo.openSpanIds = traceInfo.openSpanIds.filter(
      id => id != span.spanId
    );

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

      otelSpan.setAttributes({
        ...attrsForSpan(span),
        [ATTR_GEN_AI_CONVERSATION_ID]: traceInfo.conversationId,
        [ATTR_GEN_AI_AGENT_NAME]: agentName,
      });

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
    for (const {otelSpan} of this.spansById.values()) {
      if (otelSpan.isRecording()) {
        otelSpan.end();
      }
    }
    this.spansById.clear();
    this.tracesById.clear();
  }
}
