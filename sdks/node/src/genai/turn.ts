import {
  type Context,
  ROOT_CONTEXT,
  type Span,
  SpanKind,
  SpanStatusCode,
  type TimeInput,
  trace,
} from '@opentelemetry/api';

import {_getGenaiState} from './context';
import {LLM, type LLMInit} from './llm';
import {getWeaveTracer} from './provider';
import {SpanBase} from './spanBase';
import {
  ATTR_GEN_AI_AGENT_NAME,
  ATTR_GEN_AI_CONVERSATION_ID,
  ATTR_GEN_AI_OPERATION_NAME,
  ATTR_GEN_AI_REQUEST_MODEL,
  WEAVE_GENAI_TRACER_NAME,
} from './semconv';
import {SubAgent, type SubAgentInit} from './subagent';
import {Tool, type ToolInit} from './tool';

export interface TurnInit {
  agentName?: string;
  model?: string;
  /** Backdate the span's start time. Used when reconstructing agent spans from
   *  post-hoc data (e.g. transcript replay). */
  startTime?: TimeInput;
}

/**
 * An agent invocation. Typically wraps the work to respond to a single
 * user message. Emits an `invoke_agent` span and acts as the root of the
 * trace for that turn: it is always started under `ROOT_CONTEXT` so it
 * never accidentally inherits a parent from another OTel-instrumented
 * library.
 *
 * Created by `weave.startTurn()` (or `session.startTurn()`) and
 * terminated with `end()`. Only one Turn may be active in an async chain.
 * Children (LLM, Tool, SubAgent) attach via the `startLLM`, `startTool`,
 * `startSubagent` methods.
 *
 * @example
 * const turn = weave.startTurn({agentName: 'research-bot', model: MODEL});
 * try {
 *   const llm = turn.startLLM({model: MODEL, providerName: 'openai'});
 *   // ...
 *   llm.end();
 * } finally {
 *   turn.end();
 * }
 */
export class Turn extends SpanBase {
  private constructor(
    span: Span,
    private readonly context: Context,
    private readonly conversationId: string,
    public readonly agentName: string,
    public readonly model: string
  ) {
    super(span);
  }

  static create(opts: TurnInit & {conversationId?: string} = {}): Turn {
    const state = _getGenaiState();
    if (state.turn !== null) {
      throw new Error(
        'A Turn is already active in this async chain. End it before starting a new one.'
      );
    }
    const tracer = getWeaveTracer(WEAVE_GENAI_TRACER_NAME);
    const attributes: Record<string, string> = {
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
    // Pass ROOT_CONTEXT explicitly so Turn is always a root span — never
    // accidentally inherits a parent from some other OTel-instrumented
    // library's active context.
    const span = tracer.startSpan(
      'invoke_agent',
      {
        kind: SpanKind.CLIENT,
        attributes,
        ...(opts.startTime !== undefined ? {startTime: opts.startTime} : {}),
      },
      ROOT_CONTEXT
    );
    const turn = new Turn(
      span,
      trace.setSpan(ROOT_CONTEXT, span),
      opts.conversationId ?? '',
      opts.agentName ?? '',
      opts.model ?? ''
    );
    state.turn = turn;
    return turn;
  }

  /** Start a child LLM span under this Turn. */
  startLLM(opts: LLMInit): LLM {
    return LLM.create({
      ...opts,
      parentContext: this.context,
      conversationId: this.conversationId,
    });
  }

  /** Start a child Tool span under this Turn. */
  startTool(opts: ToolInit): Tool {
    return Tool.create({
      ...opts,
      parentContext: this.context,
      conversationId: this.conversationId,
    });
  }

  /** Start a child SubAgent span under this Turn. */
  startSubagent(opts: SubAgentInit): SubAgent {
    return SubAgent.create({
      ...opts,
      parentContext: this.context,
      conversationId: this.conversationId,
    });
  }

  /**
   * Close the Turn span. Idempotent. Pass `error` to mark it as failed; pass
   * `endTime` to backdate the close.
   */
  end(opts?: {error?: Error; endTime?: TimeInput}): void {
    if (this._ended) {
      return;
    }
    this._ended = true;
    if (opts?.error) {
      this.span.recordException(opts.error);
      this.span.setStatus({
        code: SpanStatusCode.ERROR,
        message: opts.error.message,
      });
    }
    this.span.end(opts?.endTime);
    const state = _getGenaiState();
    if (state.turn === this) {
      state.turn = null;
    }
  }
}
