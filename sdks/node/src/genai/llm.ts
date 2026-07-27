import {
  type Attributes,
  type Context,
  type Span,
  SpanKind,
  trace,
} from '@opentelemetry/api';

import type {ChildSpanContext} from './common';
import {getGenaiState} from './context';
import {getWeaveTracer} from './provider';
import {SpanBase, type SpanEndOptions, type SpanInitBase} from './spanBase';
import {
  ATTR_GEN_AI_CONVERSATION_ID,
  ATTR_GEN_AI_INPUT_MESSAGES,
  ATTR_GEN_AI_OPERATION_NAME,
  ATTR_GEN_AI_OUTPUT_MESSAGES,
  ATTR_GEN_AI_OUTPUT_TYPE,
  ATTR_GEN_AI_PROVIDER_NAME,
  ATTR_GEN_AI_REQUEST_MODEL,
  ATTR_GEN_AI_RESPONSE_FINISH_REASONS,
  ATTR_GEN_AI_RESPONSE_ID,
  ATTR_GEN_AI_RESPONSE_MODEL,
  ATTR_GEN_AI_SYSTEM_INSTRUCTIONS,
  ATTR_GEN_AI_USAGE_CACHE_CREATION_INPUT_TOKENS,
  ATTR_GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS,
  ATTR_GEN_AI_USAGE_INPUT_TOKENS,
  ATTR_GEN_AI_USAGE_OUTPUT_TOKENS,
  ATTR_GEN_AI_USAGE_REASONING_OUTPUT_TOKENS,
  WEAVE_GENAI_TRACER_NAME,
} from './semconv';
import {SubAgent, type SubAgentInit} from './subagent';
import {Tool, type ToolInit} from './tool';
import type {Message, MessagePart, Modality, Reasoning, Usage} from './types';

export interface LLMInit extends SpanInitBase {
  model: string;
  providerName?: string;
  systemInstructions?: string[];
}

/** Discriminated union for `LLM.attachMedia`: pick one of content / uri / fileId. */
export type AttachMediaOpts =
  | {content: string; mimeType: string; modality: Modality}
  | {uri: string; modality: Modality}
  | {fileId: string; modality: Modality; mimeType?: string};

/**
 * An LLM call. Emits a `chat` span with `gen_ai.*` attributes.
 *
 * Created by `weave.startLLM()` (or `turn.startLLM()`) and terminated with
 * `end()`. Only one LLM may be active in an async context at a time; nest
 * tool/subagent calls under it via `startTool` / `startSubagent`.
 *
 * Populate `inputMessages` / `outputMessages` / `usage` / `reasoning` directly,
 * or via the helper functions (`output`, `think`, `attachMedia`, `record`).
 *
 * All recorded data is flushed to the span at `end()`.
 *
 * @example
 * const llm = weave.startLLM({model: 'gpt-4o-mini', providerName: 'openai'});
 *
 * try {
 *   llm.inputMessages = [{role: 'user', content: prompt}];
 *   const resp = await openai.chat.completions.create({...});
 *   llm.output(resp.choices[0].message.content ?? '');
 *   llm.record({usage: {inputTokens: resp.usage?.prompt_tokens}});
 * } finally {
 *   llm.end();
 * }
 *
 * @example
 * const llm = weave.startLLM({
 *   model: 'gpt-4o-mini',
 *   providerName: 'openai',
 *   systemInstructions: ['You are a helpful weather bot.'],
 *   startTime: new Date('2026-05-29T10:00:00.000Z'),
 * });
 *
 * try {
 *   // ... call the LLM, populate llm.outputMessages / usage ...
 * } finally {
 *   llm.end();
 * }
 */
export class LLM extends SpanBase {
  /** Mutable data populated between `create()` and `end()`. */

  /**
   * Input messages sent to the model. Flushed to `gen_ai.input.messages` on
   * `end()`.
   */
  inputMessages: Message[] = [];
  /**
   * Assistant messages returned by the model. Flushed to
   * `gen_ai.output.messages` on `end()`.
   */
  outputMessages: Message[] = [];
  /** Token counts and cache stats. Flushed to `gen_ai.usage.*` on `end()`. */
  usage: Usage = {};
  /**
   * Chain-of-thought content. Folded into the last assistant message as a
   * ReasoningPart at serialization time.
   */
  reasoning?: Reasoning;

  private _mediaAttachments: AttachMediaOpts[] = [];
  private _responseId?: string;
  private _responseModel?: string;
  private _finishReasons: string[] = [];
  private _outputType?: string;

  private constructor(
    span: Span,
    private readonly context: Context,
    private readonly conversationId: string,
    public readonly model: string,
    public readonly providerName: string,
    private readonly systemInstructions: string[],
    private readonly attributes: Attributes
  ) {
    super(span);
  }

  static create(opts: LLMInit & ChildSpanContext): LLM {
    const state = getGenaiState();
    if (state.llm !== null) {
      throw new Error(
        'An LLM is already active in this async chain. End it before starting a new one.'
      );
    }
    const tracer = getWeaveTracer(WEAVE_GENAI_TRACER_NAME);
    const attributes: Attributes = {...(opts.attributes ?? {})};
    const span = tracer.startSpan(
      'chat',
      {kind: SpanKind.CLIENT, attributes, startTime: opts.startTime},
      opts.parentContext
    );
    const llm = new LLM(
      span,
      trace.setSpan(opts.parentContext, span),
      opts.conversationId ?? '',
      opts.model,
      opts.providerName ?? '',
      opts.systemInstructions ?? [],
      opts.attributes ?? {}
    );
    state.llm = llm;
    return llm;
  }

  // ---------------------------------------------------------------------------
  // Enrichment surface
  // ---------------------------------------------------------------------------

  /** Append an assistant message to the response. */
  output(content: string): this {
    if (this._warnIfEnded('output')) {
      return this;
    }
    this.outputMessages.push({role: 'assistant', content});
    return this;
  }

  /** Set or extend the model's reasoning/chain-of-thought content. Accumulates
   *  into `this.reasoning.content`. Folded into the last assistant message as
   *  a `ReasoningPart` at serialization time, matching the Python SDK's
   *  on-the-wire shape. */
  think(content: string): this {
    if (this._warnIfEnded('think')) {
      return this;
    }
    if (this.reasoning === undefined) {
      this.reasoning = {content};
    } else {
      this.reasoning.content += content;
    }
    return this;
  }

  /** Stage a media attachment for the LLM call. Pick exactly one of
   *  `content` (inline base64 bytes), `uri` (URI reference), or `fileId`
   *  (pre-uploaded file id). The attachment is glued onto the last user
   *  message in `inputMessages` on `end()`. */
  attachMedia(opts: AttachMediaOpts): this {
    if (this._warnIfEnded('attachMedia')) {
      return this;
    }
    this._mediaAttachments.push(opts);
    return this;
  }

  /** Convenience for `attachMedia({uri, modality})`. */
  attachMediaUrl(url: string, opts: {modality: Modality}): this {
    if (this._warnIfEnded('attachMediaUrl')) {
      return this;
    }
    return this.attachMedia({uri: url, modality: opts.modality});
  }

  /**
   * Bulk-set any subset of the mutable fields. Replaces (does not merge).
   * Useful for assigning everything at once after a provider call returns.
   */
  record(opts: {
    inputMessages?: Message[];
    outputMessages?: Message[];
    usage?: Usage;
    reasoning?: Reasoning;
    responseId?: string;
    responseModel?: string;
    finishReasons?: string[];
    outputType?: string;
    mediaAttachments?: AttachMediaOpts[];
  }): this {
    if (this._warnIfEnded('record')) {
      return this;
    }
    if (opts.inputMessages !== undefined) {
      this.inputMessages = opts.inputMessages;
    }
    if (opts.outputMessages !== undefined) {
      this.outputMessages = opts.outputMessages;
    }
    if (opts.usage !== undefined) {
      this.usage = opts.usage;
    }
    if (opts.reasoning !== undefined) {
      this.reasoning = opts.reasoning;
    }
    if (opts.responseId !== undefined) {
      this._responseId = opts.responseId;
    }
    if (opts.responseModel !== undefined) {
      this._responseModel = opts.responseModel;
    }
    if (opts.finishReasons !== undefined) {
      this._finishReasons = opts.finishReasons;
    }
    if (opts.outputType !== undefined) {
      this._outputType = opts.outputType;
    }
    if (opts.mediaAttachments !== undefined) {
      this._mediaAttachments = opts.mediaAttachments;
    }
    return this;
  }

  // ---------------------------------------------------------------------------
  // Child factories
  // ---------------------------------------------------------------------------

  /** Start a child Tool span nested under this LLM. */
  startTool(opts: ToolInit): Tool {
    return Tool.create({
      ...opts,
      parentContext: this.context,
      conversationId: this.conversationId,
      attributes: this.attributes,
    });
  }

  /** Start a child SubAgent span nested under this LLM. */
  startSubagent(opts: SubAgentInit): SubAgent {
    return SubAgent.create({
      ...opts,
      parentContext: this.context,
      conversationId: this.conversationId,
      attributes: this.attributes,
    });
  }

  // ---------------------------------------------------------------------------
  // Lifecycle
  // ---------------------------------------------------------------------------

  /** Flush accumulated state and close the span. Idempotent. Pass `error` to mark failed; pass `endTime` to backdate the close. */
  end(opts?: SpanEndOptions): void {
    if (this._ended) {
      return;
    }
    this._ended = true;

    this.span.setAttribute(ATTR_GEN_AI_OPERATION_NAME, 'chat');
    if (this.model) {
      this.span.setAttribute(ATTR_GEN_AI_REQUEST_MODEL, this.model);
    }
    if (this.providerName) {
      this.span.setAttribute(ATTR_GEN_AI_PROVIDER_NAME, this.providerName);
    }
    if (this.conversationId) {
      this.span.setAttribute(ATTR_GEN_AI_CONVERSATION_ID, this.conversationId);
    }
    if (this.systemInstructions.length > 0) {
      this.span.setAttribute(
        ATTR_GEN_AI_SYSTEM_INSTRUCTIONS,
        JSON.stringify(
          this.systemInstructions.map(content => ({type: 'text', content}))
        )
      );
    }

    // Fold reasoning into the last assistant message as a ReasoningPart so
    // the wire format matches the Python SDK (which serializes reasoning
    // inside gen_ai.output.messages, not as a separate attribute).
    if (this.reasoning?.content) {
      const parts = this._ensureLastAssistantParts();
      parts.push({type: 'reasoning', content: this.reasoning.content});
    }

    // Throw staged media attachments onto the last user message in `inputMessages`.
    if (this._mediaAttachments.length > 0) {
      const parts = this._ensureLastInputParts();
      for (const m of this._mediaAttachments) {
        let part: MessagePart;
        if ('content' in m) {
          part = {type: 'blob', ...m};
        } else if ('uri' in m) {
          part = {type: 'uri', ...m};
        } else {
          part = {type: 'file', ...m};
        }
        parts.push(part);
      }
    }

    if (this.inputMessages.length > 0) {
      this.span.setAttribute(
        ATTR_GEN_AI_INPUT_MESSAGES,
        JSON.stringify(this.inputMessages)
      );
    }
    if (this.outputMessages.length > 0) {
      this.span.setAttribute(
        ATTR_GEN_AI_OUTPUT_MESSAGES,
        JSON.stringify(this.outputMessages)
      );
    }

    const u = this.usage;
    if (u.inputTokens !== undefined) {
      this.span.setAttribute(ATTR_GEN_AI_USAGE_INPUT_TOKENS, u.inputTokens);
    }
    if (u.outputTokens !== undefined) {
      this.span.setAttribute(ATTR_GEN_AI_USAGE_OUTPUT_TOKENS, u.outputTokens);
    }
    if (u.reasoningTokens !== undefined) {
      this.span.setAttribute(
        ATTR_GEN_AI_USAGE_REASONING_OUTPUT_TOKENS,
        u.reasoningTokens
      );
    }
    if (u.cacheCreationInputTokens !== undefined) {
      this.span.setAttribute(
        ATTR_GEN_AI_USAGE_CACHE_CREATION_INPUT_TOKENS,
        u.cacheCreationInputTokens
      );
    }
    if (u.cacheReadInputTokens !== undefined) {
      this.span.setAttribute(
        ATTR_GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS,
        u.cacheReadInputTokens
      );
    }

    if (this._responseId) {
      this.span.setAttribute(ATTR_GEN_AI_RESPONSE_ID, this._responseId);
    }
    if (this._responseModel) {
      this.span.setAttribute(ATTR_GEN_AI_RESPONSE_MODEL, this._responseModel);
    }
    if (this._finishReasons.length > 0) {
      this.span.setAttribute(
        ATTR_GEN_AI_RESPONSE_FINISH_REASONS,
        this._finishReasons
      );
    }
    if (this._outputType) {
      this.span.setAttribute(ATTR_GEN_AI_OUTPUT_TYPE, this._outputType);
    }

    this._closeSpan(opts);
    const state = getGenaiState();
    if (state.llm === this) {
      state.llm = null;
    }
  }

  // ---------------------------------------------------------------------------
  // Private helpers
  // ---------------------------------------------------------------------------

  /** Return the parts array of the last assistant message, creating both the
   *  message and the parts array if needed. If the existing assistant message
   *  has a `content` string but no parts, promote that content to a TextPart
   *  so subsequent appends compose cleanly. */
  private _ensureLastAssistantParts(): MessagePart[] {
    let last = this.outputMessages[this.outputMessages.length - 1];
    if (last === undefined || last.role !== 'assistant') {
      last = {role: 'assistant'};
      this.outputMessages.push(last);
    }
    return ensureParts(last);
  }

  /** Same as above, but for the last input message (creating a user message
   *  if `inputMessages` is empty). Media parts attach here. */
  private _ensureLastInputParts(): MessagePart[] {
    let last = this.inputMessages[this.inputMessages.length - 1];
    if (last === undefined) {
      last = {role: 'user'};
      this.inputMessages.push(last);
    }
    return ensureParts(last);
  }
}

function ensureParts(msg: Message): MessagePart[] {
  if (msg.parts === undefined) {
    msg.parts = [];
    if (msg.content !== undefined) {
      msg.parts.push({type: 'text', content: msg.content});
      msg.content = undefined;
    }
  }
  return msg.parts;
}
