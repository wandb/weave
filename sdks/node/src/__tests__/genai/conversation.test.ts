import {
  ATTR_GEN_AI_AGENT_NAME,
  ATTR_GEN_AI_CONVERSATION_ID,
} from '../../genai/semconv';
import {Conversation, Session} from '../../genai/conversation';

import {
  findSpan,
  setupExporterPerTest,
  setupGenAITestEnvironment,
  spanSnapshot,
} from './common';

describe('Conversation', () => {
  setupGenAITestEnvironment();
  const getExporter = setupExporterPerTest();

  it('emits no span of its own but propagates conversationId as gen_ai.conversation.id', () => {
    const conversation = Conversation.create({
      agentName: 'weather-bot',
      conversationId: 'c-1',
    });
    const turn = conversation.startTurn();
    turn.end();
    conversation.end();

    const spans = getExporter().getFinishedSpans();
    expect(spans).toHaveLength(1); // only the turn span
    expect(spans[0].name).toBe('invoke_agent');
    expect(spans[0].attributes[ATTR_GEN_AI_CONVERSATION_ID]).toBe('c-1');
    expect(spans[0].attributes[ATTR_GEN_AI_AGENT_NAME]).toBe('weather-bot');
  });

  it('auto-generates a conversationId when none is supplied', () => {
    const conversation = Conversation.create({});
    expect(conversation.conversationId).toBeTruthy();
  });

  it('deprecated `Session` is an alias for `Conversation`', () => {
    expect(Session).toBe(Conversation);
    const conversation = Session.create({conversationId: 'aliased'});
    expect(conversation).toBeInstanceOf(Conversation);
    conversation.end();
  });

  it('deprecated `sessionId` opt + property are aliases for `conversationId`', () => {
    // Input alias: ConversationInit.sessionId still seeds conversationId.
    const conversation = Conversation.create({sessionId: 'legacy-id'});
    expect(conversation.conversationId).toBe('legacy-id');
    // Read alias: Conversation.sessionId still returns conversationId.
    expect(conversation.sessionId).toBe('legacy-id');
    conversation.end();
  });

  it('conversationId wins when both opts are provided', () => {
    const conversation = Conversation.create({
      conversationId: 'new',
      sessionId: 'old',
    });
    expect(conversation.conversationId).toBe('new');
    conversation.end();
  });

  it('startTurn emits given data on `invoke_agent` span', () => {
    const conversation = Conversation.create({
      agentName: 'dispatcher',
      model: 'some-model',
      conversationId: 'c-2',
    });
    const turn = conversation.startTurn({
      agentName: 'weather-bot',
      model: 'gpt-4o',
      userMessage: "What's the weather?",
      systemInstructions: ['Be helpful', 'Be concise'],
    });
    turn.end();
    conversation.end();

    const span = findSpan(getExporter().getFinishedSpans(), 'invoke_agent');
    expect(spanSnapshot(span)).toMatchInlineSnapshot(`
      {
        "attributes": {
          "gen_ai.agent.name": "weather-bot",
          "gen_ai.conversation.id": "<uuid>",
          "gen_ai.input.messages": "[{"role":"user","parts":[{"type":"text","content":"What's the weather?"}]}]",
          "gen_ai.operation.name": "invoke_agent",
          "gen_ai.request.model": "gpt-4o",
          "gen_ai.system_instructions": "[{"type":"text","content":"Be helpful"},{"type":"text","content":"Be concise"}]",
        },
        "endTime": "<timestamp>",
        "startTime": "<timestamp>",
      }
    `);
  });

  it('startTurn falls back to conversation data when not given', () => {
    const conversation = Conversation.create({
      agentName: 'dispatcher',
      model: 'some-model',
      conversationId: 'c-3',
    });
    const turn = conversation.startTurn();
    turn.end();
    conversation.end();

    const span = findSpan(getExporter().getFinishedSpans(), 'invoke_agent');
    expect(spanSnapshot(span)).toMatchInlineSnapshot(`
      {
        "attributes": {
          "gen_ai.agent.name": "dispatcher",
          "gen_ai.conversation.id": "<uuid>",
          "gen_ai.operation.name": "invoke_agent",
          "gen_ai.request.model": "some-model",
        },
        "endTime": "<timestamp>",
        "startTime": "<timestamp>",
      }
    `);
  });
});
