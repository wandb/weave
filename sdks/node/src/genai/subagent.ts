import {type Attributes, type Span, SpanKind} from '@opentelemetry/api';

import type {ChildSpanContext} from './common';
import {getGenaiState} from './context';
import {getWeaveTracer} from './provider';
import {SpanBase, type SpanEndOptions, type SpanInitBase} from './spanBase';
import {
  ATTR_GEN_AI_AGENT_NAME,
  ATTR_GEN_AI_CONVERSATION_ID,
  ATTR_GEN_AI_OPERATION_NAME,
  ATTR_GEN_AI_REQUEST_MODEL,
  ATTR_GEN_AI_SYSTEM_INSTRUCTIONS,
  WEAVE_GENAI_TRACER_NAME,
} from './semconv';

export interface SubAgentInit extends SpanInitBase {
  name: string;
  model?: string;
  systemInstructions?: string[];
}

/**
 * A nested agent invocation — used when the current agent hands work to
 * another named agent (e.g. a planner calling a researcher). Emits an
 * `invoke_agent` span tagged with the sub-agent's name and (optionally)
 * its model.
 *
 * Created by `weave.startSubagent()` (or `turn.startSubagent()`, or
 * `llm.startSubagent()`) and terminated with `end()`.
 *
 * @example
 * const sub = weave.startSubagent({name: 'researcher'});
 *
 * try {
 *   // ... orchestrate the sub-agent's LLM/Tool calls ...
 * } finally {
 *   sub.end();
 * }
 *
 * @example
 * const sub = weave.startSubagent({
 *   name: 'researcher',
 *   model: 'gpt-4o',
 *   systemInstructions: ['Find authoritative sources before answering.'],
 *   startTime: new Date('2026-05-29T10:00:00.000Z'),
 * });
 *
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
    const state = getGenaiState();
    const tracer = getWeaveTracer(WEAVE_GENAI_TRACER_NAME);
    const attributes: Attributes = {
      ...(state.conversation?.attributes ?? {}),
      [ATTR_GEN_AI_OPERATION_NAME]: 'invoke_agent',
      [ATTR_GEN_AI_AGENT_NAME]: opts.name,
    };
    if (opts.model) {
      attributes[ATTR_GEN_AI_REQUEST_MODEL] = opts.model;
    }
    if (opts.conversationId) {
      attributes[ATTR_GEN_AI_CONVERSATION_ID] = opts.conversationId;
    }
    if (opts.systemInstructions && opts.systemInstructions.length > 0) {
      attributes[ATTR_GEN_AI_SYSTEM_INSTRUCTIONS] = JSON.stringify(
        opts.systemInstructions.map(content => ({type: 'text', content}))
      );
    }
    const span = tracer.startSpan(
      'invoke_agent',
      {kind: SpanKind.CLIENT, attributes, startTime: opts.startTime},
      opts.parentContext
    );
    return new SubAgent(span, opts.name, opts.model ?? '');
  }

  /**
   * Close the SubAgent span. Idempotent. Pass `error` to mark it as failed;
   * pass `endTime` to backdate the close.
   */
  end(opts?: SpanEndOptions): void {
    if (this._ended) {
      return;
    }
    this._ended = true;
    this._closeSpan(opts);
  }
}
