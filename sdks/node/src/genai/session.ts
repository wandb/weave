import {uuidv7} from 'uuidv7';

import {_getGenaiState} from './context';
import {Turn, type TurnInit} from './turn';

export interface SessionInit {
  agentName?: string;
  model?: string;
  /** Conversation ID propagated to every span under this session as
   *  `gen_ai.conversation.id`. Auto-generated if omitted. */
  sessionId?: string;
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
    public readonly sessionId: string
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
      opts.sessionId ?? uuidv7()
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

  end(): void {
    if (this._ended) {
      return;
    }
    this._ended = true;
    const state = _getGenaiState();
    // Cascade: end any active descendants innermost-first so each child span
    // closes before its parent.
    if (state.llm) {
      state.llm.end();
    }
    if (state.turn) {
      state.turn.end();
    }
    if (state.session === this) {
      state.session = null;
    }
  }
}
