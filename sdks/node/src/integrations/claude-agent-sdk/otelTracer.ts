/**
 * OpenTelemetry (GenAI) tracer for the Claude Agent SDK.
 *
 * Emits GenAI-semconv agent spans through the shared Weave GenAI tracer, which
 * targets `/agents/otel/v1/traces` on the trace server (the Agents tab) — the
 * same substrate the pi-coding-agent and OpenAI-Agents OTel integrations use.
 * This is the integration's sole emission path; `wrapQuery` drives it for every
 * `query()` call.
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
  type Attributes,
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
import type {
  ModelUsage,
  NonNullableUsage,
  SDKAssistantMessage,
  SDKMessage,
  SDKResultMessage,
  SDKUserMessage,
  SDKUserMessageReplay,
} from '@anthropic-ai/claude-agent-sdk';
import {toWeaveUsage} from './messages';

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
        parts.push({type: 'reasoning', content: block.thinking});
        break;
      case 'text':
        parts.push({type: 'text', content: block.text});
        break;
      case 'tool_use':
        parts.push({
          type: 'tool_call',
          toolCallId: block.id,
          toolName: block.name,
          arguments: JSON.stringify(block.input ?? {}),
        });
        break;
      default:
        break;
    }
  }
  return parts;
}

/** The `tool_result` block carried on a user message, taken from the SDK type. */
type ToolResultBlock = Extract<
  SDKUserMessage['message']['content'][number],
  {type: 'tool_result'}
>;

/** Stringify tool-result content (string or content-block array). */
function toolResultText(content: ToolResultBlock['content']): string {
  if (!content) {
    return '';
  }
  if (typeof content === 'string') {
    return content;
  }
  // `content` is an array of content blocks here; keep the text parts.
  const text = content
    .map(block => (block.type === 'text' ? block.text : ''))
    .filter(Boolean)
    .join('\n');
  return text || JSON.stringify(content);
}

/**
 * Map one model's SDK usage object to the scalar `gen_ai.usage.*` span
 * attributes. {@link toWeaveUsage} normalizes both the camelCase per-model
 * `modelUsage` values and the snake_case aggregate `usage`.
 *
 * `input_tokens` is emitted as the FULL prompt — fresh + cache-read +
 * cache-creation — see the folding note below.
 */
function usageAttributes(
  rawUsage: ModelUsage | NonNullableUsage
): Record<string, number> {
  // toWeaveUsage returns the typed WeaveUsage shape, where every token field is
  // a required number on both SDK casings — no nullish guards needed.
  const usage = toWeaveUsage(rawUsage);

  // Anthropic reports `input_tokens` disjoint from the cache counts (fresh,
  // uncached tokens only). Weave's canonical convention — matching OpenAI and
  // the trace server's cost formula
  // `(input_tokens - cache_read - cache_creation) * prompt_cost` — is that
  // `input_tokens` is the FULL prompt, with cache_read/cache_creation as subsets
  // of it. Fold the cache counts in so this integration's usage is comparable
  // across providers: per-token cost stays correct and the cache-hit-rate
  // denominator (`cache_read / input_tokens`) lands in [0, 1] instead of blowing
  // up when the cached share dwarfs the fresh tokens.
  const input =
    usage.input_tokens +
    usage.cache_read_input_tokens +
    usage.cache_creation_input_tokens;
  const output = usage.output_tokens;

  return {
    [ATTR_GEN_AI_USAGE_INPUT_TOKENS]: input,
    [ATTR_GEN_AI_USAGE_OUTPUT_TOKENS]: output,
    [ATTR_GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS]: usage.cache_read_input_tokens,
    [ATTR_GEN_AI_USAGE_CACHE_CREATION_INPUT_TOKENS]:
      usage.cache_creation_input_tokens,
    [ATTR_GEN_AI_USAGE_TOTAL_TOKENS]: input + output,
  };
}

/**
 * The error message for a finished run, or undefined if it succeeded. A thrown
 * stream error wins; then a non-success terminal subtype surfaces its `errors`,
 * then a result flagged `is_error` surfaces its text. Returns a string (possibly
 * empty) exactly when the run errored, so callers branch on `!= null`. This
 * broadens the Python integration's `is_error`-only check so failed runs
 * (error_max_turns, error_during_execution, …) also surface as errors.
 */
function runErrorMessage(
  error: unknown,
  result?: SDKResultMessage
): string | undefined {
  if (error instanceof Error) {
    return error.message;
  }
  if (error != null) {
    return String(error);
  }
  // `result` and `errors` live on opposite members of the union; narrow on
  // `subtype` to read either.
  if (result && result.subtype !== 'success') {
    return result.errors.join('; ');
  }
  if (result?.is_error) {
    return result.result;
  }
  return undefined;
}

type ClaudeAgentOtelTracerOptions = {
  /** The user prompt, when invoked as a string (recorded as input on the root). */
  prompt?: string;
  /**
   * The main-thread agent name (`options.agent`), used as `gen_ai.agent.name` —
   * the key the Agents-tab usage rollup groups on. Falls back to the integration
   * name `claude_agent_sdk` when the caller didn't name an agent.
   */
  agent?: string;
};

export class ClaudeAgentOtelTracer {
  private readonly tracer: Tracer;
  private readonly agentName: string;
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
    this.tracer = getWeaveTracer(TRACER_NAME);

    // gen_ai.agent.name follows the caller's main-thread `options.agent` when
    // set (the Agents-tab usage rollup groups on it), falling back to the
    // integration name. The span name and integration.name stay the constant.
    this.agentName = opts.agent || AGENT_NAME;

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
          [ATTR_GEN_AI_AGENT_NAME]: this.agentName,
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
    const sessionId = msg.session_id;
    if (this.conversationId == null && sessionId) {
      this.conversationId = sessionId;
      this.invokeAgentSpan.setAttribute(ATTR_GEN_AI_CONVERSATION_ID, sessionId);
    }

    switch (msg.type) {
      case 'assistant':
        this.processAssistant(msg);
        break;
      case 'user':
        this.processUser(msg);
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

    // Late-bind the conversation id from the result if no earlier message
    // carried a session_id (e.g. a result-only stream), so the turn still
    // groups into its session.
    if (this.conversationId == null && result?.session_id) {
      this.conversationId = result.session_id;
      this.invokeAgentSpan.setAttribute(
        ATTR_GEN_AI_CONVERSATION_ID,
        result.session_id
      );
    }

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
      // Emit per-model usage on child spans and let the trace server cost and
      // roll it up, rather than summing on the client. See
      // {@link emitModelUsageSpans}.
      this.emitModelUsageSpans(result);

      // Both result members carry these as required numbers.
      this.invokeAgentSpan.setAttribute(ATTR_COST_USD, result.total_cost_usd);
      this.invokeAgentSpan.setAttribute(ATTR_NUM_TURNS, result.num_turns);
      // `result` is the final assistant text, present only on the success member.
      if (result.subtype === 'success') {
        const output: Message[] = [{role: 'assistant', content: result.result}];
        this.invokeAgentSpan.setAttribute(
          ATTR_GEN_AI_OUTPUT_MESSAGES,
          JSON.stringify(output)
        );
      }
    }

    // Mark the root failed on a thrown stream error, a non-success terminal
    // subtype, or an is_error result. runErrorMessage returns a string exactly
    // when the run errored.
    const errorMessage = runErrorMessage(error, result);
    if (errorMessage != null) {
      this.invokeAgentSpan.setAttribute(ATTR_ERROR_TYPE, 'agent_error');
      this.invokeAgentSpan.setStatus({
        code: SpanStatusCode.ERROR,
        message: errorMessage || 'Conversation ended with error',
      });
    }

    this.invokeAgentSpan.end();
  }

  // The conversation/session id, attached to child spans only once it's known.
  private conversationAttrs(): Attributes {
    return this.conversationId
      ? {[ATTR_GEN_AI_CONVERSATION_ID]: this.conversationId}
      : {};
  }

  // A `chat` span (CLIENT, child of the root) keyed by model. `extraAttrs`
  // carries the per-model usage from emitModelUsageSpans; processAssistant
  // passes none and sets the response on the returned span directly.
  private startChatSpan(
    model: string | undefined,
    extraAttrs: Attributes = {}
  ): Span {
    return this.tracer.startSpan(
      `chat ${model ?? ''}`.trimEnd(),
      {
        kind: SpanKind.CLIENT,
        attributes: {
          ...CLAUDE_AGENT_SDK_OTEL_ATTRS,
          [ATTR_GEN_AI_OPERATION_NAME]: 'chat',
          // Stamp the agent name on children, not just the root: the per-agent
          // usage rollup groups by `gen_ai.agent.name`, so a usage-bearing
          // `chat` span without it would drop out of the agent's token totals.
          [ATTR_GEN_AI_AGENT_NAME]: this.agentName,
          [ATTR_GEN_AI_PROVIDER_NAME]: PROVIDER_NAME,
          ...(model
            ? {
                [ATTR_GEN_AI_REQUEST_MODEL]: model,
                [ATTR_GEN_AI_RESPONSE_MODEL]: model,
              }
            : {}),
          ...this.conversationAttrs(),
          ...extraAttrs,
        },
      },
      this.invokeAgentCtx
    );
  }

  /**
   * Emit one `chat` span per model carrying that model's token usage, keyed by
   * `gen_ai.response.model`, as children of the root. The trace server keys
   * `summary.usage` on each span's model, costs every model from its own price,
   * and rolls the per-model totals up into the root `invoke_agent` span — so we
   * hand it the SDK's per-model `modelUsage` breakdown verbatim instead of
   * summing on the client, which would collapse a multi-model session onto one
   * model's price and discard the per-model split the server's cost rollup needs.
   *
   * The root carries no token usage of its own, so it isn't double-counted in
   * that descendant rollup; the SDK's authoritative `total_cost_usd` still rides
   * on the root as a reference attribute. Sourcing usage from the result's
   * `modelUsage` (rather than per-assistant-message usage) also captures models
   * the SDK used without emitting an assistant message — e.g. a fast model for
   * an internal step.
   *
   * These usage spans intentionally reuse the `chat <model>` name of the
   * per-message content spans from {@link processAssistant}: the SDK reports
   * usage only in the aggregate result, never per message, so a model that also
   * emitted content ends up with two same-named siblings (one with content and
   * no tokens, one with tokens and no content). They don't double-count — only
   * the usage span carries tokens — but name-based span lookup sees duplicates,
   * so distinguish them by attribute (`gen_ai.output.messages` vs
   * `gen_ai.usage.*`).
   */
  private emitModelUsageSpans(result: SDKResultMessage): void {
    // Prefer the per-model breakdown; fall back to the flat aggregate keyed by
    // the session's primary model when the SDK reports no `modelUsage`.
    const perModel: Array<[string | undefined, ModelUsage | NonNullableUsage]> =
      result.modelUsage && Object.keys(result.modelUsage).length > 0
        ? Object.entries(result.modelUsage)
        : result.usage
          ? [[this.rootModel ?? undefined, result.usage]]
          : [];

    for (const [model, rawUsage] of perModel) {
      const attrs = usageAttributes(rawUsage);
      if (Object.keys(attrs).length === 0) {
        continue;
      }
      this.startChatSpan(model, attrs).end();
    }
  }

  private processAssistant(msg: SDKAssistantMessage): void {
    const model = msg.message.model;
    if (this.rootModel == null && model) {
      this.rootModel = model;
    }

    const content = msg.message.content;

    // Per-chat usage and input messages are intentionally omitted: the SDK only
    // reports aggregate usage in the terminal result (lifted onto the root), and
    // the stream doesn't expose the per-turn input context.
    //
    // One `chat` span per assistant message, carrying the full response
    // (text + reasoning + tool_call parts) as gen_ai.output.messages.
    const chatSpan = this.startChatSpan(model);
    const parts = assistantParts(content);
    if (parts.length > 0) {
      const outputMessage: Message = {role: 'assistant', parts};
      chatSpan.setAttribute(
        ATTR_GEN_AI_OUTPUT_MESSAGES,
        JSON.stringify([outputMessage])
      );
    }
    if (msg.message.stop_reason) {
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
      const toolSpan = this.tracer.startSpan(
        `execute_tool ${block.name}`,
        {
          kind: SpanKind.INTERNAL,
          attributes: {
            ...CLAUDE_AGENT_SDK_OTEL_ATTRS,
            [ATTR_GEN_AI_OPERATION_NAME]: 'execute_tool',
            // Carry the agent name too (see startChatSpan) so tool spans group
            // with their agent in the per-agent rollups.
            [ATTR_GEN_AI_AGENT_NAME]: this.agentName,
            [ATTR_GEN_AI_TOOL_NAME]: block.name,
            [ATTR_GEN_AI_TOOL_CALL_ID]: block.id,
            [ATTR_GEN_AI_TOOL_CALL_ARGUMENTS]: JSON.stringify(
              block.input ?? {}
            ),
            ...this.conversationAttrs(),
          },
        },
        this.invokeAgentCtx
      );
      this.openToolSpans.set(block.id, toolSpan);
    }
  }

  private processUser(msg: SDKUserMessage | SDKUserMessageReplay): void {
    const content = Array.isArray(msg.message.content)
      ? msg.message.content
      : [];
    for (const block of content) {
      if (block.type !== 'tool_result') {
        continue;
      }
      const span = this.openToolSpans.get(block.tool_use_id);
      if (!span) {
        continue;
      }
      this.openToolSpans.delete(block.tool_use_id);
      const resultText = toolResultText(block.content);
      span.setAttribute(ATTR_GEN_AI_TOOL_CALL_RESULT, resultText);
      if (block.is_error) {
        span.setAttribute(ATTR_ERROR_TYPE, 'tool_error');
        span.setStatus({
          code: SpanStatusCode.ERROR,
          message: resultText,
        });
      }
      span.end();
    }
  }
}
