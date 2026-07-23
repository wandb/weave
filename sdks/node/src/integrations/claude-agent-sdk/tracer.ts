/**
 * Weave GenAI tracer for the Claude Agent SDK.
 *
 * Maps one `query()` message stream onto the high-level Weave TypeScript SDK:
 *
 *   invoke_agent                              (Turn, one trace per query)
 *   ├─ chat                                   (LLM, one per assistant message)
 *   ├─ execute_tool                           (Tool, tool_use → tool_result)
 *   └─ chat                                   (LLM, one usage span per model)
 *
 * The high-level handles emit through the shared Weave GenAI provider to
 * `/agents/otel/v1/traces`. Handles retain explicit parent contexts and
 * conversation metadata, so they remain valid across the async generator's
 * yields. Creation runs in short `runIsolated()` frames to contain the GenAI
 * SDK's ambient-state bookkeeping while multiple queries are in flight.
 */
import type {Attributes} from '@opentelemetry/api';

import {
  runIsolated,
  Turn,
  type Message,
  type MessagePart,
  type Tool,
  type Usage,
} from '../../genai';
import {
  ATTR_ERROR_TYPE,
  ATTR_GEN_AI_AGENT_NAME,
  ATTR_GEN_AI_CONVERSATION_ID,
  ATTR_GEN_AI_OUTPUT_MESSAGES,
  ATTR_GEN_AI_PROVIDER_NAME,
  ATTR_GEN_AI_RESPONSE_MODEL,
  ATTR_GEN_AI_USAGE_TOTAL_TOKENS,
} from '../../genai/semconv';
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

const AGENT_NAME = 'claude_agent_sdk';
// The Claude Agent SDK runs Anthropic models exclusively.
const PROVIDER_NAME = 'anthropic';

// Total cost is provider-reported, not a GenAI-semconv field.
const ATTR_COST_USD = 'claude_agent_sdk.usage.cost_usd';
const ATTR_NUM_TURNS = 'claude_agent_sdk.num_turns';

// Turn attributes travel through the handle to every child span, including
// when a later generator callback runs in a different isolation frame.
const CLAUDE_AGENT_SDK_ATTRIBUTES = asOtelAttributes(
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
  const text = content
    .map((block: any) => (block.type === 'text' ? block.text : ''))
    .filter(Boolean)
    .join('\n');
  return text || JSON.stringify(content);
}

type NormalizedUsage = {
  usage: Usage;
  totalTokens: number;
};

/**
 * Normalize one model's usage for `LLM.record()`.
 *
 * Anthropic reports `input_tokens` disjoint from cache-read/cache-creation.
 * Weave's canonical input count is inclusive, with both cache counts as
 * subsets, so fold them into inputTokens before recording.
 */
function normalizeUsage(
  rawUsage: ModelUsage | NonNullableUsage
): NormalizedUsage {
  const usage = toWeaveUsage(rawUsage);
  const inputTokens =
    usage.input_tokens +
    usage.cache_read_input_tokens +
    usage.cache_creation_input_tokens;
  const outputTokens = usage.output_tokens;

  return {
    usage: {
      inputTokens,
      outputTokens,
      cacheReadInputTokens: usage.cache_read_input_tokens,
      cacheCreationInputTokens: usage.cache_creation_input_tokens,
    },
    totalTokens: inputTokens + outputTokens,
  };
}

/**
 * The error message for a finished run, or undefined if it succeeded. A thrown
 * stream error wins; then a non-success terminal subtype surfaces its errors;
 * then a success result flagged `is_error` surfaces its text.
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
  if (result && result.subtype !== 'success') {
    return result.errors.join('; ');
  }
  if (result?.is_error) {
    return result.result;
  }
  return undefined;
}

type ClaudeAgentTracerOptions = {
  /** The user prompt, when invoked as a string (recorded as input on the Turn). */
  prompt?: string;
  /**
   * The main-thread agent name (`options.agent`). Falls back to the integration
   * name used by the Agents-tab per-agent usage rollup.
   */
  agent?: string;
};

export class ClaudeAgentTracer {
  private readonly agentName: string;
  private readonly prompt: string | undefined;
  private readonly startedAt = new Date();
  private readonly turnAttributes: Attributes = {
    ...CLAUDE_AGENT_SDK_ATTRIBUTES,
  };
  private readonly openTools = new Map<string, Tool>();

  private turn: Turn | null = null;
  private conversationId: string | null = null;
  private rootModel: string | null = null;
  private finished = false;

  constructor(opts: ClaudeAgentTracerOptions = {}) {
    this.agentName = opts.agent || AGENT_NAME;
    this.prompt = opts.prompt;
  }

  processMessage(msg: SDKMessage): void {
    this.captureConversationId(msg.session_id);
    this.ensureTurn();

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

    this.captureConversationId(result?.session_id);
    const turn = this.ensureTurn();

    // Sweep tool calls left open by an interrupted stream or missing result.
    for (const tool of this.openTools.values()) {
      tool.setAttributes({[ATTR_ERROR_TYPE]: 'aborted'});
      tool.end({error: new Error('Agent ended with open tool span')});
    }
    this.openTools.clear();

    if (this.rootModel) {
      turn.setAttributes({
        [ATTR_GEN_AI_RESPONSE_MODEL]: this.rootModel,
      });
    }

    if (result) {
      this.emitModelUsageSpans(result);

      const resultAttributes: Attributes = {
        [ATTR_COST_USD]: result.total_cost_usd,
        [ATTR_NUM_TURNS]: result.num_turns,
      };
      if (result.subtype === 'success') {
        const output: Message[] = [{role: 'assistant', content: result.result}];
        resultAttributes[ATTR_GEN_AI_OUTPUT_MESSAGES] = JSON.stringify(output);
      }
      turn.setAttributes(resultAttributes);
    }

    const errorMessage = runErrorMessage(error, result);
    if (errorMessage != null) {
      turn.setAttributes({[ATTR_ERROR_TYPE]: 'agent_error'});
      turn.end({
        error: new Error(errorMessage || 'Conversation ended with error'),
      });
    } else {
      turn.end();
    }
  }

  /**
   * Capture the Claude session id. Real SDK messages all carry it, but the
   * late-binding branch keeps result-only streams and partial test doubles safe.
   */
  private captureConversationId(sessionId: string | undefined): void {
    if (this.conversationId != null || !sessionId) {
      return;
    }
    this.conversationId = sessionId;
    if (this.turn) {
      this.turn.setAttributes({
        [ATTR_GEN_AI_CONVERSATION_ID]: sessionId,
      });
    }
  }

  /**
   * Lazily create the root Turn once a message is consumed. The start time is
   * captured in the constructor, so delaying creation until the session id is
   * known does not shorten the recorded query duration.
   */
  private ensureTurn(): Turn {
    if (this.turn) {
      return this.turn;
    }

    this.turn = runIsolated(() =>
      Turn.create({
        agentName: this.agentName,
        conversationId: this.conversationId ?? undefined,
        attributes: this.turnAttributes,
        startTime: this.startedAt,
      })
    );
    this.turn.setAttributes({
      [ATTR_GEN_AI_PROVIDER_NAME]: PROVIDER_NAME,
    });
    if (this.prompt != null) {
      this.turn.record({
        messages: [{role: 'user', content: this.prompt}],
      });
    }
    return this.turn;
  }

  /** Agent/conversation identity that is not first-class on child emitters. */
  private childAttributes(): Attributes {
    return {
      [ATTR_GEN_AI_AGENT_NAME]: this.agentName,
      ...(this.conversationId
        ? {[ATTR_GEN_AI_CONVERSATION_ID]: this.conversationId}
        : {}),
    };
  }

  /**
   * Emit one usage-only LLM span per model so the trace server can price and
   * roll up each model independently. The root carries no token usage.
   */
  private emitModelUsageSpans(result: SDKResultMessage): void {
    const perModel: Array<[string | undefined, ModelUsage | NonNullableUsage]> =
      result.modelUsage && Object.keys(result.modelUsage).length > 0
        ? Object.entries(result.modelUsage)
        : result.usage
          ? [[this.rootModel ?? undefined, result.usage]]
          : [];

    const turn = this.ensureTurn();
    for (const [model, rawUsage] of perModel) {
      const normalized = normalizeUsage(rawUsage);
      runIsolated(() => {
        const llm = turn.startLLM({
          model: model ?? '',
          providerName: PROVIDER_NAME,
        });
        llm.setAttributes({
          ...this.childAttributes(),
          [ATTR_GEN_AI_USAGE_TOTAL_TOKENS]: normalized.totalTokens,
        });
        llm.record({
          usage: normalized.usage,
          ...(model ? {responseModel: model} : {}),
        });
        llm.end();
      });
    }
  }

  private processAssistant(msg: SDKAssistantMessage): void {
    const model = msg.message.model;
    if (this.rootModel == null && model) {
      this.rootModel = model;
    }

    const content = msg.message.content;
    const parts = assistantParts(content);
    const turn = this.ensureTurn();

    runIsolated(() => {
      const llm = turn.startLLM({
        model: model ?? '',
        providerName: PROVIDER_NAME,
      });
      llm.setAttributes(this.childAttributes());
      llm.record({
        ...(parts.length > 0
          ? {outputMessages: [{role: 'assistant', parts}]}
          : {}),
        ...(model ? {responseModel: model} : {}),
        ...(msg.message.stop_reason
          ? {finishReasons: [msg.message.stop_reason]}
          : {}),
      });
      llm.end();
    });

    // Tool spans are flat children of the Turn and remain open until the
    // matching tool_result arrives on a later user message.
    for (const block of content) {
      if (block.type !== 'tool_use') {
        continue;
      }
      const tool = turn.startTool({
        name: block.name,
        toolCallId: block.id,
        args: JSON.stringify(block.input ?? {}),
      });
      tool.setAttributes(this.childAttributes());
      this.openTools.set(block.id, tool);
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
      const tool = this.openTools.get(block.tool_use_id);
      if (!tool) {
        continue;
      }
      this.openTools.delete(block.tool_use_id);
      const resultText = toolResultText(block.content);
      tool.result = resultText;
      if (block.is_error) {
        tool.setAttributes({[ATTR_ERROR_TYPE]: 'tool_error'});
        tool.end({error: new Error(resultText || 'Tool execution failed')});
      } else {
        tool.end();
      }
    }
  }
}
