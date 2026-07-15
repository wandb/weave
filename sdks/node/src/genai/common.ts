import type {Attributes, Context} from '@opentelemetry/api';

/**
 * Internal options a parent emitter passes into a child class's `create()`
 * factory. Carries the OTel parent Context (which already has the parent span
 * attached), the conversation id, and the custom attributes. All three are
 * forwarded explicitly down the handle chain, so every descendant span
 * inherits them from its parent.
 */
export interface ChildSpanContext {
  parentContext: Context;
  conversationId?: string;
  attributes?: Attributes;
}
