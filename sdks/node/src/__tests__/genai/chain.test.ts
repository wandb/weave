import {ATTR_GEN_AI_CONVERSATION_ID} from '../../genai/semconv';
import {Conversation} from '../../genai/conversation';

import {
  findSpan,
  setupExporterPerTest,
  setupGenAITestEnvironment,
} from './common';

describe('end-to-end chain', () => {
  setupGenAITestEnvironment();
  const getExporter = setupExporterPerTest();

  it('conversation → turn → llm → tool wires the full parent-child trace', () => {
    const conversation = Conversation.create({
      agentName: 'weather-bot',
      conversationId: 'conv-e2e',
    });
    const turn = conversation.startTurn();
    const llm = turn.startLLM({model: 'gpt-4o'});
    const tool = llm.startTool({name: 'get_weather'});
    tool.end();
    llm.end();
    turn.end();
    conversation.end();

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
      expect(s.attributes[ATTR_GEN_AI_CONVERSATION_ID]).toBe('conv-e2e');
    }
  });
});
