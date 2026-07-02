/**
 * Weave OTEL integration for the pi.dev coding agent.
 *
 * Registers as a pi coding agent extension and emits OpenTelemetry spans for
 * the full agent lifecycle, conforming to the GenAI semantic conventions:
 * https://opentelemetry.io/docs/specs/semconv/gen-ai/
 *
 * Spans are exported through the shared Weave GenAI tracer, which targets
 * `/agents/otel/v1/traces` on the trace server.
 *
 * Usage:
 * ```typescript
 * import { init, createOtelExtension } from 'weave';
 *
 * import {
 *   createAgentSession,
 *   DefaultResourceLoader,
 *   SessionManager,
 *   getAgentDir,
 * } from '@earendil-works/pi-coding-agent';
 *
 * await init('my-entity/my-project');
 *
 * const resourceLoader = new DefaultResourceLoader({
 *   cwd: process.cwd(),
 *   agentDir: getAgentDir(),
 *   extensionFactories: [createOtelExtension()],
 * });
 * await resourceLoader.reload();
 *
 * const { session } = await createAgentSession({
 *   resourceLoader,
 *   sessionManager: SessionManager.inMemory(),
 * });
 *
 * await session.bindExtensions({});
 *
 * await session.prompt('What files are in the current directory?');
 *
 * ```
 */

import {
  type Context,
  type Span,
  type Tracer,
  ROOT_CONTEXT,
  SpanKind,
  SpanStatusCode,
  trace,
} from '@opentelemetry/api';

import {getWeaveTracer} from '../genai/provider';
import {
  ATTR_ERROR_TYPE,
  ATTR_GEN_AI_AGENT_NAME,
  ATTR_GEN_AI_CONVERSATION_ID,
  ATTR_GEN_AI_INPUT_MESSAGES,
  ATTR_GEN_AI_OPERATION_NAME,
  ATTR_GEN_AI_OUTPUT_MESSAGES,
  ATTR_GEN_AI_PROVIDER_NAME,
  ATTR_GEN_AI_REQUEST_MODEL,
  ATTR_GEN_AI_RESPONSE_FINISH_REASONS,
  ATTR_GEN_AI_RESPONSE_MODEL,
  ATTR_GEN_AI_SYSTEM_INSTRUCTIONS,
  ATTR_GEN_AI_TOOL_CALL_ARGUMENTS,
  ATTR_GEN_AI_TOOL_CALL_ID,
  ATTR_GEN_AI_TOOL_CALL_RESULT,
  ATTR_GEN_AI_TOOL_NAME,
  ATTR_GEN_AI_USAGE_CACHE_CREATION_INPUT_TOKENS,
  ATTR_GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS,
  ATTR_GEN_AI_USAGE_INPUT_TOKENS,
  ATTR_GEN_AI_USAGE_OUTPUT_TOKENS,
  ATTR_GEN_AI_USAGE_TOTAL_TOKENS,
} from '../genai/semconv';

import {asOtelAttributes, libraryIntegration} from './integrationMetadata';
import type {
  PiAgentMessage,
  PiAssistantMessage,
  PiExtensionApi,
  PiExtensionContext,
  PiExtensionDefinition,
  PiExtensionEvent,
  PiModel,
} from './piCodingAgent.types';

// Integration provenance, flattened once for OTel span attributes (scalars only).
const PI_CODING_AGENT_INTEGRATION_OTEL_ATTRS = asOtelAttributes(
  libraryIntegration('pi_coding_agent', {packageName: '@pi-dev/coding-agent'})
);

// ---------------------------------------------------------------------------
// Options
// ---------------------------------------------------------------------------

/** Options for the pi coding agent OTEL extension. */
export interface OtelExtensionOptions {
  tracer?: Tracer;
  captureContent?: boolean;
}

// ---------------------------------------------------------------------------
// Attribute keys — GenAI semconv keys from common, pi-specific keys below
// ---------------------------------------------------------------------------

const ATTR_PI_SESSION_CWD = 'pi.session.cwd';
const ATTR_PI_USAGE_COST_USD = 'pi.usage.cost_usd';
const ATTR_PI_COMPACTION_REASON = 'pi.compaction.reason';
const ATTR_PI_COMPACTION_ABORTED = 'pi.compaction.aborted';
const ATTR_PI_COMPACTION_WILL_RETRY = 'pi.compaction.will_retry';
const ATTR_PI_AUTO_RETRY_ATTEMPT = 'auto_retry.attempt';
const ATTR_PI_AUTO_RETRY_MAX_ATTEMPTS = 'auto_retry.max_attempts';
const ATTR_PI_AUTO_RETRY_ERROR_MESSAGE = 'auto_retry.error_message';
const ATTR_PI_AUTO_RETRY_SUCCESS = 'auto_retry.success';
const ATTR_PI_AUTO_RETRY_FINAL_ERROR = 'auto_retry.final_error';

const TRACER_NAME = 'pi-coding-agent';

// ---------------------------------------------------------------------------
// Message shape understood by the Weave GenAI extractor
// (see weave/trace_server/opentelemetry/genai_extraction.py)
// ---------------------------------------------------------------------------

type WeaveMessagePart =
  | {type: 'text'; content: string}
  | {type: 'reasoning'; content: string}
  | {
      type: 'tool_call';
      toolCallId: string;
      toolName: string;
      arguments?: string;
    };

interface WeaveMessage {
  role: string;
  content?: string;
  parts?: WeaveMessagePart[];
  finish_reason?: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Maps a pi provider name to the GenAI semconv gen_ai.provider.name value. */
function resolveGenAiProviderName(provider: string): string {
  const providerName = provider.toLowerCase();
  switch (providerName) {
    case 'anthropic':
      return 'anthropic';
    case 'openai':
    case 'openai-codex':
    case 'github-copilot':
      return 'openai';
    case 'azure-openai-responses':
      return 'azure.ai.openai';
    case 'google':
    case 'google-gemini-cli':
    case 'google-vertex':
      return 'gcp.gemini';
    case 'amazon-bedrock':
      return 'aws.bedrock';
    case 'mistral':
      return 'mistral_ai';
    default:
      return providerName;
  }
}

/** Type assertion: narrows a PiAgentMessage to PiAssistantMessage. */
function isAssistant(msg: PiAgentMessage): msg is PiAssistantMessage {
  return msg.role === 'assistant';
}

function mapAssistantParts(
  content: PiAssistantMessage['content']
): WeaveMessagePart[] {
  return content.map(part => {
    if (part.type === 'text') {
      return {type: 'text', content: part.text};
    }
    if (part.type === 'thinking') {
      return {type: 'reasoning', content: part.thinking};
    }
    // toolCall
    return {
      type: 'tool_call',
      toolCallId: part.id,
      toolName: part.name,
      arguments: safeStringify(part.arguments),
    };
  });
}

function mapPiMessage(msg: PiAgentMessage): WeaveMessage {
  if (isAssistant(msg)) {
    return {
      role: 'assistant',
      parts: mapAssistantParts(msg.content),
      finish_reason: msg.stopReason,
    };
  }
  const content = msg.content;
  return {
    role: msg.role,
    content: typeof content === 'string' ? content : safeStringify(content),
  };
}

function safeStringify(val: unknown): string {
  if (typeof val === 'string') {
    return val;
  }
  try {
    return JSON.stringify(val);
  } catch {
    return String(val);
  }
}

// ---------------------------------------------------------------------------
// Adapter
// ---------------------------------------------------------------------------

/**
 * Attaches to a pi coding agent session via the extension event system and
 * emits OTEL spans for the full agent lifecycle.
 */
export class PiCodingAgentOtelAdapter {
  private readonly tracer: Tracer;
  private readonly captureContent: boolean;

  // Per-prompt span (gen_ai.invoke_agent) — one per user prompt → response
  // cycle. Each is started under ROOT_CONTEXT so every prompt gets its own
  // trace id; sibling prompts in the same conversation are linked via
  // `gen_ai.conversation.id`, not a shared parent span.
  private invokeAgentSpan: Span | null = null;
  private invokeAgentCtx: Context = ROOT_CONTEXT;

  // cwd captured at session_start; stamped on each invoke_agent span as
  // pi.session.cwd.
  private sessionCwd: string | null = null;

  // Per-LLM-turn span (gen_ai.chat) — one per LLM API call within a cycle
  private chatSpan: Span | null = null;

  // Per-tool spans keyed by toolCallId
  private readonly toolSpans = new Map<string, Span>();

  // Current model, updated on model_select events
  private currentModel: PiModel | null = null;

  // Conversation ID for the session — set once in onSessionStart, attached to every span
  private conversationId: string | null = null;

  // Accumulated usage across all turns within the current invoke_agent cycle
  private agentInputTokens = 0;
  private agentOutputTokens = 0;
  private agentTotalTokens = 0;
  private agentCostUsd = 0;

  constructor(opts: OtelExtensionOptions = {}) {
    this.captureContent = opts.captureContent ?? true;

    if (opts.tracer) {
      this.tracer = opts.tracer;
    } else {
      // The shared Weave GenAI tracer targets /agents/otel/v1/traces and
      // owns auth, resource attrs, batching, and beforeExit flush.
      this.tracer = getWeaveTracer(TRACER_NAME);
      // Pi does not await async session_shutdown handlers, so any spans
      // still open when the event loop drains must be ended before the
      // GenAI provider's own beforeExit handler flushes the exporter.
      process.once('beforeExit', () => {
        this.endInvokeAgentSpan();
      });
    }
  }

  /** Returns a pi extension definition for use with createAgentSession({ extensions: [...] }). */
  asExtension(): PiExtensionDefinition {
    return {
      name: 'pi-coding-agent-weave-otel',
      setup: pi => this.setup(pi),
    };
  }

  private setup(pi: PiExtensionApi): void {
    pi.on('session_start', this.onSessionStart);
    pi.on('session_shutdown', this.onSessionShutdown);
    pi.on('model_select', this.onModelSelect);
    pi.on('before_agent_start', this.onBeforeAgentStart);
    pi.on('context', this.onContext);
    pi.on('turn_start', this.onTurnStart);
    pi.on('turn_end', this.onTurnEnd);
    pi.on('agent_end', this.onAgentEnd);
    pi.on('tool_call', this.onToolCall);
    pi.on('tool_result', this.onToolResult);
    pi.on('session_compact', this.onSessionCompact);
    pi.on('auto_retry_start', this.onAutoRetryStart);
    pi.on('auto_retry_end', this.onAutoRetryEnd);
  }

  // ---------------------------------------------------------------------------
  // Event handlers
  // ---------------------------------------------------------------------------

  private onSessionStart = (
    _event: Extract<PiExtensionEvent, {type: 'session_start'}>,
    ctx: PiExtensionContext
  ): void => {
    this.currentModel = ctx.model ?? null;
    this.conversationId = ctx.sessionManager.getSessionId();
    this.sessionCwd = ctx.cwd;
  };

  private onSessionShutdown = (): void => {
    this.endInvokeAgentSpan();
  };

  private onModelSelect = (
    event: Extract<PiExtensionEvent, {type: 'model_select'}>
  ): void => {
    this.currentModel = event.model;
  };

  private onBeforeAgentStart = (
    event: Extract<PiExtensionEvent, {type: 'before_agent_start'}>,
    ctx: PiExtensionContext
  ): void => {
    const model = this.currentModel ?? ctx.model ?? null;
    this.invokeAgentSpan = this.tracer.startSpan(
      'invoke_agent pi-coding-agent',
      {
        kind: SpanKind.INTERNAL,
        attributes: {
          ...PI_CODING_AGENT_INTEGRATION_OTEL_ATTRS,
          [ATTR_GEN_AI_OPERATION_NAME]: 'invoke_agent',
          [ATTR_GEN_AI_AGENT_NAME]: 'pi-coding-agent',
          ...(model
            ? {
                [ATTR_GEN_AI_PROVIDER_NAME]: resolveGenAiProviderName(
                  model.provider
                ),
              }
            : {}),
          ...(this.conversationId
            ? {[ATTR_GEN_AI_CONVERSATION_ID]: this.conversationId}
            : {}),
          ...(this.sessionCwd ? {[ATTR_PI_SESSION_CWD]: this.sessionCwd} : {}),
        },
      },
      ROOT_CONTEXT
    );
    this.invokeAgentCtx = trace.setSpan(ROOT_CONTEXT, this.invokeAgentSpan);
    this.agentInputTokens = 0;
    this.agentOutputTokens = 0;
    this.agentTotalTokens = 0;
    this.agentCostUsd = 0;

    if (this.captureContent) {
      if (event.systemPrompt) {
        this.invokeAgentSpan.setAttribute(
          ATTR_GEN_AI_SYSTEM_INSTRUCTIONS,
          JSON.stringify([event.systemPrompt])
        );
      }
      this.invokeAgentSpan.setAttribute(
        ATTR_GEN_AI_INPUT_MESSAGES,
        JSON.stringify([{role: 'user', content: event.prompt}])
      );
    }
  };

  private onAgentEnd = (
    event: Extract<PiExtensionEvent, {type: 'agent_end'}>
  ): void => {
    if (
      this.captureContent &&
      this.invokeAgentSpan &&
      event.messages.length > 0
    ) {
      const assistantMessages = event.messages
        .filter(m => m.role === 'assistant')
        .map(mapPiMessage);
      if (assistantMessages.length > 0) {
        this.invokeAgentSpan.setAttribute(
          ATTR_GEN_AI_OUTPUT_MESSAGES,
          JSON.stringify(assistantMessages)
        );
      }
    }
    this.endInvokeAgentSpan();
  };

  private onTurnStart = (
    _event: Extract<PiExtensionEvent, {type: 'turn_start'}>,
    ctx: PiExtensionContext
  ): void => {
    const model = this.currentModel ?? ctx.model ?? null;
    const modelId = model?.id ?? 'unknown';
    this.chatSpan = this.tracer.startSpan(
      `chat ${modelId}`,
      {
        kind: SpanKind.CLIENT,
        attributes: {
          ...PI_CODING_AGENT_INTEGRATION_OTEL_ATTRS,
          [ATTR_GEN_AI_OPERATION_NAME]: 'chat',
          ...(model
            ? {
                [ATTR_GEN_AI_PROVIDER_NAME]: resolveGenAiProviderName(
                  model.provider
                ),
                [ATTR_GEN_AI_REQUEST_MODEL]: model.id,
              }
            : {}),
          ...(this.conversationId
            ? {[ATTR_GEN_AI_CONVERSATION_ID]: this.conversationId}
            : {}),
        },
      },
      this.invokeAgentCtx
    );
  };

  private onContext = (
    event: Extract<PiExtensionEvent, {type: 'context'}>
  ): void => {
    if (!this.chatSpan || !this.captureContent) {
      return;
    }
    const systemInstructions: string[] = [];
    const inputMessages: WeaveMessage[] = [];
    for (const msg of event.messages) {
      if (msg.role === 'system') {
        const content = msg.content;
        const text =
          typeof content === 'string' ? content : safeStringify(content);
        if (text) {
          systemInstructions.push(text);
        }
        continue;
      }
      inputMessages.push(mapPiMessage(msg));
    }
    if (systemInstructions.length > 0) {
      this.chatSpan.setAttribute(
        ATTR_GEN_AI_SYSTEM_INSTRUCTIONS,
        JSON.stringify(systemInstructions)
      );
    }
    if (inputMessages.length > 0) {
      this.chatSpan.setAttribute(
        ATTR_GEN_AI_INPUT_MESSAGES,
        JSON.stringify(inputMessages)
      );
    }
  };

  private onTurnEnd = (
    event: Extract<PiExtensionEvent, {type: 'turn_end'}>
  ): void => {
    if (isAssistant(event.message)) {
      const {usage} = event.message;
      this.agentInputTokens += usage.input;
      this.agentOutputTokens += usage.output;
      this.agentTotalTokens += usage.totalTokens;
      this.agentCostUsd += usage.cost.total;

      if (this.chatSpan) {
        this.chatSpan.setAttributes({
          [ATTR_GEN_AI_RESPONSE_MODEL]: event.message.model,
          [ATTR_GEN_AI_RESPONSE_FINISH_REASONS]: [event.message.stopReason],
          [ATTR_GEN_AI_USAGE_INPUT_TOKENS]: usage.input,
          [ATTR_GEN_AI_USAGE_OUTPUT_TOKENS]: usage.output,
          [ATTR_GEN_AI_USAGE_TOTAL_TOKENS]: usage.totalTokens,
          [ATTR_GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS]: usage.cacheRead,
          [ATTR_GEN_AI_USAGE_CACHE_CREATION_INPUT_TOKENS]: usage.cacheWrite,
          [ATTR_PI_USAGE_COST_USD]: usage.cost.total,
        });

        if (this.captureContent) {
          this.chatSpan.setAttribute(
            ATTR_GEN_AI_OUTPUT_MESSAGES,
            JSON.stringify([mapPiMessage(event.message)])
          );
        }

        if (
          event.message.stopReason === 'error' &&
          event.message.errorMessage
        ) {
          this.chatSpan.setAttribute(ATTR_ERROR_TYPE, 'llm_error');
          this.chatSpan.setStatus({
            code: SpanStatusCode.ERROR,
            message: event.message.errorMessage,
          });
        }
      }
    }
    this.endChatSpan();
  };

  private onToolCall = (
    event: Extract<PiExtensionEvent, {type: 'tool_call'}>
  ): void => {
    const attributes: Record<string, string | number | boolean> = {
      ...PI_CODING_AGENT_INTEGRATION_OTEL_ATTRS,
      [ATTR_GEN_AI_OPERATION_NAME]: 'execute_tool',
      [ATTR_GEN_AI_TOOL_NAME]: event.toolName,
      [ATTR_GEN_AI_TOOL_CALL_ID]: event.toolCallId,
    };
    if (this.conversationId) {
      attributes[ATTR_GEN_AI_CONVERSATION_ID] = this.conversationId;
    }
    if (this.captureContent) {
      attributes[ATTR_GEN_AI_TOOL_CALL_ARGUMENTS] = safeStringify(event.input);
    }
    const span = this.tracer.startSpan(
      `execute_tool ${event.toolName}`,
      {kind: SpanKind.INTERNAL, attributes},
      this.invokeAgentCtx
    );
    this.toolSpans.set(event.toolCallId, span);
  };

  private onToolResult = (
    event: Extract<PiExtensionEvent, {type: 'tool_result'}>
  ): void => {
    const span = this.toolSpans.get(event.toolCallId);
    if (!span) {
      return;
    }
    this.toolSpans.delete(event.toolCallId);
    if (event.isError) {
      span.setAttribute(ATTR_ERROR_TYPE, 'tool_error');
      span.setStatus({
        code: SpanStatusCode.ERROR,
        message:
          typeof event.content === 'string'
            ? event.content
            : safeStringify(event.content),
      });
    }
    if (this.captureContent) {
      span.setAttribute(
        ATTR_GEN_AI_TOOL_CALL_RESULT,
        safeStringify(event.content)
      );
    }
    span.end();
  };

  private onSessionCompact = (
    event: Extract<PiExtensionEvent, {type: 'session_compact'}>
  ): void => {
    const span = this.tracer.startSpan(
      'pi.coding_agent.compaction',
      {
        kind: SpanKind.INTERNAL,
        attributes: {
          ...PI_CODING_AGENT_INTEGRATION_OTEL_ATTRS,
          [ATTR_PI_COMPACTION_REASON]: event.reason,
          [ATTR_PI_COMPACTION_ABORTED]: event.aborted,
          [ATTR_PI_COMPACTION_WILL_RETRY]: event.willRetry,
          ...(this.conversationId
            ? {[ATTR_GEN_AI_CONVERSATION_ID]: this.conversationId}
            : {}),
        },
      },
      ROOT_CONTEXT
    );
    span.end();
  };

  private onAutoRetryStart = (
    event: Extract<PiExtensionEvent, {type: 'auto_retry_start'}>
  ): void => {
    this.invokeAgentSpan?.addEvent('auto_retry_start', {
      [ATTR_PI_AUTO_RETRY_ATTEMPT]: event.attempt,
      [ATTR_PI_AUTO_RETRY_MAX_ATTEMPTS]: event.maxAttempts,
      [ATTR_PI_AUTO_RETRY_ERROR_MESSAGE]: event.errorMessage,
    });
  };

  private onAutoRetryEnd = (
    event: Extract<PiExtensionEvent, {type: 'auto_retry_end'}>
  ): void => {
    this.invokeAgentSpan?.addEvent('auto_retry_end', {
      [ATTR_PI_AUTO_RETRY_SUCCESS]: event.success,
      [ATTR_PI_AUTO_RETRY_ATTEMPT]: event.attempt,
      ...(event.finalError
        ? {[ATTR_PI_AUTO_RETRY_FINAL_ERROR]: event.finalError}
        : {}),
    });
  };

  // ---------------------------------------------------------------------------
  // Span lifecycle helpers
  // ---------------------------------------------------------------------------

  private endChatSpan(): void {
    if (this.chatSpan) {
      this.chatSpan.end();
      this.chatSpan = null;
    }
  }

  private endInvokeAgentSpan(): void {
    this.endChatSpan();
    for (const [, span] of this.toolSpans) {
      span.setAttribute(ATTR_ERROR_TYPE, 'aborted');
      span.setStatus({
        code: SpanStatusCode.ERROR,
        message: 'Agent ended with open tool span',
      });
      span.end();
    }
    this.toolSpans.clear();
    if (this.invokeAgentSpan) {
      this.invokeAgentSpan.setAttributes({
        [ATTR_GEN_AI_USAGE_INPUT_TOKENS]: this.agentInputTokens,
        [ATTR_GEN_AI_USAGE_OUTPUT_TOKENS]: this.agentOutputTokens,
        [ATTR_GEN_AI_USAGE_TOTAL_TOKENS]: this.agentTotalTokens,
        [ATTR_PI_USAGE_COST_USD]: this.agentCostUsd,
      });
      this.invokeAgentSpan.end();
      this.invokeAgentSpan = null;
      this.invokeAgentCtx = ROOT_CONTEXT;
    }
  }
}

// ---------------------------------------------------------------------------
// Public factory
// ---------------------------------------------------------------------------

/**
 * Creates a pi coding agent extension that emits OTEL spans for the full
 * agent lifecycle, conforming to the GenAI semantic conventions.
 *
 * When `weave.init(...)` has been called, spans are automatically exported
 * to the Weave trace server at `/agents/otel/v1/traces`. Otherwise, pass a
 * custom `tracer` in `opts`.
 *
 * @example
 * ```typescript
 * const resourceLoader = new DefaultResourceLoader({
 *   extensionFactories: [createOtelExtension()],
 * });
 * ```
 */
export function createOtelExtension(
  opts: OtelExtensionOptions = {}
): (pi: PiExtensionApi) => void {
  const {setup} = new PiCodingAgentOtelAdapter(opts).asExtension();
  return setup;
}

// Re-export types for consumers
export type {
  PiExtensionDefinition,
  PiExtensionContext,
  PiModel,
} from './piCodingAgent.types';
