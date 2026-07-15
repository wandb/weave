import type {Attributes, Context} from '@opentelemetry/api';

/**
 * Options a parent emitter passes into a child's `create()` factory: the OTel
 * parent Context (with the parent span already attached), the conversation id,
 * and the custom attributes. All three are forwarded down the handle chain, so
 * every descendant span inherits them.
 */
export interface ChildSpanContext {
  parentContext: Context;
  conversationId?: string;
  attributes?: Attributes;
}
