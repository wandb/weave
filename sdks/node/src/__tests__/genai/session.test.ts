import {GEN_AI_ATTR} from '../../genai/semconv';
import {Session} from '../../genai/session';

import {setupExporterPerTest, setupGenAITestEnvironment} from './common';

describe('Session', () => {
  setupGenAITestEnvironment();
  const getExporter = setupExporterPerTest();

  it('emits no span of its own but propagates sessionId as gen_ai.conversation.id', () => {
    const session = Session.create({
      agentName: 'weather-bot',
      sessionId: 's-1',
    });
    const turn = session.startTurn();
    turn.end();
    session.end();

    const spans = getExporter().getFinishedSpans();
    expect(spans).toHaveLength(1); // only the turn span
    expect(spans[0].name).toBe('invoke_agent');
    expect(spans[0].attributes[GEN_AI_ATTR.GEN_AI_CONVERSATION_ID]).toBe('s-1');
    expect(spans[0].attributes[GEN_AI_ATTR.GEN_AI_AGENT_NAME]).toBe(
      'weather-bot'
    );
  });

  it('auto-generates a sessionId when none is supplied', () => {
    const session = Session.create({});
    expect(session.sessionId).toBeTruthy();
  });
});
