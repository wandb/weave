/**
 * Emits Weave calls from a Claude Agent SDK `query()` message stream.
 *
 * Mirrors the Python integration's inline message processor: a single root
 * `claude_agent_sdk.query` call (kind=agent) with child calls created in real
 * time as messages stream — `claude_agent_sdk.thinking`/`.text` (kind=llm) and
 * `claude_agent_sdk.tool_use.<name>` (kind=tool), the latter finished when the
 * matching `tool_result` arrives in a later user message. Usage/cost/duration
 * are lifted from the final result message onto the root call.
 */
import {uuidv7} from 'uuidv7';
import type {WeaveClient} from '../../weaveClient';
import {asAttributes, libraryIntegration} from '../integrationMetadata';
import {
  serializeMessage,
  textDisplayName,
  thinkingDisplayName,
  toolUseDisplayName,
  toWeaveUsage,
  turnDisplayName,
  type SDKAssistantMessage,
  type SDKMessage,
  type SDKResultMessage,
  type SDKUserMessage,
  type ThinkingBlock,
  type TextBlock,
  type ToolResultBlock,
  type ToolUseBlock,
} from './messages';

const ROOT_OP = 'claude_agent_sdk.query';

// Integration provenance stamped onto every call this tracer produces.
const CLAUDE_AGENT_SDK_INTEGRATION = libraryIntegration('claude_agent_sdk', {
  packageName: '@anthropic-ai/claude-agent-sdk',
});

export interface ClaudeAgentTracerOptions {
  client: WeaveClient;
  /** The user prompt, when invoked as a string (used for the root display name/inputs). */
  prompt?: string;
  /** Root op name. Defaults to `claude_agent_sdk.query`. */
  rootOp?: string;
}

function now(): string {
  return new Date().toISOString();
}

/** Extract a human-readable error message from a tool_result flagged `is_error`. */
function toolResultErrorMessage(result: ToolResultBlock): string {
  const {content} = result;
  if (typeof content === 'string' && content) {
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
  return 'Tool returned an error';
}

export class ClaudeAgentTracer {
  private readonly client: WeaveClient;
  private readonly callId = uuidv7();
  private readonly traceId = uuidv7();
  private readonly openToolCalls = new Map<string, string>();
  private readonly messages: Array<Record<string, unknown>> = [];
  private rootModel: string | null = null;
  private finished = false;

  constructor(opts: ClaudeAgentTracerOptions) {
    this.client = opts.client;
    const inputs: Record<string, unknown> = {};
    if (opts.prompt != null) {
      inputs.prompt = opts.prompt;
    }
    this.client.saveCallStart({
      project_id: this.client.projectId,
      id: this.callId,
      op_name: opts.rootOp ?? ROOT_OP,
      display_name: turnDisplayName(opts.prompt ?? null),
      trace_id: this.traceId,
      parent_id: null,
      started_at: now(),
      inputs,
      attributes: {
        kind: 'agent',
        ...asAttributes(CLAUDE_AGENT_SDK_INTEGRATION),
      },
    });
  }

  /** Process one streamed message, creating/finishing child calls in real time. */
  processMessage(msg: SDKMessage): void {
    switch (msg.type) {
      case 'assistant':
        this.processAssistant(msg as SDKAssistantMessage);
        break;
      case 'user':
        this.processUser(msg as SDKUserMessage);
        break;
      case 'system':
        this.messages.push(serializeMessage(msg));
        break;
      default:
        break;
    }
  }

  /**
   * Finish any open child calls and the root call, lifting result metadata.
   * `error`, when set, is an exception thrown while iterating the stream and
   * takes precedence over the result message: the root call is recorded as an
   * error rather than a successful completion.
   */
  finalize(result?: SDKResultMessage, error?: unknown): void {
    if (this.finished) {
      return;
    }
    this.finished = true;

    // If the stream threw, the still-open tool calls were interrupted — finish
    // them WITH the exception rather than as silent successful completions. On a
    // clean finish (no error), leftover open tool calls are closed without one.
    const interrupted =
      error != null
        ? `Tool call interrupted: ${
            error instanceof Error ? error.message : String(error)
          }`
        : undefined;
    for (const childId of this.openToolCalls.values()) {
      this.endCall(childId, {}, {}, interrupted);
    }
    this.openToolCalls.clear();

    const output: Record<string, unknown> = {
      status: 'completed',
      messages: this.messages,
    };
    if (this.rootModel) {
      output.model = this.rootModel;
    }

    let summary: Record<string, unknown> = {};
    let exception: string | undefined;

    if (result) {
      if (result.total_cost_usd != null)
        output.total_cost_usd = result.total_cost_usd;
      if (result.duration_ms != null) output.duration_ms = result.duration_ms;
      if (result.num_turns != null) output.num_turns = result.num_turns;
      if (result.result != null) output.result = result.result;
      if (result.usage != null) output.usage = result.usage;

      if (result.modelUsage) {
        const usage: Record<string, unknown> = {};
        for (const [model, u] of Object.entries(result.modelUsage)) {
          usage[model] = {requests: 1, ...toWeaveUsage(u)};
        }
        summary = {usage};
      } else if (this.rootModel && result.usage) {
        summary = {
          usage: {
            [this.rootModel]: {requests: 1, ...toWeaveUsage(result.usage)},
          },
        };
      }

      // why: the SDK reports non-success terminal subtypes (e.g.
      // `error_max_turns`, `error_during_execution`); treat any non-`success`
      // subtype as an error even if `is_error` is unset, so failed runs surface
      // as errors. This intentionally broadens the Python integration's
      // `is_error`-only check.
      if (result.is_error || (result.subtype && result.subtype !== 'success')) {
        output.status = 'error';
        // `||` (not `??`) so an empty-string `result` falls through to the
        // joined `errors` / default rather than yielding a blank exception.
        const detail =
          result.result ||
          (result.errors && result.errors.join('; ')) ||
          'Conversation ended with error';
        exception = String(detail);
      }
    }

    // A thrown stream error wins over the result message: the conversation did
    // not complete, so report the exception (mirrors the WeaveClient pattern).
    if (error != null) {
      output.status = 'error';
      exception = error instanceof Error ? error.message : String(error);
    }

    this.endCall(this.callId, output, summary, exception);
  }

  private processAssistant(msg: SDKAssistantMessage): void {
    const serialized = serializeMessage(msg);
    this.messages.push(serialized);

    const content = msg.message?.content ?? [];
    if (this.rootModel == null && msg.message?.model) {
      this.rootModel = msg.message.model;
    }

    const thinking = content
      .filter((b): b is ThinkingBlock => b.type === 'thinking')
      .map(b => b.thinking)
      .join('\n');
    if (thinking) {
      const id = this.startChild(
        'claude_agent_sdk.thinking',
        thinkingDisplayName(thinking),
        'llm',
        {}
      );
      this.endCall(id, {thinking});
    }

    const text = content
      .filter((b): b is TextBlock => b.type === 'text')
      .map(b => b.text)
      .join('\n');
    if (text) {
      const id = this.startChild(
        'claude_agent_sdk.text',
        textDisplayName(text),
        'llm',
        {}
      );
      this.endCall(id, {text, model: msg.message?.model});
    }

    for (const block of content.filter(
      (b): b is ToolUseBlock => b.type === 'tool_use'
    )) {
      const id = this.startChild(
        `claude_agent_sdk.tool_use.${block.name}`,
        toolUseDisplayName(block.name, block.input ?? {}),
        'tool',
        {message: serialized}
      );
      this.openToolCalls.set(block.id, id);
    }
  }

  private processUser(msg: SDKUserMessage): void {
    this.messages.push(serializeMessage(msg));

    const content = Array.isArray(msg.message?.content)
      ? msg.message.content
      : [];
    for (const block of content) {
      if (block.type !== 'tool_result') {
        continue;
      }
      const toolResult = block as ToolResultBlock;
      const childId = this.openToolCalls.get(toolResult.tool_use_id);
      if (childId) {
        this.openToolCalls.delete(toolResult.tool_use_id);
        // A tool_result flagged `is_error` is the tool reporting failure —
        // record it as an exception on the tool call, not a clean completion.
        const exception = toolResult.is_error
          ? toolResultErrorMessage(toolResult)
          : undefined;
        this.endCall(childId, toolResult, {}, exception);
      }
    }
  }

  private startChild(
    opName: string,
    displayName: string,
    kind: string,
    inputs: Record<string, unknown>
  ): string {
    const childId = uuidv7();
    this.client.saveCallStart({
      project_id: this.client.projectId,
      id: childId,
      op_name: opName,
      display_name: displayName,
      trace_id: this.traceId,
      parent_id: this.callId,
      started_at: now(),
      inputs,
      attributes: {kind, ...asAttributes(CLAUDE_AGENT_SDK_INTEGRATION)},
    });
    return childId;
  }

  private endCall(
    id: string,
    output: unknown,
    summary: Record<string, unknown> = {},
    exception?: string
  ): void {
    this.client.saveCallEnd({
      project_id: this.client.projectId,
      id,
      ended_at: now(),
      output,
      summary,
      ...(exception != null ? {exception} : {}),
    });
  }
}
