import {uuidv7} from 'uuidv7';

import {_currentSession} from './context';
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
  private readonly _previousSession: Session | undefined;

  private constructor(
    public readonly agentName: string,
    public readonly model: string,
    public readonly sessionId: string
  ) {
    this._previousSession = _currentSession.getStore();
    _currentSession.enterWith(this);
  }

  static create(opts: SessionInit = {}): Session {
    return new Session(
      opts.agentName ?? '',
      opts.model ?? '',
      opts.sessionId ?? uuidv7()
    );
  }

  startTurn(opts: TurnInit = {}): Turn {
    return Turn.create({
      agentName: opts.agentName ?? this.agentName,
      model: opts.model ?? this.model,
      userMessage: opts.userMessage,
      conversationId: this.sessionId,
    });
  }

  end(): void {
    if (this._ended) {
      return;
    }
    this._ended = true;
    // Session emits no span — only the AsyncLocalStorage restore is meaningful here.
    _currentSession.enterWith(this._previousSession);
  }
}
