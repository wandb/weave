import {type Attributes, type Span, SpanKind} from '@opentelemetry/api';

import type {ChildSpanContext} from './common';
import {getGenaiState} from './context';
import {getWeaveTracer} from './provider';
import {SpanBase, type SpanEndOptions, type SpanInitBase} from './spanBase';
import {
  ATTR_GEN_AI_AGENT_DESCRIPTION,
  ATTR_GEN_AI_AGENT_ID,
  ATTR_GEN_AI_AGENT_NAME,
  ATTR_GEN_AI_AGENT_VERSION,
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
  agentId?: string;
  agentDescription?: string;
  agentVersion?: string;
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
type Opts = {
  span: Span;
  conversationId: string;
} & Required<Omit<SubAgentInit, 'startTime'>>;

export class SubAgent extends SpanBase {
  private _conversationId: string;
  private _name: string;
  private _model: string;
  private _systemInstructions: string[];
  private _agentId: string;
  private _agentDescription: string;
  private _agentVersion: string;

  public get name() {
    return this._name;
  }

  public get model() {
    return this._model;
  }

  private constructor(opts: Opts) {
    super(opts.span);
    this._conversationId = opts.conversationId;
    this._name = opts.name;
    this._model = opts.model;
    this._systemInstructions = opts.systemInstructions;
    this._agentId = opts.agentId;
    this._agentDescription = opts.agentDescription;
    this._agentVersion = opts.agentVersion;
  }

  static create(opts: SubAgentInit & ChildSpanContext): SubAgent {
    const state = getGenaiState();
    const tracer = getWeaveTracer(WEAVE_GENAI_TRACER_NAME);
    const attributes: Attributes = {...(state.conversation?.attributes ?? {})};
    const span = tracer.startSpan(
      'invoke_agent',
      {kind: SpanKind.CLIENT, attributes, startTime: opts.startTime},
      opts.parentContext
    );
    return new SubAgent({
      span,
      name: opts.name,
      model: opts.model ?? '',
      conversationId: opts.conversationId ?? '',
      systemInstructions: opts.systemInstructions ?? [],
      agentId: opts.agentId ?? '',
      agentDescription: opts.agentDescription ?? '',
      agentVersion: opts.agentVersion ?? '',
    });
  }

  /**
   * Bulk-set any fields. Replaces (does not merge).
   */
  record(opts: Partial<Omit<SubAgentInit, keyof SpanInitBase>>): this {
    if (this._warnIfEnded('record')) return this;

    if (opts.name !== undefined) {
      this._name = opts.name;
    }
    if (opts.model !== undefined) {
      this._model = opts.model;
    }
    if (opts.systemInstructions !== undefined) {
      this._systemInstructions = opts.systemInstructions;
    }
    if (opts.agentId !== undefined) {
      this._agentId = opts.agentId;
    }
    if (opts.agentDescription !== undefined) {
      this._agentDescription = opts.agentDescription;
    }
    if (opts.agentVersion !== undefined) {
      this._agentVersion = opts.agentVersion;
    }
    return this;
  }

  /**
   * Read current field values (to reflect mutations made via `record()`
   * since `start`) and close the span. Idempotent. Pass `error` to mark
   * it as failed; pass `endTime` to backdate the close.
   */
  end(opts?: SpanEndOptions): void {
    if (this._ended) {
      return;
    }
    this._ended = true;

    this.span.setAttribute(ATTR_GEN_AI_OPERATION_NAME, 'invoke_agent');
    this.span.setAttribute(ATTR_GEN_AI_AGENT_NAME, this._name);
    if (this._model) {
      this.span.setAttribute(ATTR_GEN_AI_REQUEST_MODEL, this._model);
    }
    if (this._conversationId) {
      this.span.setAttribute(ATTR_GEN_AI_CONVERSATION_ID, this._conversationId);
    }
    if (this._agentId) {
      this.span.setAttribute(ATTR_GEN_AI_AGENT_ID, this._agentId);
    }
    if (this._agentDescription) {
      this.span.setAttribute(
        ATTR_GEN_AI_AGENT_DESCRIPTION,
        this._agentDescription
      );
    }
    if (this._agentVersion) {
      this.span.setAttribute(ATTR_GEN_AI_AGENT_VERSION, this._agentVersion);
    }
    if (this._systemInstructions.length > 0) {
      this.span.setAttribute(
        ATTR_GEN_AI_SYSTEM_INSTRUCTIONS,
        JSON.stringify(
          this._systemInstructions.map(content => ({type: 'text', content}))
        )
      );
    }

    this._closeSpan(opts);
  }
}
