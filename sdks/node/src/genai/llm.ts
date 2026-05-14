import {
  type Context,
  type Span,
  SpanKind,
  SpanStatusCode,
  trace,
} from '@opentelemetry/api';

import type {ChildSpanContext} from './common';
import {_currentLLM} from './context';
import {getWeaveTracer} from './provider';
import {GEN_AI_ATTR, WEAVE_GENAI_TRACER_NAME} from './semconv';
import {SubAgent, type SubAgentInit} from './subagent';
import {Tool, type ToolInit} from './tool';
import type {Message, Reasoning, Usage} from './types';

export interface LLMInit {
  model: string;
  providerName?: string;
  systemInstructions?: string[];
}

export class LLM {
  /** Mutable data populated between `create()` and `end()`. */
  inputMessages: Message[] = [];
  outputMessages: Message[] = [];
  usage: Usage = {};
  reasoning?: Reasoning;

  private _ended = false;
  private readonly _previousLLM: LLM | undefined;

  private constructor(
    private readonly span: Span,
    private readonly context: Context,
    private readonly conversationId: string,
    public readonly model: string,
    public readonly providerName: string,
    public readonly systemInstructions: string[]
  ) {
    this._previousLLM = _currentLLM.getStore();
    _currentLLM.enterWith(this);
  }

  static create(opts: LLMInit & ChildSpanContext): LLM {
    const tracer = getWeaveTracer(WEAVE_GENAI_TRACER_NAME);
    const attributes: Record<string, string> = {
      [GEN_AI_ATTR.GEN_AI_OPERATION_NAME]: 'chat',
      [GEN_AI_ATTR.GEN_AI_REQUEST_MODEL]: opts.model,
    };
    if (opts.providerName) {
      attributes[GEN_AI_ATTR.GEN_AI_PROVIDER_NAME] = opts.providerName;
    }
    if (opts.conversationId) {
      attributes[GEN_AI_ATTR.GEN_AI_CONVERSATION_ID] = opts.conversationId;
    }
    const span = tracer.startSpan(
      'chat',
      {kind: SpanKind.CLIENT, attributes},
      opts.parentContext
    );
    return new LLM(
      span,
      trace.setSpan(opts.parentContext, span),
      opts.conversationId ?? '',
      opts.model,
      opts.providerName ?? '',
      opts.systemInstructions ?? []
    );
  }

  startTool(opts: ToolInit): Tool {
    return Tool.create({
      ...opts,
      parentContext: this.context,
      conversationId: this.conversationId,
    });
  }

  startSubagent(opts: SubAgentInit): SubAgent {
    return SubAgent.create({
      ...opts,
      parentContext: this.context,
      conversationId: this.conversationId,
    });
  }

  end(opts?: {error?: Error}): void {
    if (this._ended) {
      return;
    }
    this._ended = true;

    if (this.inputMessages.length > 0) {
      this.span.setAttribute(
        GEN_AI_ATTR.GEN_AI_INPUT_MESSAGES,
        JSON.stringify(this.inputMessages)
      );
    }
    if (this.outputMessages.length > 0) {
      this.span.setAttribute(
        GEN_AI_ATTR.GEN_AI_OUTPUT_MESSAGES,
        JSON.stringify(this.outputMessages)
      );
    }

    const u = this.usage;
    if (u.inputTokens !== undefined) {
      this.span.setAttribute(
        GEN_AI_ATTR.GEN_AI_USAGE_INPUT_TOKENS,
        u.inputTokens
      );
    }
    if (u.outputTokens !== undefined) {
      this.span.setAttribute(
        GEN_AI_ATTR.GEN_AI_USAGE_OUTPUT_TOKENS,
        u.outputTokens
      );
    }
    if (u.reasoningTokens !== undefined) {
      this.span.setAttribute(
        GEN_AI_ATTR.GEN_AI_USAGE_REASONING_OUTPUT_TOKENS,
        u.reasoningTokens
      );
    }
    if (u.cacheCreationInputTokens !== undefined) {
      this.span.setAttribute(
        GEN_AI_ATTR.GEN_AI_USAGE_CACHE_CREATION_INPUT_TOKENS,
        u.cacheCreationInputTokens
      );
    }
    if (u.cacheReadInputTokens !== undefined) {
      this.span.setAttribute(
        GEN_AI_ATTR.GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS,
        u.cacheReadInputTokens
      );
    }

    if (opts?.error) {
      this.span.recordException(opts.error);
      this.span.setStatus({
        code: SpanStatusCode.ERROR,
        message: opts.error.message,
      });
    }
    this.span.end();
    _currentLLM.enterWith(this._previousLLM);
  }
}
