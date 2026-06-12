import {
  type Attributes,
  type Context,
  type Span,
  type SpanKind,
  SpanStatusCode,
  type TimeInput,
} from '@opentelemetry/api';

import {getWeaveTracer} from './provider';
import {WEAVE_GENAI_TRACER_NAME} from './semconv';

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
 * `error` marks the span failed (records the exception + ERROR status).
 * `endTime` backdates the close so a replayed span carries an accurate
 * duration. Undefined `endTime` → OTel stamps the current time.
 */
export interface SpanEndOptions {
  error?: Error;
  endTime?: TimeInput;
}

/**
 * Shared base for the four GenAI span wrappers (`Tool`, `LLM`, `SubAgent`,
 * `Turn`). Holds the underlying OTel span plus the `_ended` guard and exposes
 * the common escape-hatch mutators so every span type gets an identical
 * surface.
 *
 * Mirrors the Python SDK's `_SpanBase` mixin (wandb/weave#7131): rather than
 * re-declaring `setAttributes`/`addEvent` on each class, the implementation
 * lives here once and covers all four uniformly. The same single-source rule
 * covers the span lifecycle and post-hoc times: `_startSpan` opens the span
 * (applying `SpanInitBase.startTime`) and `_closeSpan` ends it (applying
 * `SpanEndOptions.endTime`) — both pass the time straight through to OTel.
 *
 * Mutating after `end()` warns and no-ops — the span is closed, so further
 * mutation can no longer reach the trace. All mutators return `this` for
 * chaining.
 */
export abstract class SpanBase {
  protected _ended = false;

  protected constructor(protected readonly span: Span) {}

  /**
   * Open a GenAI span on the shared Weave tracer, applying the optional
   * post-hoc `startTime`. Called by each subclass's static `create()` factory
   * with its own span name / kind / attributes / parent context — the only
   * parts that genuinely differ per emitter. Centralizes tracer acquisition
   * and the `startTime` plumbing so no emitter can forget either; the
   * lifecycle counterpart is `_closeSpan`.
   */
  protected static _startSpan(
    name: string,
    kind: SpanKind,
    attributes: Attributes,
    context: Context,
    startTime?: TimeInput
  ): Span {
    return getWeaveTracer(WEAVE_GENAI_TRACER_NAME).startSpan(
      name,
      {kind, attributes, startTime},
      context
    );
  }

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
   * Record an optional error, then close the span — backdating the close when
   * `endTime` is given. Subclasses call this as the final step of their own
   * `end()`, after flushing their span-specific data. Centralizes the
   * error-status + `span.end()` tail that is otherwise identical across all
   * four emitters.
   */
  protected _closeSpan(opts?: SpanEndOptions): void {
    if (opts?.error) {
      this.span.recordException(opts.error);
      this.span.setStatus({
        code: SpanStatusCode.ERROR,
        message: opts.error.message,
      });
    }
    this.span.end(opts?.endTime);
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
