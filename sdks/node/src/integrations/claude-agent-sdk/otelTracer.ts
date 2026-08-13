import {
  Conversation,
  runIsolated,
  type Message,
  type MessagePart,
  type SubAgent,
  type Tool,
  type Turn,
  type Usage,
} from '../../genai';
import {ATTR_GEN_AI_USAGE_TOTAL_TOKENS} from '../../genai/semconv';
import {asOtelAttributes, libraryIntegration} from '../integrationMetadata';
import type {
  ModelUsage,
  NonNullableUsage,
  SDKAssistantMessage,
  SDKMessage,
  SDKResultMessage,
  SDKTaskNotificationMessage,
  SDKUserMessage,
  SDKUserMessageReplay,
} from '@anthropic-ai/claude-agent-sdk';
import {toWeaveUsage} from './messages';

const AGENT_NAME = 'claude_agent_sdk';
const PROVIDER_NAME = 'anthropic';

const ATTR_COST_USD = 'claude_agent_sdk.usage.cost_usd';

function namedError(name: string, message: string): Error {
  const error = new Error(message);
  error.name = name;
  return error;
}

const CLAUDE_AGENT_SDK_ATTRIBUTES = asOtelAttributes(
  libraryIntegration(AGENT_NAME, {
    packageName: '@anthropic-ai/claude-agent-sdk',
  })
);

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

type ToolResultBlock = Extract<
  SDKUserMessage['message']['content'][number],
  {type: 'tool_result'}
>;

type ToolUseBlock = Extract<
  SDKAssistantMessage['message']['content'][number],
  {type: 'tool_use'}
>;

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

function userInputMessage(msg: SDKUserMessage): Message {
  const content = msg.message.content;
  if (typeof content === 'string') {
    return {role: 'user', content};
  }

  const parts: MessagePart[] = [];
  for (const block of content) {
    switch (block.type) {
      case 'text':
        parts.push({type: 'text', content: block.text});
        break;
      case 'image':
        if (block.source.type === 'base64') {
          parts.push({
            type: 'blob',
            content: block.source.data,
            mimeType: block.source.media_type,
            modality: 'image',
          });
        } else {
          parts.push({
            type: 'uri',
            uri: block.source.url,
            modality: 'image',
          });
        }
        break;
      case 'tool_result':
        parts.push({
          type: 'tool_result',
          toolCallId: block.tool_use_id,
          result: toolResultText(block.content),
        });
        break;
      default:
        break;
    }
  }

  if (parts.length === 1 && parts[0].type === 'text') {
    return {role: 'user', content: parts[0].content};
  }
  return {role: 'user', parts};
}

function recordOf(value: unknown): Record<string, unknown> {
  return typeof value === 'object' && value != null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function stringField(
  value: Record<string, unknown>,
  key: string
): string | undefined {
  return typeof value[key] === 'string' ? value[key] : undefined;
}

function completedSubagentOutputText(
  value: Record<string, unknown>
): string | undefined {
  if (value.status !== 'completed' || !Array.isArray(value.content)) {
    return undefined;
  }

  const text: string[] = [];
  for (const item of value.content) {
    const block = recordOf(item);
    const blockText = stringField(block, 'text');
    if (block.type !== 'text' || blockText == null) {
      return undefined;
    }
    text.push(blockText);
  }
  return text.join('\n');
}

// `Task` is the pre-rename name for `Agent`; older SDK versions still emit it.
const SUBAGENT_TOOL_NAMES = new Set(['Agent', 'Task']);

function isSubagentTool(name: string): boolean {
  return SUBAGENT_TOOL_NAMES.has(name);
}

function booleanField(value: Record<string, unknown>, key: string): boolean {
  return value[key] === true;
}

/**
 * `run_in_background` and `isolation: 'remote'` (which the SDK documents as
 * always backgrounded) are declared on the `Agent` input, so read the lifetime
 * from the caller's request rather than inferring it from the result shape —
 * an unrecognized result status must not silently downgrade it.
 */
function subagentLifetime(
  input: Record<string, unknown>
): 'turn-scoped' | 'background' {
  return booleanField(input, 'run_in_background') ||
    stringField(input, 'isolation') === 'remote'
    ? 'background'
    : 'turn-scoped';
}

type SubagentIdentity = {
  agentId?: string;
  model?: string;
  taskId?: string;
};

/**
 * Reads an `Agent`/`Task` tool result. `async_launched` and `remote_launched`
 * only acknowledge the launch — the real outcome arrives later as a
 * `task_notification` — so neither is terminal.
 */
function subagentResult(value: unknown): {
  acknowledgesLaunch: boolean;
  identity: SubagentIdentity;
  outputText: string | undefined;
} {
  const raw = recordOf(value);
  return {
    acknowledgesLaunch:
      raw.status === 'async_launched' || raw.status === 'remote_launched',
    identity: {
      agentId: stringField(raw, 'agentId'),
      model: stringField(raw, 'resolvedModel'),
      // A remote launch names its handle `taskId`; the others use `agentId`.
      taskId: stringField(raw, 'taskId'),
    },
    outputText: completedSubagentOutputText(raw),
  };
}

type NormalizedUsage = {
  usage: Usage;
  totalTokens: number;
};

function normalizeUsage(
  rawUsage: ModelUsage | NonNullableUsage
): NormalizedUsage {
  const usage = toWeaveUsage(rawUsage);
  // Anthropic excludes cache tokens from input tokens; Weave includes them.
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

type ClaudeAgentOtelTracerOptions = {
  prompt?: string;
  agent?: string;
};

type PendingTurn = {
  inputMessages: Message[];
  startedAt: Date;
};

/**
 * A subagent's terminal state. Buffered so child spans close before their
 * parent. Failures are recorded immediately without ending the span;
 * `endedAt` preserves the real duration across the deferred close.
 */
type SubagentOutcome =
  | {status: 'ok'; endedAt: Date}
  | {status: 'error'; endedAt: Date};

type OpenSubagent = {
  /** `AgentOutput.agentId` — the subagent's own identity. */
  agentId?: string;
  /** `background` subagents outlive the turn that launched them. */
  lifetime: 'turn-scoped' | 'background';
  /** Owning subagent's tool-use ID; undefined when the parent is the Turn. */
  parentToolUseId?: string;
  span: SubAgent;
  /** `task_notification.task_id` — the task-registry handle, not assumed equal to `agentId`. */
  taskId?: string;
  outcome?: SubagentOutcome;
};

type OpenTool = {
  /** Owning subagent's tool-use ID; undefined when the parent is the Turn. */
  ownerToolUseId?: string;
  tool: Tool;
};

/** Emits Claude Agent SDK traces through Weave GenAI handles. */
export class ClaudeAgentOtelTracer {
  private readonly agentName: string;
  private readonly startedAt = new Date();
  private readonly openSubagents = new Map<string, OpenSubagent>();
  private readonly openTools = new Map<string, OpenTool>();
  private readonly pendingTurns: PendingTurn[] = [];

  private conversation: Conversation | null = null;
  private conversationId: string | undefined;
  private activeTurn: Turn | null = null;
  private bufferedInputMessages: Message[] = [];
  private bufferedTurnStartedAt: Date | null = null;
  private completedTurns = 0;
  private rootModel: string | null = null;
  private finished = false;

  constructor(opts: ClaudeAgentOtelTracerOptions = {}) {
    this.agentName = opts.agent || AGENT_NAME;
    if (opts.prompt != null) {
      this.pendingTurns.push({
        inputMessages: [{role: 'user', content: opts.prompt}],
        startedAt: this.startedAt,
      });
    }
  }

  processInput(msg: SDKUserMessage): void {
    if (this.finished) {
      return;
    }
    this.rememberConversationId(msg.session_id);
    if (this.bufferedTurnStartedAt == null) {
      this.bufferedTurnStartedAt = new Date();
    }
    this.bufferedInputMessages.push(userInputMessage(msg));

    if (msg.shouldQuery !== false) {
      this.pendingTurns.push({
        inputMessages: this.bufferedInputMessages,
        startedAt: this.bufferedTurnStartedAt,
      });
      this.bufferedInputMessages = [];
      this.bufferedTurnStartedAt = null;
    }
  }

  processMessage(msg: SDKMessage): void {
    if (this.finished) {
      return;
    }
    this.rememberConversationId(msg.session_id);

    switch (msg.type) {
      case 'assistant':
        this.processAssistant(msg);
        break;
      case 'user':
        this.processUser(msg);
        break;
      case 'result':
        this.endTurn(msg);
        break;
      case 'system':
        if (msg.subtype === 'task_notification') {
          this.processTaskNotification(msg);
        }
        break;
      default:
        break;
    }
  }

  finalize(result?: SDKResultMessage, error?: unknown): void {
    if (this.finished) {
      return;
    }

    if (result) {
      this.processMessage(result);
    }
    this.finished = true;

    if (
      this.activeTurn ||
      this.pendingTurns.length > 0 ||
      this.bufferedInputMessages.length > 0 ||
      this.completedTurns === 0
    ) {
      this.endTurn(undefined, error);
    }
    this.finishOpenTools('shutdown');
    this.finishOpenSubagents('shutdown');
  }

  private endTurn(result?: SDKResultMessage, error?: unknown): void {
    const turn = this.getOrCreateTurn();
    // Sweep children before their parents, and spare anything owned by a
    // background subagent that is still running past this turn boundary.
    this.finishOpenTools('turn-boundary');
    this.finishOpenSubagents('turn-boundary');

    if (result) {
      this.emitModelUsageSpans(result, turn);

      turn.setAttributes({
        [ATTR_COST_USD]: result.total_cost_usd,
      });
      if (result.subtype === 'success') {
        turn.record({
          outputMessages: [{role: 'assistant', content: result.result}],
        });
      }
    }

    const errorMessage = runErrorMessage(error, result);
    if (errorMessage != null) {
      turn.end({
        error: namedError(
          'agent_error',
          errorMessage || 'Conversation ended with error'
        ),
      });
    } else {
      turn.end();
    }

    this.activeTurn = null;
    this.rootModel = null;
    this.completedTurns += 1;
  }

  private rememberConversationId(conversationId: string | undefined): void {
    if (this.conversationId == null && conversationId) {
      this.conversationId = conversationId;
    }
  }

  private getOrCreateConversation(): Conversation {
    if (this.conversation) {
      return this.conversation;
    }

    this.conversation = runIsolated(() =>
      Conversation.create({
        agentName: this.agentName,
        conversationId: this.conversationId ?? '',
        attributes: CLAUDE_AGENT_SDK_ATTRIBUTES,
      })
    );
    return this.conversation;
  }

  private nextPendingTurn(): PendingTurn {
    const pending = this.pendingTurns.shift();
    if (pending) {
      return pending;
    }
    if (this.bufferedTurnStartedAt) {
      const buffered = {
        inputMessages: this.bufferedInputMessages,
        startedAt: this.bufferedTurnStartedAt,
      };
      this.bufferedInputMessages = [];
      this.bufferedTurnStartedAt = null;
      return buffered;
    }
    return {
      inputMessages: [],
      startedAt: this.completedTurns === 0 ? this.startedAt : new Date(),
    };
  }

  private getOrCreateTurn(): Turn {
    if (this.activeTurn) {
      return this.activeTurn;
    }

    const pending = this.nextPendingTurn();
    const conversation = this.getOrCreateConversation();
    this.activeTurn = runIsolated(() =>
      conversation.startTurn({
        startTime: pending.startedAt,
      })
    );
    if (pending.inputMessages.length > 0) {
      this.activeTurn.record({
        messages: pending.inputMessages,
      });
    }
    return this.activeTurn;
  }

  private emitModelUsageSpans(result: SDKResultMessage, turn: Turn): void {
    const perModel: Array<[string | undefined, ModelUsage | NonNullableUsage]> =
      result.modelUsage && Object.keys(result.modelUsage).length > 0
        ? Object.entries(result.modelUsage)
        : result.usage
          ? [[this.rootModel ?? undefined, result.usage]]
          : [];

    // Keep usage per model so the server can price each model independently.
    for (const [model, rawUsage] of perModel) {
      const normalized = normalizeUsage(rawUsage);
      runIsolated(() => {
        const llm = turn.startLLM({
          model: model ?? '',
          providerName: PROVIDER_NAME,
        });
        llm.setAttributes({
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
    if (msg.parent_tool_use_id == null && this.rootModel == null && model) {
      this.rootModel = model;
    }

    const parent = this.getOrCreateMessageParent(msg);
    const content = msg.message.content;
    const parts = assistantParts(content);

    runIsolated(() => {
      const llm = parent.startLLM({
        model: model ?? '',
        providerName: PROVIDER_NAME,
      });
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

    // Tool spans stay open until the matching tool_result arrives. Record the
    // owning subagent so a turn boundary can tell whose children these are.
    const ownerToolUseId = msg.parent_tool_use_id ?? undefined;
    for (const block of content) {
      if (block.type !== 'tool_use') {
        continue;
      }
      if (isSubagentTool(block.name)) {
        this.startSubagent(block, parent, ownerToolUseId);
        continue;
      }
      const tool = parent.startTool({
        name: block.name,
        toolCallId: block.id,
        args: JSON.stringify(block.input ?? {}),
      });
      this.openTools.set(block.id, {ownerToolUseId, tool});
    }
  }

  private getOrCreateMessageParent(msg: SDKAssistantMessage): Turn | SubAgent {
    const parentToolUseId = msg.parent_tool_use_id;
    if (parentToolUseId == null) {
      return this.getOrCreateTurn();
    }

    let openSubagent = this.openSubagents.get(parentToolUseId);
    if (!openSubagent) {
      const turn = this.getOrCreateTurn();
      const span = turn.startSubagent({
        name: msg.subagent_type ?? 'subagent',
        model: msg.message.model,
        agentDescription: msg.task_description,
      });
      // Reached only when the `Agent` tool_use block was never observed, so
      // the launch options are unknown and the parent is this Turn.
      openSubagent = {lifetime: 'turn-scoped', span};
      this.openSubagents.set(parentToolUseId, openSubagent);
    } else {
      openSubagent.span.record({
        ...(msg.subagent_type ? {name: msg.subagent_type} : {}),
        ...(msg.message.model ? {model: msg.message.model} : {}),
        ...(msg.task_description
          ? {agentDescription: msg.task_description}
          : {}),
      });
    }
    return openSubagent.span;
  }

  private startSubagent(
    block: ToolUseBlock,
    parent: Turn | SubAgent,
    parentToolUseId: string | undefined
  ): void {
    const input = recordOf(block.input);
    const name =
      stringField(input, 'subagent_type') ??
      stringField(input, 'name') ??
      'subagent';
    const prompt = stringField(input, 'prompt');
    const subagent = parent.startSubagent({
      name,
      model: stringField(input, 'model'),
      agentDescription: stringField(input, 'description'),
    });
    subagent.record({
      messages: prompt ? [{role: 'user', content: prompt}] : [],
    });
    this.openSubagents.set(block.id, {
      lifetime: subagentLifetime(input),
      parentToolUseId,
      span: subagent,
    });
  }

  private processUser(msg: SDKUserMessage | SDKUserMessageReplay): void {
    const content = Array.isArray(msg.message.content)
      ? msg.message.content
      : [];
    for (const block of content) {
      if (block.type !== 'tool_result') {
        continue;
      }
      const openSubagent = this.openSubagents.get(block.tool_use_id);
      if (openSubagent) {
        this.processSubagentResult(openSubagent, block, msg);
        continue;
      }
      const openTool = this.openTools.get(block.tool_use_id);
      if (!openTool) {
        continue;
      }
      const resultText = toolResultText(block.content);
      this.openTools.delete(block.tool_use_id);
      const tool = openTool.tool;
      tool.result = resultText;
      if (block.is_error) {
        tool.end({
          error: namedError(
            'tool_error',
            resultText || 'Tool execution failed'
          ),
        });
      } else {
        tool.end();
      }
    }
  }

  private processSubagentResult(
    openSubagent: OpenSubagent,
    block: ToolResultBlock,
    msg: SDKUserMessage | SDKUserMessageReplay
  ): void {
    const {acknowledgesLaunch, identity, outputText} = subagentResult(
      msg.tool_use_result
    );
    // The identity fields ride on every `Agent` result shape, launch or not.
    openSubagent.agentId = identity.agentId ?? openSubagent.agentId;
    openSubagent.taskId = identity.taskId ?? openSubagent.taskId;
    openSubagent.span.record({
      ...(identity.model ? {model: identity.model} : {}),
      ...(identity.agentId ? {agentId: identity.agentId} : {}),
    });

    if (acknowledgesLaunch && !block.is_error) {
      // Only an acknowledgement — the outcome arrives as a task_notification.
      openSubagent.lifetime = 'background';
      return;
    }

    let terminalOutputText = outputText;
    if (block.is_error || terminalOutputText === undefined) {
      const fallbackText = toolResultText(block.content);
      terminalOutputText = fallbackText;
    }
    openSubagent.span.record({
      outputMessages: terminalOutputText
        ? [{role: 'assistant', content: terminalOutputText}]
        : [],
    });
    const endedAt = new Date();
    if (block.is_error) {
      openSubagent.span.recordError(
        namedError(
          'subagent_error',
          terminalOutputText || 'Subagent execution failed'
        )
      );
      openSubagent.outcome = {status: 'error', endedAt};
    } else {
      openSubagent.outcome = {status: 'ok', endedAt};
    }
  }

  private processTaskNotification(msg: SDKTaskNotificationMessage): void {
    // `task_id` and the launch result's `agentId` are not documented as the
    // same value, so match either before giving up.
    const toolUseId =
      msg.tool_use_id ??
      [...this.openSubagents.entries()].find(
        ([, openSubagent]) =>
          openSubagent.taskId === msg.task_id ||
          openSubagent.agentId === msg.task_id
      )?.[0];
    if (!toolUseId) {
      return;
    }

    const openSubagent = this.openSubagents.get(toolUseId);
    if (!openSubagent) {
      return;
    }
    openSubagent.taskId = msg.task_id;
    if (openSubagent.agentId == null) {
      openSubagent.agentId = msg.task_id;
      openSubagent.span.record({agentId: msg.task_id});
    }
    if (msg.usage) {
      openSubagent.span.setAttributes({
        [ATTR_GEN_AI_USAGE_TOTAL_TOKENS]: msg.usage.total_tokens,
      });
    }
    const endedAt = new Date();
    if (msg.status === 'completed') {
      // The summary is the only result text a background subagent ever reports.
      if (msg.summary) {
        openSubagent.span.record({
          outputMessages: [{role: 'assistant', content: msg.summary}],
        });
      }
      openSubagent.outcome = {status: 'ok', endedAt};
      return;
    }

    openSubagent.span.recordError(
      namedError(
        msg.status === 'stopped' ? 'aborted' : 'subagent_error',
        msg.summary || `Background subagent ${msg.status}`
      )
    );
    openSubagent.outcome = {status: 'error', endedAt};
  }

  /**
   * True when `toolUseId` is a background subagent, or a descendant of one, so
   * it must outlive the turn that launched it. Terminates because a parent is
   * always registered before its children.
   */
  private outlivesTurn(toolUseId: string | undefined): boolean {
    let cursor = toolUseId;
    while (cursor) {
      const openSubagent = this.openSubagents.get(cursor);
      if (!openSubagent) {
        return false;
      }
      if (openSubagent.lifetime === 'background') {
        return true;
      }
      cursor = openSubagent.parentToolUseId;
    }
    return false;
  }

  private finishOpenTools(reason: 'turn-boundary' | 'shutdown'): void {
    for (const [toolUseId, openTool] of [...this.openTools.entries()]) {
      if (
        reason === 'turn-boundary' &&
        this.outlivesTurn(openTool.ownerToolUseId)
      ) {
        continue;
      }
      openTool.tool.end({
        error: namedError('aborted', 'Agent ended with open tool span'),
      });
      this.openTools.delete(toolUseId);
    }
  }

  private finishOpenSubagents(reason: 'turn-boundary' | 'shutdown'): void {
    // Newest-first so a nested subagent closes before the parent it hangs off.
    const openSubagents = [...this.openSubagents.entries()].reverse();
    for (const [toolUseId, openSubagent] of openSubagents) {
      const outcome = openSubagent.outcome;
      if (outcome) {
        openSubagent.span.end({endTime: outcome.endedAt});
        this.openSubagents.delete(toolUseId);
        continue;
      }
      if (reason === 'turn-boundary' && this.outlivesTurn(toolUseId)) {
        continue;
      }
      openSubagent.span.end({
        error: namedError('aborted', 'Agent ended with open subagent span'),
      });
      this.openSubagents.delete(toolUseId);
    }
  }
}
