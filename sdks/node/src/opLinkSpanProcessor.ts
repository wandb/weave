import type {Context} from '@opentelemetry/api';
import type {
  ReadableSpan,
  Span,
  SpanProcessor,
} from '@opentelemetry/sdk-trace-base';

import {
  PARENT_CALL_ID_SPAN_ATTR,
  PARENT_CALL_TRACE_ID_SPAN_ATTR,
} from './constants';
import type {WeaveClient} from './weaveClient';

type ClientGetter = () => WeaveClient | null;

/**
 * OpenTelemetry SpanProcessor that stamps the enclosing weave op call onto the
 * spans started inside it. A span started outside that call's async chain
 * carries no link, and a link to a call that has already finished is normal too.
 */
export class OpLinkSpanProcessor implements SpanProcessor {
  constructor(private readonly getClient: ClientGetter) {}

  onStart(span: Span, _parentContext: Context): void {
    const call = this.getClient()?.getCallStack().peek();
    if (!call) {
      return;
    }

    // A span already at its attribute limit drops whatever arrives next, so the
    // id the spans query filters on is written before the trace id.
    span.setAttribute(PARENT_CALL_ID_SPAN_ATTR, call.callId);
    span.setAttribute(PARENT_CALL_TRACE_ID_SPAN_ATTR, call.traceId);
  }

  onEnd(_span: ReadableSpan): void {}

  forceFlush(): Promise<void> {
    return Promise.resolve();
  }

  shutdown(): Promise<void> {
    return Promise.resolve();
  }
}
