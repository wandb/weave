import {
  type Context,
  ROOT_CONTEXT,
  type Span,
  SpanKind,
  SpanStatusCode,
  trace,
} from '@opentelemetry/api';

import {LLM, type LLMInit} from './llm';
import {getWeaveTracer} from './provider';
import {GEN_AI_ATTR, WEAVE_GENAI_TRACER_NAME} from './semconv';
import {SubAgent, type SubAgentInit} from './subagent';
import {Tool, type ToolInit} from './tool';

export interface TurnInit {
  agentName?: string;
  model?: string;
  userMessage?: string;
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

  static async create(
    opts: TurnInit & {conversationId?: string} = {}
  ): Promise<Turn> {
    const tracer = getWeaveTracer(WEAVE_GENAI_TRACER_NAME);
    const attributes: Record<string, string> = {
      [GEN_AI_ATTR.GEN_AI_OPERATION_NAME]: 'invoke_agent',
    };
    if (opts.agentName) {
      attributes[GEN_AI_ATTR.GEN_AI_AGENT_NAME] = opts.agentName;
    }
    if (opts.model) {
      attributes[GEN_AI_ATTR.GEN_AI_REQUEST_MODEL] = opts.model;
    }
    if (opts.conversationId) {
      attributes[GEN_AI_ATTR.GEN_AI_CONVERSATION_ID] = opts.conversationId;
    }
    // Pass ROOT_CONTEXT explicitly so Turn is always a root span — never
    // accidentally inherits a parent from some other OTel-instrumented
    // library's active context.
    const span = tracer.startSpan(
      'invoke_agent',
      {kind: SpanKind.CLIENT, attributes},
      ROOT_CONTEXT
    );
    return new Turn(
      span,
      trace.setSpan(ROOT_CONTEXT, span),
      opts.conversationId ?? '',
      opts.agentName ?? '',
      opts.model ?? ''
    );
  }

  async llm(opts: LLMInit): Promise<LLM> {
    return LLM.create({
      ...opts,
      parentContext: this.context,
      conversationId: this.conversationId,
    });
  }

  async tool(opts: ToolInit): Promise<Tool> {
    return Tool.create({
      ...opts,
      parentContext: this.context,
      conversationId: this.conversationId,
    });
  }

  async subagent(opts: SubAgentInit): Promise<SubAgent> {
    return SubAgent.create({
      ...opts,
      parentContext: this.context,
      conversationId: this.conversationId,
    });
  }

  async end(opts?: {error?: Error}): Promise<void> {
    if (this._ended) return;
    this._ended = true;
    if (opts?.error) {
      this.span.recordException(opts.error);
      this.span.setStatus({
        code: SpanStatusCode.ERROR,
        message: opts.error.message,
      });
    }
    this.span.end();
  }
}
