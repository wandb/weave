import {
  type Context,
  ROOT_CONTEXT,
  type Span,
  SpanKind,
  SpanStatusCode,
  trace,
} from '@opentelemetry/api';

import {_getGenaiState} from './context';
import {LLM, type LLMInit} from './llm';
import {getWeaveTracer} from './provider';
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
}

export class Turn {
  private _ended = false;

  private constructor(
    private readonly span: Span,
    private readonly context: Context,
    private readonly conversationId: string,
    public readonly agentName: string,
    public readonly model: string
  ) {}

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
      {kind: SpanKind.CLIENT, attributes},
      ROOT_CONTEXT
    );

    span.addEvent('gen_ai.user.message', {
      'gen_ai.event.content': JSON.stringify({content: 'testing, 1, 2, 3'}),
    });

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

  startLLM(opts: LLMInit): LLM {
    return LLM.create({
      ...opts,
      parentContext: this.context,
      conversationId: this.conversationId,
    });
  }

  startTool(opts: ToolInit): Tool {
    return Tool.create({
      ...opts,
      parentContext: this.context,
      conversationId: this.conversationId,
    });
  }

  startSubagent(opts: SubAgentInit): SubAgent {
    return SubAgent.create({
      ...opts,
      parentContext: this.context,
      conversationId: this.conversationId,
    });
  }

  end(opts?: {error?: Error}): void {
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
    this.span.end();
    const state = _getGenaiState();
    if (state.turn === this) {
      state.turn = null;
    }
  }
}
