import type {Attributes, Context} from '@opentelemetry/api';

import {ATTR_USER_EMAIL, ATTR_USER_ID} from './semconv';

/**
 * Options a parent emitter passes into a child's `create()` factory: the OTel
 * parent Context (with the parent span already attached), the conversation id,
 * the end-user identity, and the custom attributes. All are forwarded down the
 * handle chain, so every descendant span inherits them.
 */
export interface ChildSpanContext {
  parentContext: Context;
  conversationId?: string;
  userId?: string;
  userEmail?: string;
  attributes?: Attributes;
}

/** `user.id` / `user.email` attributes for the non-empty identity fields. */
export function userAttributes(
  userId?: string,
  userEmail?: string
): Attributes {
  const attributes: Attributes = {};
  if (userId) {
    attributes[ATTR_USER_ID] = userId;
  }
  if (userEmail) {
    attributes[ATTR_USER_EMAIL] = userEmail;
  }
  return attributes;
}
