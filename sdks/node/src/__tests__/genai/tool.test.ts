import {SpanKind} from '@opentelemetry/api';

import {
  ATTR_GEN_AI_CONVERSATION_ID,
  ATTR_GEN_AI_OPERATION_NAME,
  ATTR_GEN_AI_TOOL_CALL_ARGUMENTS,
  ATTR_GEN_AI_TOOL_CALL_ID,
  ATTR_GEN_AI_TOOL_CALL_RESULT,
  ATTR_GEN_AI_TOOL_NAME,
} from '../../genai/semconv';
import {Turn} from '../../genai/turn';

import {
  expectSpanTimesToMatch,
  findSpan,
  setupExporterPerTest,
  setupGenAITestEnvironment,
} from './common';

describe('Tool', () => {
  setupGenAITestEnvironment();
  const getExporter = setupExporterPerTest();

  it('attaches to the turn span when started via turn.startTool() (flat)', () => {
    const turn = Turn.create({conversationId: 'conv-1'});
    const tool = turn.startTool({
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
    expect(toolSpan.attributes[ATTR_GEN_AI_OPERATION_NAME]).toBe(
      'execute_tool'
    );
    expect(toolSpan.attributes[ATTR_GEN_AI_TOOL_NAME]).toBe('get_weather');
    expect(toolSpan.attributes[ATTR_GEN_AI_TOOL_CALL_ID]).toBe('tc-1');
    expect(toolSpan.attributes[ATTR_GEN_AI_TOOL_CALL_ARGUMENTS]).toBe(
      '{"city":"Tokyo"}'
    );
    expect(toolSpan.attributes[ATTR_GEN_AI_TOOL_CALL_RESULT]).toBe('75F');
    expect(toolSpan.attributes[ATTR_GEN_AI_CONVERSATION_ID]).toBe('conv-1');
    expect(toolSpan.parentSpanContext?.spanId).toBe(turnSpan.spanContext().spanId);
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
    expect(toolSpan.parentSpanContext?.spanId).toBe(llmSpan.spanContext().spanId);
  });

  it('setAttributes records attributes on the tool span; warns + no-op after end()', () => {
    const warnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});
    const turn = Turn.create({});
    const tool = turn.startTool({name: 'get_weather'});
    tool.setAttributes({
      'weave.display_name': 'get_weather: Tokyo',
      'weave.tag': 'enterprise',
    });
    tool.end();
    tool.setAttributes({'after.end': 'x'});
    turn.end();

    const toolSpan = findSpan(getExporter().getFinishedSpans(), 'execute_tool');
    expect(toolSpan.attributes['weave.display_name']).toBe(
      'get_weather: Tokyo'
    );
    expect(toolSpan.attributes['weave.tag']).toBe('enterprise');
    expect(toolSpan.attributes['after.end']).toBeUndefined();
    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining('Tool.setAttributes() called after end()')
    );
    warnSpy.mockRestore();
  });

  it('addEvent records a span event on the tool span; warns + no-op after end()', () => {
    const warnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});
    const turn = Turn.create({});
    const tool = turn.startTool({name: 'get_weather'});
    tool.addEvent('weave.permission_request', {
      'weave.permission.suggestions': '[]',
    });
    tool.end();
    tool.addEvent('after.end');
    turn.end();

    const toolSpan = findSpan(getExporter().getFinishedSpans(), 'execute_tool');
    expect(toolSpan.events).toHaveLength(1);
    expect(toolSpan.events[0].name).toBe('weave.permission_request');
    expect(
      toolSpan.events[0].attributes?.['weave.permission.suggestions']
    ).toBe('[]');
    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining('Tool.addEvent() called after end()')
    );
    warnSpy.mockRestore();
  });

  it('startTime/endTime backdate the execute_tool span window', () => {
    const startedAt = new Date('2026-01-01T00:00:00Z');
    const endedAt = new Date('2026-01-01T00:00:05Z');
    const turn = Turn.create({});
    const tool = turn.startTool({name: 'get_weather', startTime: startedAt});
    tool.end({endTime: endedAt});
    turn.end();

    const toolSpan = findSpan(getExporter().getFinishedSpans(), 'execute_tool');
    expectSpanTimesToMatch(toolSpan, startedAt, endedAt);
  });
});
