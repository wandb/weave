import type {Attributes, Context} from '@opentelemetry/api';

/**
 * Internal options threaded from a parent emitter into a child class's
 * `create()` factory. Carries the OTel parent Context (which already has
 * the parent span attached), the propagating conversation id, and the
 * propagating custom attributes.
 */
export interface ChildSpanContext {
  parentContext: Context;
  conversationId?: string;
  /** Custom attributes carried down from the parent span. Lets conversation /
   *  turn-level attributes ride the handle chain even when the ambient GenAI
   *  state does not span the parent's and child's async frames. */
  attributes?: Attributes;
}
