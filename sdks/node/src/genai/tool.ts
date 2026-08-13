import {type Attributes, type Span, SpanKind} from '@opentelemetry/api';

import type {ChildSpanContext} from './common';
import {getWeaveTracer} from './provider';
import {SpanBase, type SpanEndOptions, type SpanInitBase} from './spanBase';
import {
  ATTR_GEN_AI_CONVERSATION_ID,
  ATTR_GEN_AI_OPERATION_NAME,
  ATTR_GEN_AI_TOOL_CALL_ARGUMENTS,
  ATTR_GEN_AI_TOOL_CALL_ID,
  ATTR_GEN_AI_TOOL_CALL_RESULT,
  ATTR_GEN_AI_TOOL_NAME,
  WEAVE_GENAI_TRACER_NAME,
} from './semconv';
import type {JsonObject, JsonValue} from './types';

export interface ToolInit extends SpanInitBase {
  name: string;
  /** A JSON object, or a pre-serialized string recorded as-is. */
  args?: JsonObject | string;
  toolCallId?: string;
}

export interface ToolEndOptions extends SpanEndOptions {
  /** A JSON value. Strings are recorded as-is; other values are serialized. */
  result?: JsonValue;
}

function serializeToolValue(value: JsonValue | undefined): string | undefined {
  if (value === undefined) {
    return undefined;
  }
  if (typeof value === 'string') {
    return value;
  }
  try {
    return JSON.stringify(value) ?? '[unserializable]';
  } catch {
    return '[unserializable]';
  }
}

/**
 * A tool invocation. Emits an `execute_tool` span carrying the tool name,
 * the arguments, the tool-call id, and the result. String arguments and
 * results are recorded as-is; other JSON values are serialized.
 *
 * Created by `weave.startTool()` (or `turn.startTool()`, or
 * `llm.startTool()`) and terminated with `end()`, which accepts the result and
 * optional error metadata.
 *
 * @example
 * const tool = weave.startTool({name: 'get_weather', args: {city: 'Tokyo'}});
 * try {
 *   const result = await getWeather('Tokyo');
 *   tool.end({result});
 * } catch (error) {
 *   tool.end({error: error as Error, errorType: 'weather_error'});
 *   throw error;
 * }
 */
export class Tool extends SpanBase {
  /**
   * Tool output as a string. Prefer passing `result` to `end()`.
   *
   * @deprecated Pass `result` to `end()` instead.
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
    const args = serializeToolValue(opts.args);
    const attributes: Attributes = {
      ...(opts.attributes ?? {}),
      [ATTR_GEN_AI_OPERATION_NAME]: 'execute_tool',
      [ATTR_GEN_AI_TOOL_NAME]: opts.name,
    };
    if (opts.toolCallId) {
      attributes[ATTR_GEN_AI_TOOL_CALL_ID] = opts.toolCallId;
    }
    if (args !== undefined) {
      attributes[ATTR_GEN_AI_TOOL_CALL_ARGUMENTS] = args;
    }
    if (opts.conversationId) {
      attributes[ATTR_GEN_AI_CONVERSATION_ID] = opts.conversationId;
    }
    const span = tracer.startSpan(
      'execute_tool',
      {kind: SpanKind.INTERNAL, attributes, startTime: opts.startTime},
      opts.parentContext
    );
    return new Tool(span, opts.name, args ?? '', opts.toolCallId ?? '');
  }

  /**
   * Record an optional result and error type, then close the span. Idempotent.
   * Pass `error` and an optional `errorType` to mark the span as failed, and
   * `endTime` to backdate the close.
   */
  end(opts?: ToolEndOptions): void {
    if (this._ended) {
      return;
    }
    this._ended = true;
    const result =
      opts?.result === undefined
        ? this.result
        : serializeToolValue(opts.result);
    if (result !== undefined) {
      this.result = result;
      this.span.setAttribute(ATTR_GEN_AI_TOOL_CALL_RESULT, result);
    }
    this._closeSpan(opts);
  }
}
