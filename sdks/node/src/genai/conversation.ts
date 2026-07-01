import type {Attributes} from '@opentelemetry/api';
import {uuidv7} from 'uuidv7';

import {getGenaiState} from './context';
import {Turn, type TurnInit} from './turn';
import type {SpanEndOptions} from './spanBase';

export interface ConversationInit {
  model?: string;

  /**
   * Stable agent identifier. Propagated as the default `agentId` to every
   * `Turn` created via `startTurn()` unless the turn sets its own; emitted
   * on each turn's `invoke_agent` span as `gen_ai.agent.id`.
   */
  agentId?: string;

  /**
   * Agent name. Propagated as the default `agentName` to every `Turn`
   * created via `startTurn()` unless the turn sets its own; emitted on
   * each turn's `invoke_agent` span as `gen_ai.agent.name`.
   */
  agentName?: string;

  /**
   * Human-readable agent description. Propagated as the default
   * `agentDescription` to every `Turn` created via `startTurn()` unless
   * the turn sets its own; emitted on each turn's `invoke_agent` span as
   * `gen_ai.agent.description`.
   */
  agentDescription?: string;

  /**
   * Agent version string. Propagated as the default `agentVersion` to
   * every `Turn` created via `startTurn()` unless the turn sets its own;
   * emitted on each turn's `invoke_agent` span as `gen_ai.agent.version`.
   */
  agentVersion?: string;

  /**
   * Conversation ID propagated to every span under this conversation as
   * `gen_ai.conversation.id`. Auto-generated if omitted.
   */
  conversationId?: string;

  /**
   * Custom attributes stamped on every span the conversation emits.
   *
   * A key here that collides with a span's own `gen_ai.*` / `weave.*`
   * attribute is unsupported; the span's value wins.
   */
  attributes?: Attributes;

  /** @deprecated Use {@link ConversationInit.conversationId} instead. */
  sessionId?: string;
}

type Opts = {
  agentName: string;
  model: string;
  conversationId: string;
  attributes: Attributes;
  agentId: string;
  agentDescription: string;
  agentVersion: string;
};

/**
 * A Conversation groups Turns under a single `gen_ai.conversation.id`. It is
 * not itself an OTel span — children stamp the conversation id onto theirs.
 */
export class Conversation {
  private _ended = false;

  private _model: string;
  private _conversationId: string;
  private _agentId: string;
  private _agentName: string;
  private _agentDescription: string;
  private _agentVersion: string;

  private _attributes: Attributes;

  private constructor(opts: Opts) {
    this._model = opts.model;
    this._conversationId = opts.conversationId;
    this._attributes = opts.attributes;
    this._agentId = opts.agentId;
    this._agentName = opts.agentName;
    this._agentDescription = opts.agentDescription;
    this._agentVersion = opts.agentVersion;
  }

  public get agentName() {
    return this._agentName;
  }

  public get model() {
    return this._model;
  }

  public get conversationId() {
    return this._conversationId;
  }

  public get attributes() {
    return this._attributes;
  }

  /** @deprecated Use {@link Conversation.conversationId} instead. */
  get sessionId(): string {
    return this._conversationId;
  }

  static create(opts: ConversationInit = {}): Conversation {
    const state = getGenaiState();
    if (state.conversation !== null) {
      throw new Error(
        'A Conversation is already active in this async chain. End it before starting a new one.'
      );
    }
    const conversation = new Conversation({
      model: opts.model ?? '',
      agentId: opts.agentId ?? '',
      agentName: opts.agentName ?? '',
      agentDescription: opts.agentDescription ?? '',
      agentVersion: opts.agentVersion ?? '',
      conversationId: opts.conversationId ?? opts.sessionId ?? uuidv7(),
      attributes: opts.attributes ?? {},
    });
    state.conversation = conversation;
    return conversation;
  }

  /**
   * Start a new `Turn` under this `Conversation`. The turn inherits the
   * conversation's `conversationId`; `agentName`, `agentId`, `agentDescription`,
   * `agentVersion` and `model` fall back to the conversation's values when not
   * provided on `opts`.
   *
   * @example
   * const turn = conversation.startTurn();
   *
   * @example
   * const turn = conversation.startTurn({
   *   model: 'gpt-4o',
   *   agentName: 'research-bot',
   *   agentId: 'research-bot-prod',
   *   agentDescription: 'Looks up facts on Wikipedia.',
   *   agentVersion: '1.4.2',
   *   userMessage: 'What is the weather in Tokyo?',
   *   systemInstructions: ['You are a helpful weather bot.'],
   *   startTime: new Date('2026-05-29T10:00:00.000Z'),
   * });
   */
  startTurn(opts: TurnInit = {}): Turn {
    return Turn.create({
      ...opts,
      agentName: opts.agentName ?? this._agentName,
      model: opts.model ?? this._model,
      agentId: opts.agentId ?? this._agentId,
      agentDescription: opts.agentDescription ?? this._agentDescription,
      agentVersion: opts.agentVersion ?? this._agentVersion,
      conversationId: this._conversationId,
    });
  }

  end(opts?: SpanEndOptions): void {
    if (this._ended) {
      return;
    }
    this._ended = true;
    const state = getGenaiState();
    // Cascade: end any active descendants innermost-first so each child span
    // closes before its parent.
    if (state.llm) {
      state.llm.end(opts);
    }
    if (state.turn) {
      state.turn.end(opts);
    }
    if (state.conversation === this) {
      state.conversation = null;
    }
  }
}

/** @deprecated Use {@link ConversationInit} instead. */
export type SessionInit = ConversationInit;
/** @deprecated Use {@link Conversation} instead. */
export type Session = Conversation;
/** @deprecated Use {@link Conversation} instead. */
export const Session = Conversation;
