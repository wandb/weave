import {
  type AttributeValue,
  type Attributes,
  type Context,
  ROOT_CONTEXT,
  type Span,
  SpanKind,
  trace,
} from '@opentelemetry/api';

import {getGenaiState} from './context';
import {LLM, type LLMInit} from './llm';
import {getWeaveTracer} from './provider';
import {SpanBase, type SpanEndOptions, type SpanInitBase} from './spanBase';
import {
  ATTR_GEN_AI_AGENT_DESCRIPTION,
  ATTR_GEN_AI_AGENT_ID,
  ATTR_GEN_AI_AGENT_NAME,
  ATTR_GEN_AI_AGENT_VERSION,
  ATTR_GEN_AI_CONVERSATION_ID,
  ATTR_GEN_AI_INPUT_MESSAGES,
  ATTR_GEN_AI_OPERATION_NAME,
  ATTR_GEN_AI_REQUEST_MODEL,
  ATTR_GEN_AI_SYSTEM_INSTRUCTIONS,
  WEAVE_GENAI_TRACER_NAME,
} from './semconv';
import {SubAgent, type SubAgentInit} from './subagent';
import {Tool, type ToolInit} from './tool';
import type {Message} from './types';

export interface TurnInit extends SpanInitBase {
  model?: string;
  systemInstructions?: string[];
  userMessage?: string;
  agentId?: string;
  agentName?: string;
  agentDescription?: string;
  agentVersion?: string;
}

/**
 * An agent invocation. Typically wraps the work to respond to a single
 * user message. Emits an `invoke_agent` span and acts as the root of the
 * trace for that turn: it is always started under `ROOT_CONTEXT` so it
 * never accidentally inherits a parent from another OTel-instrumented
 * library.
 *
 * Created by `weave.startTurn()` (or `conversation.startTurn()`) and
 * terminated with `end()`. Only one Turn may be active in an async chain.
 * Children (LLM, Tool, SubAgent) attach via the `startLLM`, `startTool`,
 * `startSubagent` methods.
 *
 * @example
 * const turn = weave.startTurn();
 *
 * try {
 *   const llm = turn.startLLM({model: 'gpt-4o', providerName: 'openai'});
 *   // ...
 *   llm.end();
 * } finally {
 *   turn.end();
 * }
 *
 * @example
 * const turn = weave.startTurn({
 *   model: 'gpt-4o',
 *   agentName: 'research-bot',
 *   agentId: 'research-bot-prod',
 *   agentDescription: 'Looks up facts on Wikipedia.',
 *   agentVersion: '1.4.2',
 *   userMessage: 'What is the weather in Tokyo?',
 *   systemInstructions: ['You are a helpful weather bot.'],
 *   startTime: new Date('2026-05-29T10:00:00.000Z'),
 * });
 *
 * try {
 *   const llm = turn.startLLM({model: 'gpt-4o', providerName: 'openai'});
 *   // ...
 *   llm.end();
 * } finally {
 *   turn.end();
 * }
 */

type Opts = {
  conversationId: string;
  messages: Message[];
  span: Span;
  context: Context;
} & Required<Omit<TurnInit, 'userMessage' | 'startTime'>>;

export class Turn extends SpanBase {
  private _context: Context;
  private _conversationId: string;
  private _agentId: string;
  private _agentName: string;
  private _agentDescription: string;
  private _agentVersion: string;
  private _model: string;
  private _messages: Message[];
  private _systemInstructions: string[];

  public get agentName() {
    return this._agentName;
  }

  public get model() {
    return this._model;
  }

  private constructor(opts: Opts) {
    super(opts.span);
    this._context = opts.context;
    this._conversationId = opts.conversationId;
    this._agentId = opts.agentId;
    this._agentName = opts.agentName;
    this._agentDescription = opts.agentDescription;
    this._agentVersion = opts.agentVersion;
    this._messages = opts.messages;
    this._model = opts.model;
    this._systemInstructions = opts.systemInstructions;
  }

  static create(opts: TurnInit & {conversationId?: string} = {}): Turn {
    const state = getGenaiState();
    if (state.turn !== null) {
      throw new Error(
        'A Turn is already active in this async chain. End it before starting a new one.'
      );
    }
    const tracer = getWeaveTracer(WEAVE_GENAI_TRACER_NAME);
    const attributes: Attributes = {
      ...(state.conversation?.attributes ?? {}),
      [ATTR_GEN_AI_OPERATION_NAME]: 'invoke_agent',
    };
    if (opts.agentName) {
      attributes[ATTR_GEN_AI_AGENT_NAME] = opts.agentName;
    }
    if (opts.model) {
      attributes[ATTR_GEN_AI_REQUEST_MODEL] = opts.model;
    }
    if (opts.conversationId) {
      attributes[ATTR_GEN_AI_CONVERSATION_ID] = opts.conversationId;
    }
    if (opts.agentId) {
      attributes[ATTR_GEN_AI_AGENT_ID] = opts.agentId;
    }
    if (opts.agentDescription) {
      attributes[ATTR_GEN_AI_AGENT_DESCRIPTION] = opts.agentDescription;
    }
    if (opts.agentVersion) {
      attributes[ATTR_GEN_AI_AGENT_VERSION] = opts.agentVersion;
    }
    const messages: Message[] = opts.userMessage
      ? [{role: 'user', parts: [{type: 'text', content: opts.userMessage}]}]
      : [];
    if (messages.length > 0) {
      attributes[ATTR_GEN_AI_INPUT_MESSAGES] = JSON.stringify(messages);
    }
    if (opts.systemInstructions && opts.systemInstructions.length > 0) {
      attributes[ATTR_GEN_AI_SYSTEM_INSTRUCTIONS] = JSON.stringify(
        opts.systemInstructions.map(content => ({type: 'text', content}))
      );
    }
    // Pass ROOT_CONTEXT explicitly so Turn is always a root span — never
    // accidentally inherits a parent from some other OTel-instrumented
    // library's active context.
    const span = tracer.startSpan(
      'invoke_agent',
      {kind: SpanKind.CLIENT, attributes, startTime: opts.startTime},
      ROOT_CONTEXT
    );
    const turn = new Turn({
      span,
      context: trace.setSpan(ROOT_CONTEXT, span),
      conversationId: opts.conversationId ?? '',
      model: opts.model ?? '',
      agentName: opts.agentName ?? '',
      messages,
      systemInstructions: opts.systemInstructions ?? [],
      agentId: opts.agentId ?? '',
      agentDescription: opts.agentDescription ?? '',
      agentVersion: opts.agentVersion ?? '',
    });
    state.turn = turn;
    return turn;
  }

  /** Start a child LLM span under this Turn. */
  startLLM(opts: LLMInit): LLM {
    return LLM.create({
      ...opts,
      parentContext: this._context,
      conversationId: this._conversationId,
    });
  }

  /** Start a child Tool span under this Turn. */
  startTool(opts: ToolInit): Tool {
    return Tool.create({
      ...opts,
      parentContext: this._context,
      conversationId: this._conversationId,
    });
  }

  /** Start a child SubAgent span under this Turn. */
  startSubagent(opts: SubAgentInit): SubAgent {
    return SubAgent.create({
      ...opts,
      parentContext: this._context,
      conversationId: this._conversationId,
    });
  }

  /**
   * @deprecated Use {@link setAttributes} instead, which mirrors the Python
   * SDK's `set_attributes` and OTel's `Span.setAttributes`. Retained as a thin
   * alias so existing single-attribute callers keep working. Only `Turn`
   * carries this — the other emitters never shipped a singular form.
   */
  setAttribute(key: string, value: AttributeValue): this {
    return this.setAttributes({[key]: value});
  }

  /**
   * Close the Turn span. Idempotent. Pass `error` to mark it as failed; pass
   * `endTime` to backdate the close.
   */
  end(opts?: SpanEndOptions): void {
    if (this._ended) {
      return;
    }
    this._ended = true;
    this._closeSpan(opts);
    const state = getGenaiState();
    if (state.turn === this) {
      state.turn = null;
    }
  }
}
