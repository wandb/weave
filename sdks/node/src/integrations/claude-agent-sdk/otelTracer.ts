/**
 * OpenTelemetry (GenAI) tracer for the Claude Agent SDK.
 *
 * The OTel-V2 counterpart of {@link ClaudeAgentTracer}: instead of native Weave
 * calls, it emits GenAI-semconv agent spans through the shared Weave GenAI
 * tracer, which targets `/agents/otel/v1/traces` on the trace server (the
 * Agents tab) — the same substrate the pi-coding-agent and OpenAI-Agents OTel
 * integrations use. Selected by `wrapQuery` when `shouldUseOtelV2()` is true.
 *
 * Span shape, mapped from one `query()` message stream:
 *
 *   invoke_agent claude_agent_sdk            (root, ROOT_CONTEXT)
 *   ├─ chat <model>                          (one per assistant message)
 *   └─ execute_tool <name>                   (one per tool_use → tool_result)
 *
 * Every span carries `gen_ai.conversation.id` (the SDK `session_id`) so the
 * turns of a multi-prompt session group together — the "session" link. Tokens
 * and cost from the result message are lifted onto the root span.
 *
 * Like the pi integration we hold explicit OTel `Span`/`Context` references
 * rather than using the high-level `startTurn`/`startLLM` API: that API tracks
 * the active turn/LLM in AsyncLocalStorage, which does not survive being driven
 * across an async generator's yields by an external consumer.
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

import {getWeaveTracer} from '../../genai/provider';
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
  ATTR_GEN_AI_TOOL_CALL_ARGUMENTS,
  ATTR_GEN_AI_TOOL_CALL_ID,
  ATTR_GEN_AI_TOOL_CALL_RESULT,
  ATTR_GEN_AI_TOOL_NAME,
  ATTR_GEN_AI_USAGE_CACHE_CREATION_INPUT_TOKENS,
  ATTR_GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS,
  ATTR_GEN_AI_USAGE_INPUT_TOKENS,
  ATTR_GEN_AI_USAGE_OUTPUT_TOKENS,
  ATTR_GEN_AI_USAGE_TOTAL_TOKENS,
} from '../../genai/semconv';
import type {Message, MessagePart} from '../../genai';
import {asOtelAttributes, libraryIntegration} from '../integrationMetadata';
import type {AgentTracer} from './tracer';
import {
  toWeaveUsage,
  type SDKAssistantMessage,
  type SDKMessage,
  type SDKResultMessage,
  type SDKUserMessage,
  type TextBlock,
  type ThinkingBlock,
  type ToolResultBlock,
  type ToolUseBlock,
} from './messages';

const TRACER_NAME = 'claude-agent-sdk';
const AGENT_NAME = 'claude_agent_sdk';
// The Claude Agent SDK runs Anthropic models exclusively.
const PROVIDER_NAME = 'anthropic';

// Total cost is provider-reported, not a GenAI-semconv field, so it rides on a
// namespaced attribute (mirrors pi's `pi.usage.cost_usd`).
const ATTR_COST_USD = 'claude_agent_sdk.usage.cost_usd';
const ATTR_NUM_TURNS = 'claude_agent_sdk.num_turns';

// Flattened integration provenance (scalars only) for OTel span attributes.
const CLAUDE_AGENT_SDK_OTEL_ATTRS = asOtelAttributes(
  libraryIntegration(AGENT_NAME, {
    packageName: '@anthropic-ai/claude-agent-sdk',
  })
);

/** Map an assistant message's content blocks to GenAI message parts. */
function assistantParts(
  blocks: SDKAssistantMessage['message']['content']
): MessagePart[] {
  const parts: MessagePart[] = [];
  for (const block of blocks) {
    switch (block.type) {
      case 'thinking':
        parts.push({
          type: 'reasoning',
          content: (block as ThinkingBlock).thinking,
        });
        break;
      case 'text':
        parts.push({type: 'text', content: (block as TextBlock).text});
        break;
      case 'tool_use': {
        const b = block as ToolUseBlock;
        parts.push({
          type: 'tool_call',
          toolCallId: b.id,
          toolName: b.name,
          arguments: JSON.stringify(b.input ?? {}),
        });
        break;
      }
      default:
        break;
    }
  }
  return parts;
}

/** Stringify tool-result content (string, content-block array, or other). */
function toolResultText(result: ToolResultBlock): string {
  const {content} = result;
  if (typeof content === 'string') {
    return content;
  }
  if (Array.isArray(content)) {
    const text = content
      .map(block =>
        block && typeof block === 'object' && 'text' in block
          ? String((block as {text: unknown}).text)
          : ''
      )
      .filter(Boolean)
      .join('\n');
    if (text) {
      return text;
    }
  }
  try {
    return JSON.stringify(content);
  } catch {
    return String(content);
  }
}

/**
 * Sum the per-model `modelUsage` (or fall back to the aggregate `usage`) into
 * Weave's snake_case token keys. Reuses {@link toWeaveUsage} so the
 * camelCase→snake_case handling stays in one place.
 */
function aggregateUsage(result: SDKResultMessage): Record<string, number> {
  const totals: Record<string, number> = {};
  const add = (usage: Record<string, unknown>): void => {
    for (const [key, value] of Object.entries(toWeaveUsage(usage))) {
      if (typeof value === 'number') {
        totals[key] = (totals[key] ?? 0) + value;
      }
    }
  };
  if (result.modelUsage) {
    for (const usage of Object.values(result.modelUsage)) {
      add(usage);
    }
  } else if (result.usage) {
    add(result.usage);
  }
  return totals;
}

export interface ClaudeAgentOtelTracerOptions {
  /** The user prompt, when invoked as a string (recorded as input on the root). */
  prompt?: string;
  /** Tracer override (tests inject one backed by an in-memory exporter). */
  tracer?: Tracer;
}

export class ClaudeAgentOtelTracer implements AgentTracer {
  private readonly tracer: Tracer;
  private readonly invokeAgentSpan: Span;
  private readonly invokeAgentCtx: Context;
  private readonly openToolSpans = new Map<string, Span>();
  private conversationId: string | null = null;
  private rootModel: string | null = null;
  private finished = false;

  constructor(opts: ClaudeAgentOtelTracerOptions = {}) {
    // The shared Weave GenAI tracer targets /agents/otel/v1/traces and owns
    // auth, resource attrs, batching, and beforeExit flush. A no-op tracer is
    // returned when weave.init() hasn't run, so every span call stays safe.
    this.tracer = opts.tracer ?? getWeaveTracer(TRACER_NAME);

    // Root span under ROOT_CONTEXT so each query() is its own trace; sibling
    // prompts in one session are linked via gen_ai.conversation.id, not a
    // shared parent.
    this.invokeAgentSpan = this.tracer.startSpan(
      `invoke_agent ${AGENT_NAME}`,
      {
        kind: SpanKind.INTERNAL,
        attributes: {
          ...CLAUDE_AGENT_SDK_OTEL_ATTRS,
          [ATTR_GEN_AI_OPERATION_NAME]: 'invoke_agent',
          [ATTR_GEN_AI_AGENT_NAME]: AGENT_NAME,
          [ATTR_GEN_AI_PROVIDER_NAME]: PROVIDER_NAME,
        },
      },
      ROOT_CONTEXT
    );
    this.invokeAgentCtx = trace.setSpan(ROOT_CONTEXT, this.invokeAgentSpan);

    if (opts.prompt != null) {
      this.invokeAgentSpan.setAttribute(
        ATTR_GEN_AI_INPUT_MESSAGES,
        JSON.stringify([{role: 'user', content: opts.prompt}])
      );
    }
  }

  processMessage(msg: SDKMessage): void {
    // The SDK stamps session_id on every message; capture it once as the
    // conversation id so the root and its children all carry it.
    const sessionId = (msg as {session_id?: string}).session_id;
    if (this.conversationId == null && sessionId) {
      this.conversationId = sessionId;
      this.invokeAgentSpan.setAttribute(ATTR_GEN_AI_CONVERSATION_ID, sessionId);
    }

    switch (msg.type) {
      case 'assistant':
        this.processAssistant(msg as SDKAssistantMessage);
        break;
      case 'user':
        this.processUser(msg as SDKUserMessage);
        break;
      default:
        break;
    }
  }

  finalize(result?: SDKResultMessage, error?: unknown): void {
    if (this.finished) {
      return;
    }
    this.finished = true;

    // Sweep tool calls left open (interrupted stream or missing tool_result).
    for (const span of this.openToolSpans.values()) {
      span.setAttribute(ATTR_ERROR_TYPE, 'aborted');
      span.setStatus({
        code: SpanStatusCode.ERROR,
        message: 'Agent ended with open tool span',
      });
      span.end();
    }
    this.openToolSpans.clear();

    if (this.rootModel) {
      this.invokeAgentSpan.setAttribute(
        ATTR_GEN_AI_RESPONSE_MODEL,
        this.rootModel
      );
    }

    if (result) {
      const usage = aggregateUsage(result);
      const usageAttrs: Record<string, number> = {};
      if (usage.input_tokens != null) {
        usageAttrs[ATTR_GEN_AI_USAGE_INPUT_TOKENS] = usage.input_tokens;
      }
      if (usage.output_tokens != null) {
        usageAttrs[ATTR_GEN_AI_USAGE_OUTPUT_TOKENS] = usage.output_tokens;
      }
      if (usage.cache_read_input_tokens != null) {
        usageAttrs[ATTR_GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS] =
          usage.cache_read_input_tokens;
      }
      if (usage.cache_creation_input_tokens != null) {
        usageAttrs[ATTR_GEN_AI_USAGE_CACHE_CREATION_INPUT_TOKENS] =
          usage.cache_creation_input_tokens;
      }
      if (usage.input_tokens != null && usage.output_tokens != null) {
        usageAttrs[ATTR_GEN_AI_USAGE_TOTAL_TOKENS] =
          usage.input_tokens + usage.output_tokens;
      }
      this.invokeAgentSpan.setAttributes(usageAttrs);

      if (result.total_cost_usd != null) {
        this.invokeAgentSpan.setAttribute(ATTR_COST_USD, result.total_cost_usd);
      }
      if (result.num_turns != null) {
        this.invokeAgentSpan.setAttribute(ATTR_NUM_TURNS, result.num_turns);
      }
      if (result.result != null) {
        const output: Message[] = [{role: 'assistant', content: result.result}];
        this.invokeAgentSpan.setAttribute(
          ATTR_GEN_AI_OUTPUT_MESSAGES,
          JSON.stringify(output)
        );
      }
    }

    // A thrown stream error, or a non-success terminal subtype, marks the root
    // as failed (mirrors the native-call tracer's broadening of the Python
    // `is_error`-only check).
    const errored =
      error != null ||
      (result != null &&
        (result.is_error ||
          (result.subtype != null && result.subtype !== 'success')));
    if (errored) {
      const message =
        error != null
          ? error instanceof Error
            ? error.message
            : String(error)
          : result?.result ||
            (result?.errors && result.errors.join('; ')) ||
            'Conversation ended with error';
      this.invokeAgentSpan.setAttribute(ATTR_ERROR_TYPE, 'agent_error');
      this.invokeAgentSpan.setStatus({
        code: SpanStatusCode.ERROR,
        message,
      });
    }

    this.invokeAgentSpan.end();
  }

  private processAssistant(msg: SDKAssistantMessage): void {
    const model = msg.message?.model;
    if (this.rootModel == null && model) {
      this.rootModel = model;
    }

    const content = msg.message?.content ?? [];

    // One `chat` span per assistant message, carrying the full response
    // (text + reasoning + tool_call parts) as gen_ai.output.messages.
    const chatSpan = this.tracer.startSpan(
      `chat ${model ?? ''}`.trimEnd(),
      {
        kind: SpanKind.CLIENT,
        attributes: {
          ...CLAUDE_AGENT_SDK_OTEL_ATTRS,
          [ATTR_GEN_AI_OPERATION_NAME]: 'chat',
          [ATTR_GEN_AI_PROVIDER_NAME]: PROVIDER_NAME,
          ...(model ? {[ATTR_GEN_AI_REQUEST_MODEL]: model} : {}),
          ...(model ? {[ATTR_GEN_AI_RESPONSE_MODEL]: model} : {}),
          ...(this.conversationId
            ? {[ATTR_GEN_AI_CONVERSATION_ID]: this.conversationId}
            : {}),
        },
      },
      this.invokeAgentCtx
    );
    const parts = assistantParts(content);
    if (parts.length > 0) {
      const outputMessage: Message = {role: 'assistant', parts};
      chatSpan.setAttribute(
        ATTR_GEN_AI_OUTPUT_MESSAGES,
        JSON.stringify([outputMessage])
      );
    }
    if (msg.message?.stop_reason) {
      chatSpan.setAttribute(ATTR_GEN_AI_RESPONSE_FINISH_REASONS, [
        msg.message.stop_reason,
      ]);
    }
    chatSpan.end();

    // Open an execute_tool span per tool use; closed by its tool_result.
    for (const block of content) {
      if (block.type !== 'tool_use') {
        continue;
      }
      const toolBlock = block as ToolUseBlock;
      const toolSpan = this.tracer.startSpan(
        `execute_tool ${toolBlock.name}`,
        {
          kind: SpanKind.INTERNAL,
          attributes: {
            ...CLAUDE_AGENT_SDK_OTEL_ATTRS,
            [ATTR_GEN_AI_OPERATION_NAME]: 'execute_tool',
            [ATTR_GEN_AI_TOOL_NAME]: toolBlock.name,
            [ATTR_GEN_AI_TOOL_CALL_ID]: toolBlock.id,
            [ATTR_GEN_AI_TOOL_CALL_ARGUMENTS]: JSON.stringify(
              toolBlock.input ?? {}
            ),
            ...(this.conversationId
              ? {[ATTR_GEN_AI_CONVERSATION_ID]: this.conversationId}
              : {}),
          },
        },
        this.invokeAgentCtx
      );
      this.openToolSpans.set(toolBlock.id, toolSpan);
    }
  }

  private processUser(msg: SDKUserMessage): void {
    const content = Array.isArray(msg.message?.content)
      ? msg.message.content
      : [];
    for (const block of content) {
      if (block.type !== 'tool_result') {
        continue;
      }
      const result = block as ToolResultBlock;
      const span = this.openToolSpans.get(result.tool_use_id);
      if (!span) {
        continue;
      }
      this.openToolSpans.delete(result.tool_use_id);
      span.setAttribute(ATTR_GEN_AI_TOOL_CALL_RESULT, toolResultText(result));
      if (result.is_error) {
        span.setAttribute(ATTR_ERROR_TYPE, 'tool_error');
        span.setStatus({
          code: SpanStatusCode.ERROR,
          message: toolResultText(result),
        });
      }
      span.end();
    }
  }
}
