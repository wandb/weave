/**
 * Weave OTEL integration for the OpenCode coding agent.
 *
 * Registers as an OpenCode plugin and emits OpenTelemetry spans for the full
 * agent lifecycle, conforming to the GenAI semantic conventions:
 * https://opentelemetry.io/docs/specs/semconv/gen-ai/
 *
 * Spans are exported through the shared Weave GenAI tracer, which targets
 * `/agents/otel/v1/traces` on the trace server.
 *
 * Architecture:
 *  - Each user prompt triggers a new `invoke_agent` span (its own trace root).
 *  - Within that, each LLM response creates a `chat` span.
 *  - Tool executions produce `execute_tool` spans.
 *  - Prompts within the same OpenCode session are linked by
 *    `gen_ai.conversation.id` (the session ID).
 *
 * Usage as an OpenCode plugin:
 * ```typescript
 * // .opencode/plugins/weave-tracing.ts
 * import { createOpenCodePlugin } from 'weave';
 *
 * export const WeaveTracing = createOpenCodePlugin({
 *   // Optional: defaults to true
 *   captureContent: true,
 * });
 * ```
 *
 * Or configure via opencode.json:
 * ```json
 * {
 *   "plugin": ["weave"]
 * }
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
  ATTR_GEN_AI_SYSTEM_INSTRUCTIONS,
  ATTR_GEN_AI_TOOL_CALL_ARGUMENTS,
  ATTR_GEN_AI_TOOL_CALL_ID,
  ATTR_GEN_AI_TOOL_CALL_RESULT,
  ATTR_GEN_AI_TOOL_NAME,
  ATTR_GEN_AI_USAGE_INPUT_TOKENS,
  ATTR_GEN_AI_USAGE_OUTPUT_TOKENS,
  ATTR_GEN_AI_USAGE_TOTAL_TOKENS,
} from '../genai/semconv';

import {asOtelAttributes, libraryIntegration} from './integrationMetadata';
import type {
  OpenCodeMessage,
  OpenCodePart,
  OpenCodePartUpdate,
  OpenCodePluginContext,
  OpenCodePluginFactory,
  OpenCodePluginHooks,
  OpenCodeSession,
  OpenCodeSessionStatus,
  OpenCodeToolExecuteAfter,
  OpenCodeToolExecuteBefore,
} from './opencodeCodingAgent.types';

// Integration provenance, flattened once for OTel span attributes.
const OPENCODE_INTEGRATION_OTEL_ATTRS = asOtelAttributes(
  libraryIntegration('opencode', {packageName: 'opencode-ai'})
);

// ---------------------------------------------------------------------------
// Options
// ---------------------------------------------------------------------------

/** Options for the OpenCode Weave plugin. */
export interface OpenCodePluginOptions {
  /** Custom OTel tracer. If omitted, the shared Weave GenAI tracer is used. */
  tracer?: Tracer;
  /**
   * Whether to capture message content and tool arguments/results.
   * Defaults to `true`. Set to `false` for privacy compliance.
   */
  captureContent?: boolean;
  /**
   * Override the agent name stamped on `invoke_agent` spans.
   * Defaults to `'opencode'`.
   */
  agentName?: string;
}

// ---------------------------------------------------------------------------
// Attribute keys — GenAI semconv keys from common, OpenCode-specific keys below
// ---------------------------------------------------------------------------

const ATTR_OPENCODE_SESSION_CWD = 'opencode.session.cwd';
const ATTR_OPENCODE_SESSION_TITLE = 'opencode.session.title';
const ATTR_OPENCODE_TOOL_DURATION_MS = 'opencode.tool.duration_ms';

const TRACER_NAME = 'opencode-coding-agent';

// ---------------------------------------------------------------------------
// Message shape understood by the Weave GenAI extractor
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
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Maps an OpenCode provider ID to the GenAI semconv `gen_ai.provider.name`.
 */
function resolveGenAiProviderName(providerID: string): string {
  const id = providerID.toLowerCase();
  switch (id) {
    case 'anthropic':
      return 'anthropic';
    case 'openai':
      return 'openai';
    case 'google':
    case 'google-genai':
    case 'gemini':
      return 'gcp.gemini';
    case 'azure':
    case 'azure-openai':
      return 'azure.ai.openai';
    case 'mistral':
      return 'mistral_ai';
    case 'bedrock':
    case 'amazon-bedrock':
      return 'aws.bedrock';
    case 'groq':
      return 'groq';
    case 'opencode':
      return 'opencode';
    default:
      return id;
  }
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

/**
 * Convert OpenCode message parts to the Weave GenAI message format.
 */
function mapOpenCodeParts(parts: OpenCodePart[]): WeaveMessagePart[] {
  const mapped: WeaveMessagePart[] = [];
  for (const part of parts) {
    switch (part.type) {
      case 'text':
        mapped.push({type: 'text', content: part.text});
        break;
      case 'reasoning':
        mapped.push({type: 'reasoning', content: part.text});
        break;
      case 'tool-call':
        mapped.push({
          type: 'tool_call',
          toolCallId: part.toolCallId,
          toolName: part.toolName,
          arguments: safeStringify(part.args),
        });
        break;
      // tool-result and file parts are not included in the message parts model
      default:
        break;
    }
  }
  return mapped;
}

/**
 * Build a WeaveMessage from an OpenCode message and its parts.
 */
function mapOpenCodeMessage(role: string, parts: OpenCodePart[]): WeaveMessage {
  const textParts = parts.filter(p => p.type === 'text');
  const mappedParts = mapOpenCodeParts(parts);

  if (mappedParts.length > 0) {
    return {role, parts: mappedParts};
  }
  // Fallback: concatenate text parts
  return {
    role,
    content: textParts.map(p => (p as {text: string}).text).join('\n'),
  };
}

// ---------------------------------------------------------------------------
// Adapter
// ---------------------------------------------------------------------------

/**
 * Attaches to an OpenCode session via the plugin event system and emits OTEL
 * spans for the full agent lifecycle.
 */
export class OpenCodeCodingAgentOtelAdapter {
  private readonly tracer: Tracer;
  private readonly captureContent: boolean;
  private readonly agentName: string;

  // Per-prompt span (gen_ai.invoke_agent) — one per user prompt → response
  // cycle. Each prompt gets its own trace root; sibling prompts are linked
  // via gen_ai.conversation.id.
  private invokeAgentSpan: Span | null = null;
  private invokeAgentCtx: Context = ROOT_CONTEXT;

  // Session metadata
  private conversationId: string | null = null;
  private sessionCwd: string | null = null;
  private sessionTitle: string | null = null;
  private currentModelId: string | null = null;
  private currentProviderId: string | null = null;

  // Per-LLM response span (gen_ai.chat)
  private chatSpan: Span | null = null;

  // Per-tool spans keyed by a synthetic tool call ID
  private readonly toolSpans = new Map<
    string,
    {span: Span; startTime: number}
  >();
  private toolCallCounter = 0;

  // Tracks which messages we've already seen so we can detect new ones
  private processedMessageIds = new Set<string>();

  // Accumulated message parts for the current assistant response
  private currentAssistantParts: OpenCodePart[] = [];

  // Accumulated input messages for the current invoke_agent cycle
  private currentInputMessages: WeaveMessage[] = [];

  constructor(opts: OpenCodePluginOptions = {}) {
    this.captureContent = opts.captureContent ?? true;
    this.agentName = opts.agentName ?? 'opencode';

    if (opts.tracer) {
      this.tracer = opts.tracer;
    } else {
      this.tracer = getWeaveTracer(TRACER_NAME);
      process.once('beforeExit', () => {
        this.endInvokeAgentSpan();
      });
    }
  }

  /**
   * Returns an OpenCode plugin hooks object that can be returned from a plugin
   * factory function.
   */
  buildHooks(): OpenCodePluginHooks {
    return {
      event: event => this.onEvent(event),
      'tool.execute.before': (input, _output) =>
        this.onToolExecuteBefore(input),
      'tool.execute.after': (input, _output) => this.onToolExecuteAfter(input),
    };
  }

  // ---------------------------------------------------------------------------
  // Event routing
  // ---------------------------------------------------------------------------

  onEvent(event: {type: string; properties: Record<string, unknown>}): void {
    switch (event.type) {
      case 'session.created':
        this.onSessionCreated(event.properties as unknown as OpenCodeSession);
        break;
      case 'session.updated':
        this.onSessionUpdated(event.properties as unknown as OpenCodeSession);
        break;
      case 'session.status':
        this.onSessionStatus(
          event.properties as unknown as OpenCodeSessionStatus
        );
        break;
      case 'session.idle':
        this.onSessionIdle(event.properties as {sessionID: string});
        break;
      case 'session.error':
        this.onSessionError(
          event.properties as {sessionID: string; error: string}
        );
        break;
      case 'session.deleted':
        this.onSessionDeleted(event.properties as {sessionID: string});
        break;
      case 'session.compacted':
        this.onSessionCompacted(event.properties as {sessionID: string});
        break;
      case 'message.updated':
        this.onMessageUpdated(event.properties as unknown as OpenCodeMessage);
        break;
      case 'message.part.updated':
        this.onMessagePartUpdated(
          event.properties as unknown as OpenCodePartUpdate
        );
        break;
      default:
        break;
    }
  }

  // ---------------------------------------------------------------------------
  // Session lifecycle handlers
  // ---------------------------------------------------------------------------

  private onSessionCreated(session: OpenCodeSession): void {
    this.conversationId = session.id;
    this.sessionTitle = session.title ?? null;
    if (session.modelID) {
      this.currentModelId = session.modelID;
    }
    if (session.providerID) {
      this.currentProviderId = session.providerID;
    }
  }

  private onSessionUpdated(session: OpenCodeSession): void {
    if (session.title) {
      this.sessionTitle = session.title;
    }
    if (session.modelID) {
      this.currentModelId = session.modelID;
    }
    if (session.providerID) {
      this.currentProviderId = session.providerID;
    }
  }

  private onSessionStatus(status: OpenCodeSessionStatus): void {
    if (status.status === 'running' && !this.invokeAgentSpan) {
      // A new agent cycle is starting
      this.startInvokeAgentSpan();
    }
  }

  private onSessionIdle(_props: {sessionID: string}): void {
    // Session went idle — the current agent cycle is complete
    this.endInvokeAgentSpan();
  }

  private onSessionError(props: {sessionID: string; error: string}): void {
    if (this.invokeAgentSpan) {
      this.invokeAgentSpan.setAttribute(ATTR_ERROR_TYPE, 'session_error');
      this.invokeAgentSpan.setStatus({
        code: SpanStatusCode.ERROR,
        message: props.error,
      });
    }
    this.endInvokeAgentSpan();
  }

  private onSessionDeleted(_props: {sessionID: string}): void {
    this.endInvokeAgentSpan();
    this.conversationId = null;
  }

  private onSessionCompacted(props: {sessionID: string}): void {
    // Emit a compaction span as a root span (not nested under invoke_agent)
    const span = this.tracer.startSpan(
      'opencode.compaction',
      {
        kind: SpanKind.INTERNAL,
        attributes: {
          ...OPENCODE_INTEGRATION_OTEL_ATTRS,
          ...(this.conversationId
            ? {[ATTR_GEN_AI_CONVERSATION_ID]: this.conversationId}
            : {}),
        },
      },
      ROOT_CONTEXT
    );
    span.end();
  }

  // ---------------------------------------------------------------------------
  // Message handlers
  // ---------------------------------------------------------------------------

  private onMessageUpdated(message: OpenCodeMessage): void {
    if (this.processedMessageIds.has(message.id)) {
      return;
    }
    this.processedMessageIds.add(message.id);

    if (message.role === 'user') {
      // A new user message means a new invoke_agent cycle is starting.
      // If there's an existing cycle, end it first.
      if (this.invokeAgentSpan) {
        this.endInvokeAgentSpan();
      }
      this.startInvokeAgentSpan();
    } else if (message.role === 'assistant') {
      // Start a new chat span for the assistant response
      this.endChatSpan();
      this.currentAssistantParts = [];
      this.startChatSpan();
    }
  }

  private onMessagePartUpdated(update: OpenCodePartUpdate): void {
    const part = update.part;

    if (part.type === 'text' || part.type === 'reasoning') {
      // Accumulate assistant response parts
      this.currentAssistantParts.push(part);
    } else if (part.type === 'tool-call') {
      // Tool calls are tracked via the tool.execute.before/after hooks,
      // but we still accumulate them for the chat span's output messages.
      this.currentAssistantParts.push(part);
    }
  }

  // ---------------------------------------------------------------------------
  // Tool handlers
  // ---------------------------------------------------------------------------

  onToolExecuteBefore(input: OpenCodeToolExecuteBefore): void {
    const toolCallId = `opencode-tool-${++this.toolCallCounter}`;
    const attributes: Record<string, string | number | boolean> = {
      ...OPENCODE_INTEGRATION_OTEL_ATTRS,
      [ATTR_GEN_AI_OPERATION_NAME]: 'execute_tool',
      [ATTR_GEN_AI_TOOL_NAME]: input.tool,
      [ATTR_GEN_AI_TOOL_CALL_ID]: toolCallId,
    };
    if (this.conversationId) {
      attributes[ATTR_GEN_AI_CONVERSATION_ID] = this.conversationId;
    }
    if (this.captureContent) {
      attributes[ATTR_GEN_AI_TOOL_CALL_ARGUMENTS] = safeStringify(input.args);
    }

    const span = this.tracer.startSpan(
      `execute_tool ${input.tool}`,
      {kind: SpanKind.INTERNAL, attributes},
      this.invokeAgentCtx
    );

    // Key by session + tool name to match before/after
    const key = `${input.sessionID}:${input.tool}:${this.toolCallCounter}`;
    this.toolSpans.set(key, {span, startTime: Date.now()});

    // Store the key on the input object so onToolExecuteAfter can find it.
    // We use the counter-based key approach since OpenCode doesn't provide
    // a stable tool call ID across before/after hooks.
    (input as any).__weaveToolKey = key;
  }

  onToolExecuteAfter(input: OpenCodeToolExecuteAfter): void {
    // Find the matching tool span — try the stashed key first, then scan
    const key = (input as any).__weaveToolKey as string | undefined;
    let entry: {span: Span; startTime: number} | undefined;

    if (key) {
      entry = this.toolSpans.get(key);
      if (entry) {
        this.toolSpans.delete(key);
      }
    }

    // Fallback: find the most recent span for this tool name
    if (!entry) {
      for (const [k, v] of this.toolSpans) {
        if (k.includes(`:${input.tool}:`)) {
          entry = v;
          this.toolSpans.delete(k);
          break;
        }
      }
    }

    if (!entry) {
      return;
    }

    const {span, startTime} = entry;
    const durationMs = Date.now() - startTime;
    span.setAttribute(ATTR_OPENCODE_TOOL_DURATION_MS, durationMs);

    if (input.error) {
      span.setAttribute(ATTR_ERROR_TYPE, 'tool_error');
      span.setStatus({
        code: SpanStatusCode.ERROR,
        message: input.error,
      });
    }
    if (this.captureContent) {
      span.setAttribute(
        ATTR_GEN_AI_TOOL_CALL_RESULT,
        safeStringify(input.result)
      );
    }
    span.end();
  }

  // ---------------------------------------------------------------------------
  // Span lifecycle helpers
  // ---------------------------------------------------------------------------

  private startInvokeAgentSpan(): void {
    const attributes: Record<string, string | number | boolean> = {
      ...OPENCODE_INTEGRATION_OTEL_ATTRS,
      [ATTR_GEN_AI_OPERATION_NAME]: 'invoke_agent',
      [ATTR_GEN_AI_AGENT_NAME]: this.agentName,
    };
    if (this.conversationId) {
      attributes[ATTR_GEN_AI_CONVERSATION_ID] = this.conversationId;
    }
    if (this.currentProviderId) {
      attributes[ATTR_GEN_AI_PROVIDER_NAME] = resolveGenAiProviderName(
        this.currentProviderId
      );
    }
    if (this.sessionCwd) {
      attributes[ATTR_OPENCODE_SESSION_CWD] = this.sessionCwd;
    }
    if (this.sessionTitle) {
      attributes[ATTR_OPENCODE_SESSION_TITLE] = this.sessionTitle;
    }

    this.invokeAgentSpan = this.tracer.startSpan(
      `invoke_agent ${this.agentName}`,
      {kind: SpanKind.INTERNAL, attributes},
      ROOT_CONTEXT
    );
    this.invokeAgentCtx = trace.setSpan(ROOT_CONTEXT, this.invokeAgentSpan);
    this.currentInputMessages = [];
    this.currentAssistantParts = [];
    this.processedMessageIds.clear();
  }

  private startChatSpan(): void {
    const modelId = this.currentModelId ?? 'unknown';
    const attributes: Record<string, string | number | boolean> = {
      ...OPENCODE_INTEGRATION_OTEL_ATTRS,
      [ATTR_GEN_AI_OPERATION_NAME]: 'chat',
    };
    if (this.currentProviderId) {
      attributes[ATTR_GEN_AI_PROVIDER_NAME] = resolveGenAiProviderName(
        this.currentProviderId
      );
    }
    if (this.currentModelId) {
      attributes[ATTR_GEN_AI_REQUEST_MODEL] = this.currentModelId;
    }
    if (this.conversationId) {
      attributes[ATTR_GEN_AI_CONVERSATION_ID] = this.conversationId;
    }

    this.chatSpan = this.tracer.startSpan(
      `chat ${modelId}`,
      {kind: SpanKind.CLIENT, attributes},
      this.invokeAgentCtx
    );
  }

  private endChatSpan(): void {
    if (this.chatSpan) {
      // Set output messages from accumulated assistant parts
      if (this.captureContent && this.currentAssistantParts.length > 0) {
        const outputMsg = mapOpenCodeMessage(
          'assistant',
          this.currentAssistantParts
        );
        this.chatSpan.setAttribute(
          ATTR_GEN_AI_OUTPUT_MESSAGES,
          JSON.stringify([outputMsg])
        );
      }
      this.chatSpan.end();
      this.chatSpan = null;
    }
  }

  endInvokeAgentSpan(): void {
    this.endChatSpan();

    // End any remaining tool spans
    for (const [, {span}] of this.toolSpans) {
      span.setAttribute(ATTR_ERROR_TYPE, 'aborted');
      span.setStatus({
        code: SpanStatusCode.ERROR,
        message: 'Agent ended with open tool span',
      });
      span.end();
    }
    this.toolSpans.clear();

    if (this.invokeAgentSpan) {
      // Set output messages on the invoke_agent span
      if (this.captureContent && this.currentAssistantParts.length > 0) {
        const outputMsg = mapOpenCodeMessage(
          'assistant',
          this.currentAssistantParts
        );
        this.invokeAgentSpan.setAttribute(
          ATTR_GEN_AI_OUTPUT_MESSAGES,
          JSON.stringify([outputMsg])
        );
      }

      this.invokeAgentSpan.end();
      this.invokeAgentSpan = null;
      this.invokeAgentCtx = ROOT_CONTEXT;
    }

    this.currentAssistantParts = [];
    this.currentInputMessages = [];
  }

  // ---------------------------------------------------------------------------
  // Public methods for direct manipulation (useful in tests and advanced usage)
  // ---------------------------------------------------------------------------

  /** Set input messages for the current invoke_agent span. */
  setInputMessages(messages: WeaveMessage[]): void {
    if (this.captureContent && this.invokeAgentSpan) {
      this.invokeAgentSpan.setAttribute(
        ATTR_GEN_AI_INPUT_MESSAGES,
        JSON.stringify(messages)
      );
    }
  }

  /** Set system instructions for the current invoke_agent span. */
  setSystemInstructions(instructions: string[]): void {
    if (this.captureContent && this.invokeAgentSpan) {
      this.invokeAgentSpan.setAttribute(
        ATTR_GEN_AI_SYSTEM_INSTRUCTIONS,
        JSON.stringify(instructions)
      );
    }
  }

  /** Set the working directory for the session. */
  setSessionCwd(cwd: string): void {
    this.sessionCwd = cwd;
    if (this.invokeAgentSpan) {
      this.invokeAgentSpan.setAttribute(ATTR_OPENCODE_SESSION_CWD, cwd);
    }
  }

  /** Check whether the adapter has an active invoke_agent span. */
  get isActive(): boolean {
    return this.invokeAgentSpan !== null;
  }
}

// ---------------------------------------------------------------------------
// Public factory
// ---------------------------------------------------------------------------

/**
 * Creates an OpenCode plugin that emits OTEL spans for the full agent lifecycle,
 * conforming to the GenAI semantic conventions.
 *
 * When `weave.init(...)` has been called before the plugin loads, spans are
 * automatically exported to the Weave trace server at
 * `/agents/otel/v1/traces`. Otherwise, pass a custom `tracer` in `opts`.
 *
 * @example
 * ```typescript
 * // .opencode/plugins/weave-tracing.ts
 * import { createOpenCodePlugin } from 'weave';
 *
 * export const WeaveTracing = createOpenCodePlugin();
 * ```
 *
 * @example
 * ```typescript
 * // Programmatic usage with the SDK
 * import { init, createOpenCodePlugin } from 'weave';
 *
 * await init('my-entity/my-project');
 * const plugin = createOpenCodePlugin({ captureContent: true });
 * // Plugin is a standard OpenCode plugin factory function
 * ```
 */
export function createOpenCodePlugin(
  opts: OpenCodePluginOptions = {}
): OpenCodePluginFactory {
  return async (ctx: OpenCodePluginContext) => {
    const adapter = new OpenCodeCodingAgentOtelAdapter(opts);
    adapter.setSessionCwd(ctx.directory);

    return adapter.buildHooks();
  };
}

// Re-export types for consumers
export type {
  OpenCodePluginContext,
  OpenCodePluginFactory,
  OpenCodePluginHooks,
  OpenCodeSession,
  OpenCodeToolExecuteBefore,
  OpenCodeToolExecuteAfter,
} from './opencodeCodingAgent.types';
