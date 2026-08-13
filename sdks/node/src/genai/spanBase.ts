import {
  type Attributes,
  type Span,
  SpanStatusCode,
  type TimeInput,
} from '@opentelemetry/api';

import {ATTR_ERROR_TYPE} from './semconv';

/**
 * Init fields shared by every emitter's `create()` factory.
 *
 * `startTime` backdates the span's start — used when reconstructing spans
 * from post-hoc data (e.g. replaying a transcript), where the real
 * wall-clock window is only known once the call has finished. Undefined →
 * OTel stamps the current time, so the field is purely additive.
 */
export interface SpanInitBase {
  startTime?: TimeInput;
}

/**
 * Options shared by every emitter's `end()`.
 *
 * `error` marks the span failed before ending it, deriving `error.type` from
 * `error.name`. `endTime` backdates the close.
 */
export interface SpanEndOptions {
  error?: Error;
  endTime?: TimeInput;
}

export function sanitizeSpanAttributes(
  attributes: Attributes,
  owner: string
): Attributes {
  if (!(ATTR_ERROR_TYPE in attributes)) return attributes;
  const sanitized = {...attributes};
  delete sanitized[ATTR_ERROR_TYPE];
  console.warn(
    `weave.${owner} ignored ${ATTR_ERROR_TYPE} — it is managed by recordError() and end({error}).`
  );
  return sanitized;
}

/**
 * Shared base for the four GenAI span wrappers (`Tool`, `LLM`, `SubAgent`,
 * `Turn`). Holds the underlying OTel span plus the `_ended` guard and exposes
 * the common escape-hatch mutators so every span type gets an identical
 * surface.
 *
 * Mirrors the Python SDK's `_SpanBase` mixin (wandb/weave#7131): rather than
 * re-declaring `setAttributes`/`addEvent` on each class, the implementation
 * lives here once and covers all four uniformly. Post-hoc times follow the
 * same single-source rule: `SpanInitBase.startTime` is forwarded by each
 * `create()` into `tracer.startSpan`, and `_closeSpan` applies
 * `SpanEndOptions.endTime` at close (the TS counterpart of Python
 * `_SpanBase._end_otel_span`) — both pass the time straight through to OTel.
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
   * `set_attributes`). `error.type` is managed by the error helpers.
   *
   * @example
   * span.setAttributes({'weave.tag': 'prod', 'gen_ai.response.id': id});
   */
  setAttributes(attributes: Attributes): this {
    if (this._warnIfEnded('setAttributes')) return this;
    this.span.setAttributes(
      sanitizeSpanAttributes(
        attributes,
        `${this.constructor.name}.setAttributes()`
      )
    );
    return this;
  }

  /**
   * Record a failure without ending the span. Later call `end()` without the
   * same error; use `end({error})` when failure and close coincide.
   */
  recordError(error: Error): this {
    if (this._warnIfEnded('recordError')) return this;
    this._recordError(error);
    return this;
  }

  /**
   * Add a named event to the span. Useful for marking non-span moments such as
   * context compaction, tool-loop detection, or guardrail trips. Warns and
   * no-ops after `end()`. Mirrors OTel `Span.addEvent`.
   *
   * @deprecated Record this data via {@link setAttributes} instead.
   * OpenTelemetry is phasing out the Span Event API (`Span.addEvent`). This
   * method still works and existing span-event data stays valid.
   * See https://opentelemetry.io/blog/2026/deprecating-span-events/
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
   * Record an optional error, then close the span — backdating the close when
   * `endTime` is given. Subclasses call this as the final step of their own
   * `end()`, after flushing their span-specific data. Centralizes the
   * error-status + `span.end()` tail that is otherwise identical across all
   * four emitters.
   */
  protected _closeSpan(opts?: SpanEndOptions): void {
    if (opts?.error) {
      this._recordError(opts.error);
    }
    this.span.end(opts?.endTime);
  }

  private _recordError(error: Error): void {
    this.span.setAttribute(
      ATTR_ERROR_TYPE,
      error.name || error.constructor?.name || 'Error'
    );
    this.span.setStatus({
      code: SpanStatusCode.ERROR,
      ...(error.message ? {message: error.message} : {}),
    });
    this.span.recordException(error);
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
