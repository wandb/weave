import {
  type Span,
  SpanKind,
  SpanStatusCode,
  type TimeInput,
} from '@opentelemetry/api';

import type {ChildSpanContext} from './common';
import {getWeaveTracer} from './provider';
import {SpanBase} from './spanBase';
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
  /** Backdate the span's start time. Used when reconstructing tool spans from
   *  post-hoc data (e.g. transcript replay). */
  startTime?: TimeInput;
}

/**
 * A tool invocation. Emits an `execute_tool` span carrying the tool name,
 * the JSON-encoded arguments, the tool-call id, and the result.
 *
 * Created by `weave.startTool()` (or `turn.startTool()`, or
 * `llm.startTool()`) and terminated with `end()`. Assign `result` before
 * calling `end()` to record the tool's output on the span.
 *
 * @example
 * const tool = weave.startTool({
 *   name: tc.function.name,
 *   args: tc.function.arguments,
 *   toolCallId: tc.id,
 * });
 * try {
 *   tool.result = await wikipediaSearch(JSON.parse(tc.function.arguments));
 * } finally {
 *   tool.end();
 * }
 */
export class Tool extends SpanBase {
  /**
   * Tool output as a string. Recorded on `gen_ai.tool.call.result` at `end()`.
   */
  result?: string;

  private constructor(
    span: Span,
    public readonly name: string,
    public readonly args: string,
    public readonly toolCallId: string
  ) {
    super(span);
  }

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
      {
        kind: SpanKind.INTERNAL,
        attributes,
        ...(opts.startTime !== undefined ? {startTime: opts.startTime} : {}),
      },
      opts.parentContext
    );
    return new Tool(span, opts.name, opts.args ?? '', opts.toolCallId ?? '');
  }

  /**
   * Flush `result` to the span and close it. Idempotent. Pass `error` to mark
   * the span as failed; pass `endTime` to backdate the close.
   */
  end(opts?: {error?: Error; endTime?: TimeInput}): void {
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
    this.span.end(opts?.endTime);
  }
}
