import {GEN_AI_ATTR} from '../../genai/semconv';
import {Session} from '../../genai/session';

import {
  findSpan,
  setupExporterPerTest,
  setupGenAITestEnvironment,
} from './common';

describe('end-to-end chain', () => {
  setupGenAITestEnvironment();
  const getExporter = setupExporterPerTest();

  it('session → turn → llm → tool wires the full parent-child trace', () => {
    const session = Session.create({
      agentName: 'weather-bot',
      sessionId: 'conv-e2e',
    });
    const turn = session.startTurn();
    const llm = turn.llm({model: 'gpt-4o'});
    const tool = llm.startTool({name: 'get_weather'});
    tool.end();
    llm.end();
    turn.end();
    session.end();

    const spans = getExporter().getFinishedSpans();
    expect(spans).toHaveLength(3);
    const turnSpan = findSpan(spans, 'invoke_agent');
    const llmSpan = findSpan(spans, 'chat');
    const toolSpan = findSpan(spans, 'execute_tool');

    // All three share the same trace id.
    const traceId = turnSpan.spanContext().traceId;
    expect(llmSpan.spanContext().traceId).toBe(traceId);
    expect(toolSpan.spanContext().traceId).toBe(traceId);

    // Parent-child chain.
    expect(turnSpan.parentSpanId).toBeUndefined();
    expect(llmSpan.parentSpanId).toBe(turnSpan.spanContext().spanId);
    expect(toolSpan.parentSpanId).toBe(llmSpan.spanContext().spanId);

    // Conversation id propagates everywhere.
    for (const s of spans) {
      expect(s.attributes[GEN_AI_ATTR.GEN_AI_CONVERSATION_ID]).toBe('conv-e2e');
    }
  });
});
