import {SpanKind} from '@opentelemetry/api';

import {GEN_AI_ATTR} from '../../genai/semconv';
import {Turn} from '../../genai/turn';

import {
  findSpan,
  setupExporterPerTest,
  setupGenAITestEnvironment,
} from './common';

describe('Tool', () => {
  setupGenAITestEnvironment();
  const getExporter = setupExporterPerTest();

  it('attaches to the turn span when started via turn.tool() (flat)', () => {
    const turn = Turn.create({conversationId: 'conv-1'});
    const tool = turn.tool({
      name: 'get_weather',
      args: '{"city":"Tokyo"}',
      toolCallId: 'tc-1',
    });
    tool.result = '75F';
    tool.end();
    turn.end();

    const spans = getExporter().getFinishedSpans();
    const toolSpan = findSpan(spans, 'execute_tool');
    const turnSpan = findSpan(spans, 'invoke_agent');

    expect(toolSpan.kind).toBe(SpanKind.INTERNAL);
    expect(toolSpan.attributes[GEN_AI_ATTR.GEN_AI_OPERATION_NAME]).toBe(
      'execute_tool'
    );
    expect(toolSpan.attributes[GEN_AI_ATTR.GEN_AI_TOOL_NAME]).toBe(
      'get_weather'
    );
    expect(toolSpan.attributes[GEN_AI_ATTR.GEN_AI_TOOL_CALL_ID]).toBe('tc-1');
    expect(toolSpan.attributes[GEN_AI_ATTR.GEN_AI_TOOL_CALL_ARGUMENTS]).toBe(
      '{"city":"Tokyo"}'
    );
    expect(toolSpan.attributes[GEN_AI_ATTR.GEN_AI_TOOL_CALL_RESULT]).toBe(
      '75F'
    );
    expect(toolSpan.attributes[GEN_AI_ATTR.GEN_AI_CONVERSATION_ID]).toBe(
      'conv-1'
    );
    expect(toolSpan.parentSpanId).toBe(turnSpan.spanContext().spanId);
  });

  it('attaches to the LLM span when started via llm.startTool() (nested)', () => {
    const turn = Turn.create({});
    const llm = turn.startLLM({model: 'gpt-4o'});
    const tool = llm.startTool({name: 'get_weather'});
    tool.end();
    llm.end();
    turn.end();

    const spans = getExporter().getFinishedSpans();
    const toolSpan = findSpan(spans, 'execute_tool');
    const llmSpan = findSpan(spans, 'chat');
    expect(toolSpan.parentSpanId).toBe(llmSpan.spanContext().spanId);
  });
});
