/**
 * Deprecated `session`-named aliases for the GenAI Conversation SDK.
 *
 * The SDK was renamed from "Session" to "Conversation". These forward to the
 * new names and emit a one-time Node `DeprecationWarning`; the old `sessionId`
 * maps to `conversationId`. Quarantined here so the renamed core stays free of
 * legacy naming. Remove in a future release.
 */
import type {Attributes} from '@opentelemetry/api';

import {endConversation, startConversation} from './api';
import type {Conversation} from './conversation';
import {getCurrentConversation} from './context';
import type {SpanEndOptions} from './spanBase';

const _warned = new Set<string>();

function warnOnce(oldName: string, newName: string): void {
  if (_warned.has(oldName)) {
    return;
  }
  _warned.add(oldName);
  process.emitWarning(
    `weave.${oldName} is deprecated; use weave.${newName} instead.`,
    {type: 'DeprecationWarning', code: 'WEAVE_CONVERSATION_RENAMED'}
  );
}

/** @deprecated Renamed to `Conversation`. */
export type Session = Conversation;

/**
 * @deprecated Renamed to `ConversationInit`; `sessionId` is now
 * `conversationId`.
 */
export interface SessionInit {
  agentName?: string;
  model?: string;
  /** @deprecated Use `conversationId`. */
  sessionId?: string;
  attributes?: Attributes;
}

/**
 * @deprecated Renamed to `startConversation`; `sessionId` maps to
 * `conversationId`.
 */
export function startSession(opts: SessionInit = {}): Conversation {
  warnOnce('startSession', 'startConversation');
  const {sessionId, ...rest} = opts;
  return startConversation(
    sessionId === undefined ? rest : {...rest, conversationId: sessionId}
  );
}

/** @deprecated Renamed to `endConversation`. */
export function endSession(opts?: SpanEndOptions): void {
  warnOnce('endSession', 'endConversation');
  endConversation(opts);
}

/** @deprecated Renamed to `getCurrentConversation`. */
export function getCurrentSession(): Conversation | undefined {
  warnOnce('getCurrentSession', 'getCurrentConversation');
  return getCurrentConversation();
}
