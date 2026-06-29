import type {Attributes} from '@opentelemetry/api';
import {uuidv7} from 'uuidv7';

import {getGenaiState} from './context';
import {Turn, type TurnInit} from './turn';
import type {SpanEndOptions} from './spanBase';

export interface ConversationInit {
  agentName?: string;
  model?: string;
  /** Conversation ID propagated to every span under this conversation as
   *  `gen_ai.conversation.id`. Auto-generated if omitted. */
  conversationId?: string;
  /**
   * Custom attributes stamped on every span the conversation emits.
   *
   * A key here that collides with a span's own `gen_ai.*` / `weave.*`
   * attribute is unsupported; the span's value wins.
   */
  attributes?: Attributes;
}

/**
 * A Conversation groups Turns under a single `gen_ai.conversation.id`. It is not
 * itself an OTel span — children stamp the conversation id onto theirs.
 */
export class Conversation {
  private _ended = false;

  private constructor(
    public readonly agentName: string,
    public readonly model: string,
    public readonly conversationId: string,
    public readonly attributes: Attributes
  ) {}

  static create(opts: ConversationInit = {}): Conversation {
    const state = getGenaiState();
    if (state.conversation !== null) {
      throw new Error(
        'A Conversation is already active in this async chain. End it before starting a new one.'
      );
    }
    const conversation = new Conversation(
      opts.agentName ?? '',
      opts.model ?? '',
      opts.conversationId ?? uuidv7(),
      opts.attributes ?? {}
    );
    state.conversation = conversation;
    return conversation;
  }

  startTurn(opts: TurnInit = {}): Turn {
    return Turn.create({
      ...opts,
      agentName: opts.agentName ?? this.agentName,
      model: opts.model ?? this.model,
      conversationId: this.conversationId,
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
