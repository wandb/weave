import {
  ATTR_GEN_AI_AGENT_NAME,
  ATTR_GEN_AI_CONVERSATION_ID,
  ATTR_USER_EMAIL,
  ATTR_USER_ID,
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
    expect(spans[0].name).toBe('invoke_agent weather-bot');
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
      model: 'some-model',
      agentId: 'dispatcher-prod',
      agentName: 'dispatcher',
      agentDescription: 'Routes queries to specialist agents.',
      agentVersion: '2.0.1',
      conversationId: 'c-2',
    });
    const turn = conversation.startTurn({
      model: 'gpt-4o',
      agentId: 'weather-prod',
      agentName: 'weather-bot',
      agentDescription: 'Finds the most accurate weather',
      agentVersion: '3.1.2',
      userMessage: "What's the weather?",
      systemInstructions: ['Be helpful', 'Be concise'],
    });
    turn.end();
    conversation.end();

    const span = findSpan(
      getExporter().getFinishedSpans(),
      'invoke_agent weather-bot'
    );
    expect(spanSnapshot(span)).toMatchInlineSnapshot(`
      {
        "attributes": {
          "gen_ai.agent.description": "Finds the most accurate weather",
          "gen_ai.agent.id": "weather-prod",
          "gen_ai.agent.name": "weather-bot",
          "gen_ai.agent.version": "3.1.2",
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
      model: 'some-model',
      agentId: 'dispatcher-prod',
      agentName: 'dispatcher',
      agentDescription: 'Routes queries to specialist agents.',
      agentVersion: '2.0.1',
      conversationId: 'c-3',
    });
    const turn = conversation.startTurn();
    turn.end();
    conversation.end();

    const span = findSpan(
      getExporter().getFinishedSpans(),
      'invoke_agent dispatcher'
    );
    expect(spanSnapshot(span)).toMatchInlineSnapshot(`
      {
        "attributes": {
          "gen_ai.agent.description": "Routes queries to specialist agents.",
          "gen_ai.agent.id": "dispatcher-prod",
          "gen_ai.agent.name": "dispatcher",
          "gen_ai.agent.version": "2.0.1",
          "gen_ai.conversation.id": "<uuid>",
          "gen_ai.operation.name": "invoke_agent",
          "gen_ai.request.model": "some-model",
        },
        "endTime": "<timestamp>",
        "startTime": "<timestamp>",
      }
    `);
  });

  it('propagates userId / userEmail as user.id / user.email to every span', () => {
    const conversation = Conversation.create({
      agentName: 'bot',
      conversationId: 'c-user',
      userId: 'user-123',
      userEmail: 'ada@example.com',
    });
    const turn = conversation.startTurn();
    const llm = turn.startLLM({model: 'gpt-4o'});
    llm.startTool({name: 'nested'}).end();
    llm.end();
    turn.startTool({name: 'Edit'}).end();
    const subagent = turn.startSubagent({name: 'researcher'});
    subagent.startLLM({model: 'gpt-4o-mini'}).end();
    subagent.end();
    turn.end();
    conversation.end();

    const spans = getExporter().getFinishedSpans();
    expect(spans.map(span => span.name).sort()).toEqual([
      'chat gpt-4o',
      'chat gpt-4o-mini',
      'execute_tool Edit',
      'execute_tool nested',
      'invoke_agent bot',
      'invoke_agent researcher',
    ]);
    for (const span of spans) {
      expect(span.attributes[ATTR_USER_ID]).toBe('user-123');
      expect(span.attributes[ATTR_USER_EMAIL]).toBe('ada@example.com');
    }
  });

  it('a turn-level userId overrides the conversation value', () => {
    const conversation = Conversation.create({userId: 'conv-user'});
    conversation.startTurn({agentName: 'bot', userId: 'turn-user'}).end();
    conversation.end();

    const span = findSpan(getExporter().getFinishedSpans(), 'invoke_agent bot');
    expect(span.attributes[ATTR_USER_ID]).toBe('turn-user');
    expect(span.attributes[ATTR_USER_EMAIL]).toBeUndefined();
  });

  it('emits no user attributes by default', () => {
    const conversation = Conversation.create({});
    conversation.startTurn({agentName: 'bot'}).end();
    conversation.end();

    const span = findSpan(getExporter().getFinishedSpans(), 'invoke_agent bot');
    expect(span.attributes[ATTR_USER_ID]).toBeUndefined();
    expect(span.attributes[ATTR_USER_EMAIL]).toBeUndefined();
  });
});
