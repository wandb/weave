import {type Span, SpanKind, SpanStatusCode} from '@opentelemetry/api';

import type {ChildSpanContext} from './common';
import {getWeaveTracer} from './provider';
import {GEN_AI_ATTR, WEAVE_GENAI_TRACER_NAME} from './semconv';

export interface SubAgentInit {
  name: string;
  model?: string;
}

export class SubAgent {
  private _ended = false;

  private constructor(
    private readonly span: Span,
    public readonly name: string,
    public readonly model: string
  ) {}

  static create(opts: SubAgentInit & ChildSpanContext): SubAgent {
    const tracer = getWeaveTracer(WEAVE_GENAI_TRACER_NAME);
    const attributes: Record<string, string> = {
      [GEN_AI_ATTR.GEN_AI_OPERATION_NAME]: 'invoke_agent',
      [GEN_AI_ATTR.GEN_AI_AGENT_NAME]: opts.name,
    };
    if (opts.model) {
      attributes[GEN_AI_ATTR.GEN_AI_REQUEST_MODEL] = opts.model;
    }
    if (opts.conversationId) {
      attributes[GEN_AI_ATTR.GEN_AI_CONVERSATION_ID] = opts.conversationId;
    }
    const span = tracer.startSpan(
      'invoke_agent',
      {kind: SpanKind.CLIENT, attributes},
      opts.parentContext
    );
    return new SubAgent(span, opts.name, opts.model ?? '');
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
  }
}
