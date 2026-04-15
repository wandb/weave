/**
 * Weave OTEL integration for the pi.dev coding agent.
 *
 * Registers as a pi coding agent extension and emits OpenTelemetry spans for
 * the full agent lifecycle, conforming to the GenAI semantic conventions:
 * https://opentelemetry.io/docs/specs/semconv/gen-ai/
 *
 * Usage:
 * ```typescript
 * import { init } from 'weave';
 * import { createAgentSession } from '@mariozechner/pi-coding-agent';
 * import { createOtelExtension } from 'weave';
 *
 * await init('my-entity/my-project');
 *
 * const session = await createAgentSession({
 *   extensions: [createOtelExtension()],
 * });
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

import {GEN_AI_ATTR, GEN_AI_EVENT, OTEL_ATTR} from './common/genai';

import type {
  PiAgentMessage,
  PiAssistantMessage,
  PiExtensionApi,
  PiExtensionContext,
  PiExtensionDefinition,
  PiExtensionEvent,
  PiModel,
} from './piCodingAgent.types';

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

const ATTR = {
  ...GEN_AI_ATTR,
  ...OTEL_ATTR,
  // Pi-specific (not in GenAI spec)
  PI_SESSION_CWD: 'pi.session.cwd',
  PI_USAGE_COST_USD: 'pi.usage.cost_usd',
  PI_COMPACTION_REASON: 'pi.compaction.reason',
  PI_COMPACTION_ABORTED: 'pi.compaction.aborted',
  PI_COMPACTION_WILL_RETRY: 'pi.compaction.will_retry',
  PI_AUTO_RETRY_ATTEMPT: 'auto_retry.attempt',
  PI_AUTO_RETRY_MAX_ATTEMPTS: 'auto_retry.max_attempts',
  PI_AUTO_RETRY_ERROR_MESSAGE: 'auto_retry.error_message',
  PI_AUTO_RETRY_SUCCESS: 'auto_retry.success',
  PI_AUTO_RETRY_FINAL_ERROR: 'auto_retry.final_error',
} as const;

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

  // Session-level span
  private sessionSpan: Span | null = null;
  private sessionCtx: Context = ROOT_CONTEXT;

  // Per-prompt span (gen_ai.invoke_agent) — one per user prompt → response cycle
  private invokeAgentSpan: Span | null = null;
  private invokeAgentCtx: Context = ROOT_CONTEXT;

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
    this.tracer = opts.tracer ?? trace.getTracer('pi-coding-agent-weave-ext');
    this.captureContent = opts.captureContent ?? true;
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
    pi.on('message_end', this.onMessageEnd);
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
    this.sessionSpan = this.tracer.startSpan(
      'pi.coding_agent.session',
      {
        kind: SpanKind.INTERNAL,
        attributes: {
          [ATTR.GEN_AI_AGENT_NAME]: 'pi-coding-agent',
          [ATTR.PI_SESSION_CWD]: ctx.cwd,
          [ATTR.GEN_AI_CONVERSATION_ID]: this.conversationId,
        },
      },
      ROOT_CONTEXT
    );
    this.sessionCtx = trace.setSpan(ROOT_CONTEXT, this.sessionSpan);
  };

  private onSessionShutdown = (): void => {
    this.endSessionSpan();
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
          [ATTR.GEN_AI_OPERATION_NAME]: 'invoke_agent',
          [ATTR.GEN_AI_AGENT_NAME]: 'pi-coding-agent',
          ...(model
            ? {
                [ATTR.GEN_AI_PROVIDER_NAME]: resolveGenAiProviderName(
                  model.provider
                ),
              }
            : {}),
          ...(this.conversationId
            ? {[ATTR.GEN_AI_CONVERSATION_ID]: this.conversationId}
            : {}),
        },
      },
      this.sessionCtx
    );
    this.invokeAgentCtx = trace.setSpan(this.sessionCtx, this.invokeAgentSpan);
    this.agentInputTokens = 0;
    this.agentOutputTokens = 0;
    this.agentTotalTokens = 0;
    this.agentCostUsd = 0;

    if (this.captureContent) {
      if (event.systemPrompt) {
        this.invokeAgentSpan.addEvent(GEN_AI_EVENT.SYSTEM_MESSAGE, {
          [GEN_AI_EVENT.CONTENT_ATTR]: JSON.stringify({
            role: 'system',
            content: event.systemPrompt,
          }),
        });
      }
      this.invokeAgentSpan.addEvent(GEN_AI_EVENT.USER_MESSAGE, {
        [GEN_AI_EVENT.CONTENT_ATTR]: JSON.stringify({
          role: 'user',
          content: event.prompt,
        }),
      });
    }
  };

  private onAgentEnd = (): void => {
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
          [ATTR.GEN_AI_OPERATION_NAME]: 'chat',
          ...(model
            ? {
                [ATTR.GEN_AI_PROVIDER_NAME]: resolveGenAiProviderName(
                  model.provider
                ),
                [ATTR.GEN_AI_REQUEST_MODEL]: model.id,
              }
            : {}),
          ...(this.conversationId
            ? {[ATTR.GEN_AI_CONVERSATION_ID]: this.conversationId}
            : {}),
        },
      },
      this.invokeAgentCtx
    );
  };

  private onContext = (
    event: Extract<PiExtensionEvent, {type: 'context'}>
  ): void => {
    if (!this.chatSpan) return;
    const systemMessages = event.messages.filter(m => m.role === 'system');
    if (systemMessages.length === 0) return;
    this.chatSpan.addEvent(
      GEN_AI_EVENT.SYSTEM_MESSAGE,
      this.captureContent
        ? {
            [GEN_AI_EVENT.CONTENT_ATTR]: JSON.stringify(
              systemMessages.map(m => ({role: 'system', content: m.content}))
            ),
          }
        : {}
    );
  };

  private onMessageEnd = (
    event: Extract<PiExtensionEvent, {type: 'message_end'}>
  ): void => {
    if (!this.chatSpan) return;
    if (!isAssistant(event.message)) return;
    this.chatSpan.addEvent(
      GEN_AI_EVENT.ASSISTANT_MESSAGE,
      this.captureContent
        ? {
            [GEN_AI_EVENT.CONTENT_ATTR]: JSON.stringify({
              role: 'assistant',
              content: event.message.content,
            }),
          }
        : {}
    );
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
          [ATTR.GEN_AI_RESPONSE_MODEL]: event.message.model,
          [ATTR.GEN_AI_RESPONSE_FINISH_REASONS]: [event.message.stopReason],
          [ATTR.GEN_AI_USAGE_INPUT_TOKENS]: usage.input,
          [ATTR.GEN_AI_USAGE_OUTPUT_TOKENS]: usage.output,
          [ATTR.GEN_AI_USAGE_TOTAL_TOKENS]: usage.totalTokens,
          [ATTR.GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS]: usage.cacheRead,
          [ATTR.GEN_AI_USAGE_CACHE_CREATION_INPUT_TOKENS]: usage.cacheWrite,
          [ATTR.PI_USAGE_COST_USD]: usage.cost.total,
        });
      }
    }
    this.endChatSpan();
  };

  private onToolCall = (
    event: Extract<PiExtensionEvent, {type: 'tool_call'}>
  ): void => {
    const span = this.tracer.startSpan(
      `execute_tool ${event.toolName}`,
      {
        kind: SpanKind.INTERNAL,
        attributes: {
          [ATTR.GEN_AI_OPERATION_NAME]: 'execute_tool',
          [ATTR.GEN_AI_TOOL_NAME]: event.toolName,
          [ATTR.GEN_AI_TOOL_CALL_ID]: event.toolCallId,
          ...(this.conversationId
            ? {[ATTR.GEN_AI_CONVERSATION_ID]: this.conversationId}
            : {}),
        },
      },
      this.invokeAgentCtx
    );
    this.toolSpans.set(event.toolCallId, span);
  };

  private onToolResult = (
    event: Extract<PiExtensionEvent, {type: 'tool_result'}>
  ): void => {
    const span = this.toolSpans.get(event.toolCallId);
    if (!span) return;
    this.toolSpans.delete(event.toolCallId);
    if (event.isError) {
      span.setAttribute(ATTR.ERROR_TYPE, 'tool_error');
      span.setStatus({
        code: SpanStatusCode.ERROR,
        message:
          typeof event.content === 'string'
            ? event.content
            : JSON.stringify(event.content),
      });
    }
    if (this.captureContent) {
      span.addEvent(GEN_AI_EVENT.TOOL_MESSAGE, {
        [GEN_AI_EVENT.CONTENT_ATTR]: JSON.stringify({
          role: 'tool',
          content: event.content,
        }),
      });
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
          [ATTR.PI_COMPACTION_REASON]: event.reason,
          [ATTR.PI_COMPACTION_ABORTED]: event.aborted,
          [ATTR.PI_COMPACTION_WILL_RETRY]: event.willRetry,
          ...(this.conversationId
            ? {[ATTR.GEN_AI_CONVERSATION_ID]: this.conversationId}
            : {}),
        },
      },
      this.sessionCtx
    );
    span.end();
  };

  private onAutoRetryStart = (
    event: Extract<PiExtensionEvent, {type: 'auto_retry_start'}>
  ): void => {
    this.invokeAgentSpan?.addEvent('auto_retry_start', {
      [ATTR.PI_AUTO_RETRY_ATTEMPT]: event.attempt,
      [ATTR.PI_AUTO_RETRY_MAX_ATTEMPTS]: event.maxAttempts,
      [ATTR.PI_AUTO_RETRY_ERROR_MESSAGE]: event.errorMessage,
    });
  };

  private onAutoRetryEnd = (
    event: Extract<PiExtensionEvent, {type: 'auto_retry_end'}>
  ): void => {
    this.invokeAgentSpan?.addEvent('auto_retry_end', {
      [ATTR.PI_AUTO_RETRY_SUCCESS]: event.success,
      [ATTR.PI_AUTO_RETRY_ATTEMPT]: event.attempt,
      ...(event.finalError
        ? {[ATTR.PI_AUTO_RETRY_FINAL_ERROR]: event.finalError}
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
      span.setAttribute(ATTR.ERROR_TYPE, 'aborted');
      span.setStatus({
        code: SpanStatusCode.ERROR,
        message: 'Agent ended with open tool span',
      });
      span.end();
    }
    this.toolSpans.clear();
    if (this.invokeAgentSpan) {
      this.invokeAgentSpan.setAttributes({
        [ATTR.GEN_AI_USAGE_INPUT_TOKENS]: this.agentInputTokens,
        [ATTR.GEN_AI_USAGE_OUTPUT_TOKENS]: this.agentOutputTokens,
        [ATTR.GEN_AI_USAGE_TOTAL_TOKENS]: this.agentTotalTokens,
        [ATTR.PI_USAGE_COST_USD]: this.agentCostUsd,
      });
      this.invokeAgentSpan.end();
      this.invokeAgentSpan = null;
      this.invokeAgentCtx = ROOT_CONTEXT;
    }
  }

  private endSessionSpan(): void {
    this.endInvokeAgentSpan();
    if (this.sessionSpan) {
      this.sessionSpan.end();
      this.sessionSpan = null;
      this.sessionCtx = ROOT_CONTEXT;
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
 * to the Weave trace server. Otherwise, configure your own TracerProvider
 * before calling this function.
 *
 * @example
 * ```typescript
 * const session = await createAgentSession({
 *   extensions: [createOtelExtension()],
 * });
 * ```
 */
export function createOtelExtension(
  opts: OtelExtensionOptions = {}
): PiExtensionDefinition {
  return new PiCodingAgentOtelAdapter(opts).asExtension();
}

// Re-export types for consumers
export type {
  PiExtensionDefinition,
  PiExtensionContext,
  PiModel,
} from './piCodingAgent.types';
