import {
  ATTR_GEN_AI_AGENT_NAME,
  ATTR_GEN_AI_CONVERSATION_ID,
} from '../../genai/semconv';
import {
  endSession,
  getCurrentSession,
  startSession,
} from '../../genai/deprecated';

import {setupExporterPerTest, setupGenAITestEnvironment} from './common';

// The Session SDK was renamed to the Conversation SDK; these cover the
// back-compat aliases that forward to the new names (sessionId ->
// conversationId) so existing code keeps working.
describe('deprecated session aliases', () => {
  setupGenAITestEnvironment();
  const getExporter = setupExporterPerTest();

  it('startSession forwards to a Conversation, mapping sessionId -> conversationId', () => {
    const conversation = startSession({agentName: 'bot', sessionId: 's-1'});
    expect(conversation.conversationId).toBe('s-1');
    expect(getCurrentSession()).toBe(conversation);

    conversation.startTurn().end();
    endSession();

    expect(getCurrentSession()).toBeUndefined();
    const spans = getExporter().getFinishedSpans();
    expect(spans).toHaveLength(1); // only the turn span
    expect(spans[0].attributes[ATTR_GEN_AI_CONVERSATION_ID]).toBe('s-1');
    expect(spans[0].attributes[ATTR_GEN_AI_AGENT_NAME]).toBe('bot');
  });

  it('startSession auto-generates a conversationId when sessionId is omitted', () => {
    const conversation = startSession({agentName: 'bot'});
    expect(conversation.conversationId).toBeTruthy();
    endSession();
  });
});
