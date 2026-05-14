import {type Span, SpanKind, SpanStatusCode} from '@opentelemetry/api';

import type {ChildSpanContext} from './common';
import {getWeaveTracer} from './provider';
import {GEN_AI_ATTR, WEAVE_GENAI_TRACER_NAME} from './semconv';

export interface ToolInit {
  name: string;
  args?: string;
  toolCallId?: string;
}

export class Tool {
  /** Free-form result captured before `end()`. */
  result?: string;

  private _ended = false;

  private constructor(
    private readonly span: Span,
    public readonly name: string,
    public readonly args: string,
    public readonly toolCallId: string
  ) {}

  static async create(opts: ToolInit & ChildSpanContext): Promise<Tool> {
    const tracer = getWeaveTracer(WEAVE_GENAI_TRACER_NAME);
    const attributes: Record<string, string> = {
      [GEN_AI_ATTR.GEN_AI_OPERATION_NAME]: 'execute_tool',
      [GEN_AI_ATTR.GEN_AI_TOOL_NAME]: opts.name,
    };
    if (opts.toolCallId) {
      attributes[GEN_AI_ATTR.GEN_AI_TOOL_CALL_ID] = opts.toolCallId;
    }
    if (opts.args) {
      attributes[GEN_AI_ATTR.GEN_AI_TOOL_CALL_ARGUMENTS] = opts.args;
    }
    if (opts.conversationId) {
      attributes[GEN_AI_ATTR.GEN_AI_CONVERSATION_ID] = opts.conversationId;
    }
    const span = tracer.startSpan(
      'execute_tool',
      {kind: SpanKind.INTERNAL, attributes},
      opts.parentContext
    );
    return new Tool(span, opts.name, opts.args ?? '', opts.toolCallId ?? '');
  }

  async end(opts?: {error?: Error}): Promise<void> {
    if (this._ended) {
      return;
    }
    this._ended = true;
    if (this.result !== undefined) {
      this.span.setAttribute(GEN_AI_ATTR.GEN_AI_TOOL_CALL_RESULT, this.result);
    }
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
