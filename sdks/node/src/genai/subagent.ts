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
  ATTR_GEN_AI_AGENT_NAME,
  ATTR_GEN_AI_CONVERSATION_ID,
  ATTR_GEN_AI_OPERATION_NAME,
  ATTR_GEN_AI_REQUEST_MODEL,
  WEAVE_GENAI_TRACER_NAME,
} from './semconv';

export interface SubAgentInit {
  name: string;
  model?: string;
  /** Backdate the span's start time. Used when reconstructing agent spans from
   *  post-hoc data (e.g. transcript replay). */
  startTime?: TimeInput;
}

/**
 * A nested agent invocation — used when the current agent hands work to
 * another named agent (e.g. a planner calling a researcher). Emits an
 * `invoke_agent` span tagged with the sub-agent's name and (optionally)
 * its model.
 *
 * Created by `weave.startSubagent()` (or `turn.startAgent()`, or
 * `llm.startAgent()`) and terminated with `end()`.
 *
 * @example
 * const sub = weave.startSubagent({name: 'researcher', model: 'gpt-4o'});
 * try {
 *   // ... orchestrate the sub-agent's LLM/Tool calls ...
 * } finally {
 *   sub.end();
 * }
 */
export class SubAgent extends SpanBase {
  private constructor(
    span: Span,
    public readonly name: string,
    public readonly model: string
  ) {
    super(span);
  }

  static create(opts: SubAgentInit & ChildSpanContext): SubAgent {
    const tracer = getWeaveTracer(WEAVE_GENAI_TRACER_NAME);
    const attributes: Record<string, string> = {
      [ATTR_GEN_AI_OPERATION_NAME]: 'invoke_agent',
      [ATTR_GEN_AI_AGENT_NAME]: opts.name,
    };
    if (opts.model) {
      attributes[ATTR_GEN_AI_REQUEST_MODEL] = opts.model;
    }
    if (opts.conversationId) {
      attributes[ATTR_GEN_AI_CONVERSATION_ID] = opts.conversationId;
    }
    const span = tracer.startSpan(
      'invoke_agent',
      {
        kind: SpanKind.CLIENT,
        attributes,
        ...(opts.startTime !== undefined ? {startTime: opts.startTime} : {}),
      },
      opts.parentContext
    );
    return new SubAgent(span, opts.name, opts.model ?? '');
  }

  /**
   * Close the SubAgent span. Idempotent. Pass `error` to mark it as failed;
   * pass `endTime` to backdate the close.
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
  }
}
