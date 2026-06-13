import {type Context, type Span, SpanKind, trace} from '@opentelemetry/api';

import type {ChildSpanContext} from './common';
import {LLM, type LLMInit} from './llm';
import {getWeaveTracer} from './provider';
import {SpanBase, type SpanEndOptions, type SpanInitBase} from './spanBase';
import {
  ATTR_GEN_AI_AGENT_NAME,
  ATTR_GEN_AI_CONVERSATION_ID,
  ATTR_GEN_AI_OPERATION_NAME,
  ATTR_GEN_AI_REQUEST_MODEL,
  WEAVE_GENAI_TRACER_NAME,
} from './semconv';
import {Tool, type ToolInit} from './tool';

export interface SubAgentInit extends SpanInitBase {
  name: string;
  model?: string;
}

/**
 * A nested agent invocation — used when the current agent hands work to
 * another named agent (e.g. a planner calling a researcher). Emits an
 * `invoke_agent` span tagged with the sub-agent's name and (optionally)
 * its model.
 *
 * Created by `weave.startSubagent()` (or `turn.startSubagent()`, or
 * `llm.startSubagent()`) and terminated with `end()`. Children (LLM, Tool,
 * SubAgent) attach via the `startLLM`, `startTool`, `startSubagent` methods,
 * so a sub-agent's own model calls and tools nest under its `invoke_agent`
 * span rather than flattening onto the parent Turn.
 *
 * @example
 * const sub = weave.startSubagent({name: 'researcher', model: 'gpt-4o'});
 * try {
 *   const llm = sub.startLLM({model: 'gpt-4o', providerName: 'openai'});
 *   // ... orchestrate the sub-agent's LLM/Tool calls ...
 *   llm.end();
 * } finally {
 *   sub.end();
 * }
 */
export class SubAgent extends SpanBase {
  private constructor(
    span: Span,
    private readonly context: Context,
    private readonly conversationId: string,
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
      {kind: SpanKind.CLIENT, attributes, startTime: opts.startTime},
      opts.parentContext
    );
    return new SubAgent(
      span,
      trace.setSpan(opts.parentContext, span),
      opts.conversationId ?? '',
      opts.name,
      opts.model ?? ''
    );
  }

  /** Start a child LLM span nested under this SubAgent. */
  startLLM(opts: LLMInit): LLM {
    return LLM.create({
      ...opts,
      parentContext: this.context,
      conversationId: this.conversationId,
    });
  }

  /** Start a child Tool span nested under this SubAgent. */
  startTool(opts: ToolInit): Tool {
    return Tool.create({
      ...opts,
      parentContext: this.context,
      conversationId: this.conversationId,
    });
  }

  /** Start a nested SubAgent span under this SubAgent. */
  startSubagent(opts: SubAgentInit): SubAgent {
    return SubAgent.create({
      ...opts,
      parentContext: this.context,
      conversationId: this.conversationId,
    });
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
