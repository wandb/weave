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
import {
  ATTR_ERROR_TYPE,
  ATTR_GEN_AI_INPUT_MESSAGES,
  ATTR_GEN_AI_OUTPUT_MESSAGES,
  ATTR_GEN_AI_TOOL_CALL_ARGUMENTS,
  ATTR_GEN_AI_TOOL_CALL_ID,
  ATTR_GEN_AI_TOOL_CALL_RESULT,
  ATTR_GEN_AI_TOOL_NAME,
  ATTR_GEN_AI_USAGE_TOTAL_TOKENS,
} from '../../genai/semconv';
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
    if (block.type === 'text') {
      parts.push({type: 'text', content: block.text});
    } else if (block.type === 'tool_result') {
      parts.push({
        type: 'tool_result',
        toolCallId: block.tool_use_id,
        result: toolResultText(block.content),
      });
    } else {
      return {role: 'user', content: JSON.stringify(content)};
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

function isSubagentTool(name: string): boolean {
  return name === 'Agent' || name === 'Task';
}

function asyncSubagentLaunch(value: unknown): {
  model?: string;
  taskId?: string;
} | null {
  const result = recordOf(value);
  if (result.status !== 'async_launched') {
    return null;
  }
  return {
    model: stringField(result, 'resolvedModel'),
    taskId: stringField(result, 'agentId'),
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

type SubagentCompletion = {
  error?: Error;
  errorType?: 'aborted' | 'subagent_error';
};

type OpenSubagent = {
  background: boolean;
  completion?: SubagentCompletion;
  span: SubAgent;
  taskId?: string;
};

/** Emits Claude Agent SDK traces through Weave GenAI handles. */
export class ClaudeAgentOtelTracer {
  private readonly agentName: string;
  private readonly startedAt = new Date();
  private readonly openSubagents = new Map<string, OpenSubagent>();
  private readonly openTools = new Map<string, Tool>();
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
        this.processAssistant(msg, this.getOrCreateTurn());
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
    this.finishOpenSubagents(true);
  }

  private endTurn(result?: SDKResultMessage, error?: unknown): void {
    const turn = this.getOrCreateTurn();
    for (const tool of this.openTools.values()) {
      tool.setAttributes({[ATTR_ERROR_TYPE]: 'aborted'});
      tool.end({error: new Error('Agent ended with open tool span')});
    }
    this.openTools.clear();
    this.finishOpenSubagents(false);

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
      turn.setAttributes({[ATTR_ERROR_TYPE]: 'agent_error'});
      turn.end({
        error: new Error(errorMessage || 'Conversation ended with error'),
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

  private processAssistant(msg: SDKAssistantMessage, turn: Turn): void {
    const model = msg.message.model;
    if (msg.parent_tool_use_id == null && this.rootModel == null && model) {
      this.rootModel = model;
    }

    const parent = this.getOrCreateMessageParent(msg, turn);
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

    // Tool spans stay open until the matching tool_result arrives.
    for (const block of content) {
      if (block.type !== 'tool_use') {
        continue;
      }
      if (isSubagentTool(block.name)) {
        this.startSubagent(block, parent);
        continue;
      }
      const tool = parent.startTool({
        name: block.name,
        toolCallId: block.id,
        args: JSON.stringify(block.input ?? {}),
      });
      this.openTools.set(block.id, tool);
    }
  }

  private getOrCreateMessageParent(
    msg: SDKAssistantMessage,
    turn: Turn
  ): Turn | SubAgent {
    const parentToolUseId = msg.parent_tool_use_id;
    if (parentToolUseId == null) {
      return turn;
    }

    let openSubagent = this.openSubagents.get(parentToolUseId);
    if (!openSubagent) {
      const span = turn.startSubagent({
        name: msg.subagent_type ?? 'subagent',
        model: msg.message.model,
        agentDescription: msg.task_description,
      });
      span.setAttributes({
        [ATTR_GEN_AI_TOOL_CALL_ID]: parentToolUseId,
      });
      openSubagent = {background: false, span};
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

  private startSubagent(block: ToolUseBlock, parent: Turn | SubAgent): void {
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
    subagent.setAttributes({
      [ATTR_GEN_AI_TOOL_CALL_ID]: block.id,
      [ATTR_GEN_AI_TOOL_NAME]: block.name,
      [ATTR_GEN_AI_TOOL_CALL_ARGUMENTS]: JSON.stringify(block.input ?? {}),
      ...(prompt
        ? {
            [ATTR_GEN_AI_INPUT_MESSAGES]: JSON.stringify([
              {role: 'user', content: prompt},
            ]),
          }
        : {}),
    });
    this.openSubagents.set(block.id, {background: false, span: subagent});
  }

  private processUser(msg: SDKUserMessage | SDKUserMessageReplay): void {
    const content = Array.isArray(msg.message.content)
      ? msg.message.content
      : [];
    for (const block of content) {
      if (block.type !== 'tool_result') {
        continue;
      }
      const resultText = toolResultText(block.content);
      const openSubagent = this.openSubagents.get(block.tool_use_id);
      if (openSubagent) {
        const launch = asyncSubagentLaunch(msg.tool_use_result);
        if (launch && !block.is_error) {
          openSubagent.background = true;
          openSubagent.taskId = launch.taskId;
          openSubagent.span.record({
            ...(launch.model ? {model: launch.model} : {}),
            ...(launch.taskId ? {agentId: launch.taskId} : {}),
          });
          continue;
        }
        openSubagent.span.setAttributes({
          [ATTR_GEN_AI_TOOL_CALL_RESULT]: resultText,
          ...(resultText
            ? {
                [ATTR_GEN_AI_OUTPUT_MESSAGES]: JSON.stringify([
                  {role: 'assistant', content: resultText},
                ]),
              }
            : {}),
        });
        if (block.is_error) {
          openSubagent.completion = {
            errorType: 'subagent_error',
            error: new Error(resultText || 'Subagent execution failed'),
          };
        } else {
          openSubagent.completion = {};
        }
        continue;
      }
      const tool = this.openTools.get(block.tool_use_id);
      if (!tool) {
        continue;
      }
      this.openTools.delete(block.tool_use_id);
      tool.result = resultText;
      if (block.is_error) {
        tool.setAttributes({[ATTR_ERROR_TYPE]: 'tool_error'});
        tool.end({error: new Error(resultText || 'Tool execution failed')});
      } else {
        tool.end();
      }
    }
  }

  private processTaskNotification(msg: SDKTaskNotificationMessage): void {
    let toolUseId = msg.tool_use_id;
    if (!toolUseId) {
      toolUseId = [...this.openSubagents.entries()].find(
        ([, openSubagent]) => openSubagent.taskId === msg.task_id
      )?.[0];
    }
    if (!toolUseId) {
      return;
    }

    const openSubagent = this.openSubagents.get(toolUseId);
    if (!openSubagent) {
      return;
    }
    openSubagent.background = true;
    openSubagent.taskId = msg.task_id;
    openSubagent.span.record({agentId: msg.task_id});
    if (msg.status === 'completed') {
      openSubagent.completion = {};
      return;
    }

    openSubagent.completion = {
      errorType: msg.status === 'stopped' ? 'aborted' : 'subagent_error',
      error: new Error(msg.summary || `Background subagent ${msg.status}`),
    };
  }

  private finishOpenSubagents(finalizing: boolean): void {
    const openSubagents = [...this.openSubagents.entries()].reverse();
    for (const [toolUseId, openSubagent] of openSubagents) {
      const completion = openSubagent.completion;
      if (completion) {
        if (completion.errorType) {
          openSubagent.span.setAttributes({
            [ATTR_ERROR_TYPE]: completion.errorType,
          });
        }
        openSubagent.span.end(
          completion.error ? {error: completion.error} : undefined
        );
        this.openSubagents.delete(toolUseId);
        continue;
      }
      if (openSubagent.background && !finalizing) {
        continue;
      }
      openSubagent.span.setAttributes({[ATTR_ERROR_TYPE]: 'aborted'});
      openSubagent.span.end({
        error: new Error('Agent ended with open subagent span'),
      });
      this.openSubagents.delete(toolUseId);
    }
  }
}
