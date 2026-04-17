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

/** Narrows a PiAgentMessage to PiAssistantMessage, or returns undefined. */
function asAssistant(msg: PiAgentMessage): PiAssistantMessage | undefined {
  return msg.role === 'assistant' ? (msg as PiAssistantMessage) : undefined;
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
    _ctx: PiExtensionContext
  ): void => {};

  private onSessionShutdown = (): void => {};

  private onModelSelect = (
    _event: Extract<PiExtensionEvent, {type: 'model_select'}>
  ): void => {};

  private onBeforeAgentStart = (
    _event: Extract<PiExtensionEvent, {type: 'before_agent_start'}>,
    _ctx: PiExtensionContext
  ): void => {};

  private onAgentEnd = (): void => {};

  private onTurnStart = (
    _event: Extract<PiExtensionEvent, {type: 'turn_start'}>,
    _ctx: PiExtensionContext
  ): void => {};

  private onContext = (
    _event: Extract<PiExtensionEvent, {type: 'context'}>
  ): void => {};

  private onMessageEnd = (
    _event: Extract<PiExtensionEvent, {type: 'message_end'}>
  ): void => {};

  private onTurnEnd = (
    _event: Extract<PiExtensionEvent, {type: 'turn_end'}>
  ): void => {};

  private onToolCall = (
    _event: Extract<PiExtensionEvent, {type: 'tool_call'}>
  ): void => {};

  private onToolResult = (
    _event: Extract<PiExtensionEvent, {type: 'tool_result'}>
  ): void => {};

  private onSessionCompact = (
    _event: Extract<PiExtensionEvent, {type: 'session_compact'}>
  ): void => {};

  private onAutoRetryStart = (
    _event: Extract<PiExtensionEvent, {type: 'auto_retry_start'}>
  ): void => {};

  private onAutoRetryEnd = (
    _event: Extract<PiExtensionEvent, {type: 'auto_retry_end'}>
  ): void => {};

  // ---------------------------------------------------------------------------
  // Span lifecycle helpers
  // ---------------------------------------------------------------------------

  private endChatSpan(): void {}

  private endInvokeAgentSpan(): void {}

  private endSessionSpan(): void {}
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
