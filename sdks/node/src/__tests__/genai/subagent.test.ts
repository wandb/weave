import {GEN_AI_ATTR} from '../../genai/semconv';
import {Turn} from '../../genai/turn';

import {setupExporterPerTest, setupGenAITestEnvironment} from './common';

describe('SubAgent', () => {
  setupGenAITestEnvironment();
  const getExporter = setupExporterPerTest();

  it('emits a nested invoke_agent span as a child of the turn', () => {
    const turn = Turn.create({agentName: 'parent'});
    const sub = turn.subagent({name: 'child-bot', model: 'gpt-4o'});
    sub.end();
    turn.end();

    const spans = getExporter().getFinishedSpans();
    // Two spans, both named 'invoke_agent'. Differentiate by agent name.
    const subSpan = spans.find(
      s =>
        s.name === 'invoke_agent' &&
        s.attributes[GEN_AI_ATTR.GEN_AI_AGENT_NAME] === 'child-bot'
    );
    const parentTurnSpan = spans.find(
      s =>
        s.name === 'invoke_agent' &&
        s.attributes[GEN_AI_ATTR.GEN_AI_AGENT_NAME] === 'parent'
    );
    expect(subSpan).toBeDefined();
    expect(parentTurnSpan).toBeDefined();
    expect(subSpan!.parentSpanId).toBe(parentTurnSpan!.spanContext().spanId);
    expect(subSpan!.attributes[GEN_AI_ATTR.GEN_AI_REQUEST_MODEL]).toBe(
      'gpt-4o'
    );
  });
});
