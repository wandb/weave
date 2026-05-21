import type {Context} from '@opentelemetry/api';

/**
 * Internal options threaded from a parent emitter into a child class's
 * `create()` factory. Carries the OTel parent Context (which already has
 * the parent span attached) and the propagating conversation id.
 */
export interface ChildSpanContext {
  parentContext: Context;
  conversationId?: string;
}
