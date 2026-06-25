import type {Attributes} from '@opentelemetry/api';
import {uuidv7} from 'uuidv7';

import {_getGenaiState} from './context';
import {Turn, type TurnInit} from './turn';
import type {SpanEndOptions} from './spanBase';

export interface SessionInit {
  agentName?: string;
  model?: string;
  /** Conversation ID propagated to every span under this session as
   *  `gen_ai.conversation.id`. Auto-generated if omitted. */
  sessionId?: string;
  /**
   * Custom attributes stamped on every span the session emits.
   *
   * A key here that collides with a span's own `gen_ai.*` / `weave.*`
   * attribute is unsupported; the span's value wins.
   */
  attributes?: Attributes;
}

/**
 * A Session groups Turns under a single `gen_ai.conversation.id`. It is not
 * itself an OTel span — children stamp the conversation id onto theirs.
 */
export class Session {
  private _ended = false;

  private constructor(
    public readonly agentName: string,
    public readonly model: string,
    public readonly sessionId: string,
    public readonly attributes: Attributes
  ) {}

  static create(opts: SessionInit = {}): Session {
    const state = _getGenaiState();
    if (state.session !== null) {
      throw new Error(
        'A Session is already active in this async chain. End it before starting a new one.'
      );
    }
    const session = new Session(
      opts.agentName ?? '',
      opts.model ?? '',
      opts.sessionId ?? uuidv7(),
      opts.attributes ?? {}
    );
    state.session = session;
    return session;
  }

  startTurn(opts: TurnInit = {}): Turn {
    return Turn.create({
      ...opts,
      agentName: opts.agentName ?? this.agentName,
      model: opts.model ?? this.model,
      conversationId: this.sessionId,
    });
  }

  end(opts?: SpanEndOptions): void {
    if (this._ended) {
      return;
    }
    this._ended = true;
    const state = _getGenaiState();
    // Cascade: end any active descendants innermost-first so each child span
    // closes before its parent.
    if (state.llm) {
      state.llm.end(opts);
    }
    if (state.turn) {
      state.turn.end(opts);
    }
    if (state.session === this) {
      state.session = null;
    }
  }
}
