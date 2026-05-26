import {type Span, SpanKind, SpanStatusCode} from '@opentelemetry/api';

import type {ChildSpanContext} from './common';
import {getWeaveTracer} from './provider';
import {
  ATTR_GEN_AI_CONVERSATION_ID,
  ATTR_GEN_AI_OPERATION_NAME,
  ATTR_GEN_AI_TOOL_CALL_ARGUMENTS,
  ATTR_GEN_AI_TOOL_CALL_ID,
  ATTR_GEN_AI_TOOL_CALL_RESULT,
  ATTR_GEN_AI_TOOL_NAME,
  WEAVE_GENAI_TRACER_NAME,
} from './semconv';

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

  static create(opts: ToolInit & ChildSpanContext): Tool {
    const tracer = getWeaveTracer(WEAVE_GENAI_TRACER_NAME);
    const attributes: Record<string, string> = {
      [ATTR_GEN_AI_OPERATION_NAME]: 'execute_tool',
      [ATTR_GEN_AI_TOOL_NAME]: opts.name,
    };
    if (opts.toolCallId) {
      attributes[ATTR_GEN_AI_TOOL_CALL_ID] = opts.toolCallId;
    }
    if (opts.args) {
      attributes[ATTR_GEN_AI_TOOL_CALL_ARGUMENTS] = opts.args;
    }
    if (opts.conversationId) {
      attributes[ATTR_GEN_AI_CONVERSATION_ID] = opts.conversationId;
    }
    const span = tracer.startSpan(
      'execute_tool',
      {kind: SpanKind.INTERNAL, attributes},
      opts.parentContext
    );
    return new Tool(span, opts.name, opts.args ?? '', opts.toolCallId ?? '');
  }

  end(opts?: {error?: Error}): void {
    if (this._ended) {
      return;
    }
    this._ended = true;
    if (this.result !== undefined) {
      this.span.setAttribute(ATTR_GEN_AI_TOOL_CALL_RESULT, this.result);
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
