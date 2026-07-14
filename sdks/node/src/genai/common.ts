import type {Attributes, Context} from '@opentelemetry/api';

/**
 * Internal options passed from a parent emitter into a child class's
 * `create()` factory. Carries the OTel parent Context (which already has the
 * parent span attached), the propagating conversation id, and the propagating
 * custom attributes. All three travel with the handle rather than being read
 * from ambient state, so they survive across `runIsolated` frames.
 */
export interface ChildSpanContext {
  parentContext: Context;
  conversationId?: string;
  attributes?: Attributes;
}
