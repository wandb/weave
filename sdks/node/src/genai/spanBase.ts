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
 * Mutating after `end()` warns and no-ops — the span is closed, so further
 * mutation can no longer reach the trace. All mutators return `this` for
 * chaining.
 */
export abstract class SpanBase {
  protected _ended = false;

  protected constructor(protected readonly span: Span) {}

  /**
   * Set multiple attributes on the span at once. Warns and no-ops after
   * `end()`. Mirrors OTel `Span.setAttributes` (and the Python SDK's
   * `set_attributes`).
   *
   * @example
   * span.setAttributes({'weave.tag': 'prod', 'gen_ai.response.id': id});
   */
  setAttributes(attributes: Attributes): this {
    if (this._warnIfEnded('setAttributes')) return this;
    this.span.setAttributes(attributes);
    return this;
  }

  /**
   * Add a named event to the span. Useful for marking non-span moments such as
   * context compaction, tool-loop detection, or guardrail trips. Warns and
   * no-ops after `end()`. Mirrors OTel `Span.addEvent`.
   *
   * @example
   * span.addEvent('context_compacted', {removedMessages: 12});
   */
  addEvent(name: string, attributes?: Attributes, startTime?: TimeInput): this {
    if (this._warnIfEnded('addEvent')) return this;
    this.span.addEvent(name, attributes, startTime);
    return this;
  }

  /**
   * Warn if called after `end()`. Returns `true` if the caller should
   * short-circuit; the span is already closed, so any further mutation can no
   * longer reach the trace. The warning names the concrete emitter type (e.g.
   * `weave.Tool.setAttributes(...)`) via the runtime constructor name.
   */
  protected _warnIfEnded(method: string): boolean {
    if (this._ended) {
      console.warn(
        `weave.${this.constructor.name}.${method}() called after end() — data will not be recorded on the span.`
      );
      return true;
    }
    return false;
  }
}
