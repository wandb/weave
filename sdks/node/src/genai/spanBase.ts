import type {Attributes, Span, TimeInput} from '@opentelemetry/api';

/**
 * Shared base for the four GenAI span wrappers (`Tool`, `LLM`, `SubAgent`,
 * `Turn`). Holds the underlying OTel span plus the `_ended` guard and exposes
 * the common escape-hatch mutators so every span type gets an identical
 * surface.
 *
 * Mirrors the Python SDK's `_SpanBase` mixin (wandb/weave#7131): rather than
 * re-declaring `setAttributes`/`addEvent` on each class, the implementation
 * lives here once and covers all four uniformly.
 *
 * All mutators are no-ops after `end()` — the span is closed, so further
 * mutation can no longer reach the trace — and return `this` for chaining.
 */
export abstract class SpanBase {
  protected _ended = false;

  protected constructor(protected readonly span: Span) {}

  /**
   * Set multiple attributes on the span at once. No-op after `end()`. Mirrors
   * OTel `Span.setAttributes` (and the Python SDK's `set_attributes`).
   *
   * @example
   * span.setAttributes({'weave.tag': 'prod', 'gen_ai.response.id': id});
   */
  setAttributes(attributes: Attributes): this {
    if (this._ended) return this;
    this.span.setAttributes(attributes);
    return this;
  }

  /**
   * Add a named event to the span. Useful for marking non-span moments such as
   * context compaction, tool-loop detection, or guardrail trips. No-op after
   * `end()`. Mirrors OTel `Span.addEvent`.
   *
   * @example
   * span.addEvent('context_compacted', {removedMessages: 12});
   */
  addEvent(name: string, attributes?: Attributes, startTime?: TimeInput): this {
    if (this._ended) return this;
    this.span.addEvent(name, attributes, startTime);
    return this;
  }
}
