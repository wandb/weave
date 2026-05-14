import {uuidv7} from 'uuidv7';

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
  private constructor(
    public readonly agentName: string,
    public readonly model: string,
    public readonly sessionId: string
  ) {}

  static async create(opts: SessionInit = {}): Promise<Session> {
    return new Session(
      opts.agentName ?? '',
      opts.model ?? '',
      opts.sessionId ?? uuidv7()
    );
  }

  async startTurn(opts: TurnInit = {}): Promise<Turn> {
    return Turn.create({
      agentName: opts.agentName ?? this.agentName,
      model: opts.model ?? this.model,
      userMessage: opts.userMessage,
      conversationId: this.sessionId,
    });
  }

  async end(): Promise<void> {
    // Session emits no span; this exists only to mirror the start/end
    // symmetry of the other classes.
  }
}
