import {
  ATTR_GEN_AI_AGENT_NAME,
  ATTR_GEN_AI_CONVERSATION_ID,
} from '../../genai/semconv';
import {Conversation} from '../../genai/conversation';

import {setupExporterPerTest, setupGenAITestEnvironment} from './common';

describe('Conversation', () => {
  setupGenAITestEnvironment();
  const getExporter = setupExporterPerTest();

  it('emits no span of its own but propagates conversationId as gen_ai.conversation.id', () => {
    const conversation = Conversation.create({
      agentName: 'weather-bot',
      conversationId: 's-1',
    });
    const turn = conversation.startTurn();
    turn.end();
    conversation.end();

    const spans = getExporter().getFinishedSpans();
    expect(spans).toHaveLength(1); // only the turn span
    expect(spans[0].name).toBe('invoke_agent');
    expect(spans[0].attributes[ATTR_GEN_AI_CONVERSATION_ID]).toBe('s-1');
    expect(spans[0].attributes[ATTR_GEN_AI_AGENT_NAME]).toBe('weather-bot');
  });

  it('auto-generates a conversationId when none is supplied', () => {
    const conversation = Conversation.create({});
    expect(conversation.conversationId).toBeTruthy();
  });
});
