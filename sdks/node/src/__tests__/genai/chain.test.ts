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

  it('session → turn → llm → tool wires the full parent-child trace', async () => {
    const session = await Session.create({
      agentName: 'weather-bot',
      sessionId: 'conv-e2e',
    });
    const turn = await session.startTurn();
    const llm = await turn.llm({model: 'gpt-4o'});
    const tool = await llm.startTool({name: 'get_weather'});
    await tool.end();
    await llm.end();
    await turn.end();
    await session.end();

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
