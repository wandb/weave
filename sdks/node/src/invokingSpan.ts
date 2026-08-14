import {isSpanContextValid, trace, TraceFlags} from '@opentelemetry/api';

/**
 * Identity of the OTel span a call starting now was invoked from, or null.
 *
 * Recorded on the call so a reader can walk from an agent's `execute_tool` span
 * to the op call it invoked. The pair means "this span was current", not "this
 * span called exactly this call", so one span maps to every call started inside
 * it. Nothing is recorded for a span a reader could not use: `isRecording()`
 * says the span is alive, the sampled flag says it will be exported, which a
 * RECORD_ONLY sampling decision withholds, and `isSpanContextValid` rejects the
 * all-zero identity a custom `IdGenerator` can produce.
 *
 * Only instrumentation the user installed themselves is visible here. Weave's
 * own spans never become current — this SDK registers no OTel context manager
 * and passes every parent as an explicit `Context` — so the integrations that
 * emit them have to answer from their own state instead. Who installed the
 * tracer provider is deliberately not checked: that is process state while the
 * question is about one span. A missing key and a pair that matches no span are
 * therefore both normal.
 */
export function invokingSpanAttr(): {
  trace_id: string;
  span_id: string;
} | null {
  const span = trace.getActiveSpan();
  if (!span || !span.isRecording()) {
    return null;
  }
  const spanContext = span.spanContext();
  if (
    !isSpanContextValid(spanContext) ||
    !(spanContext.traceFlags & TraceFlags.SAMPLED)
  ) {
    return null;
  }
  return {trace_id: spanContext.traceId, span_id: spanContext.spanId};
}
