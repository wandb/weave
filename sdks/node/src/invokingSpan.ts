import {isSpanContextValid, trace, TraceFlags} from '@opentelemetry/api';

/**
 * Identity of the OTel span a call starting now was invoked from, or null.
 *
 * The pair means "this span was current", not "this span called exactly this
 * call", so one span maps to every call started inside it. Nothing is recorded
 * for a span a reader could not use: not alive, held out of the export path by
 * a RECORD_ONLY sampling decision, or carrying the all-zero identity a custom
 * `IdGenerator` can produce.
 *
 * Only instrumentation the user installed themselves is visible: this SDK
 * registers no OTel context manager and never calls `startActiveSpan`, so its
 * own spans never become current. A missing key and a pair that matches no span
 * are both normal.
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
