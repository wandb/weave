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

  it('setAttribute and addEvent record on the tool span', () => {
    const turn = Turn.create({conversationId: 'conv-1'});
    const tool = turn.startTool({name: 'get_weather', toolCallId: 'tc-1'});
    const ts = new Date('2026-01-01T00:00:00Z');
    tool.setAttribute('weave.display_name', 'get_weather: Tokyo');
    tool.addEvent(
      'weave.permission_request',
      {'weave.permission.suggestions': '[]'},
      ts
    );
    tool.end();
    turn.end();

    const spans = getExporter().getFinishedSpans();
    const toolSpan = findSpan(spans, 'execute_tool');
    expect(toolSpan.attributes['weave.display_name']).toBe(
      'get_weather: Tokyo'
    );
    expect(toolSpan.events).toHaveLength(1);
    expect(toolSpan.events[0].name).toBe('weave.permission_request');
    expect(
      toolSpan.events[0].attributes?.['weave.permission.suggestions']
    ).toBe('[]');
    // Span event time is [seconds, nanoseconds]; verify seconds match.
    const MILLIS_PER_SECOND = 1000;
    expect(toolSpan.events[0].time[0]).toBe(
      Math.floor(ts.getTime() / MILLIS_PER_SECOND)
    );
  });

  it('setAttribute and addEvent warn and no-op after end()', () => {
    const warnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});

    const turn = Turn.create({});
    const tool = turn.startTool({name: 'f'});
    tool.end();
    tool.setAttribute('weave.display_name', 'too-late');
    tool.addEvent('weave.permission_request');
    turn.end();

    // One warning per method, naming the method that was called too late.
    expect(warnSpy).toHaveBeenCalledTimes(2);
    for (const method of ['setAttribute', 'addEvent']) {
      expect(warnSpy).toHaveBeenCalledWith(
        expect.stringContaining(`Tool.${method}() called after end()`)
      );
    }

    // Nothing reached the span.
    const spans = getExporter().getFinishedSpans();
    const toolSpan = findSpan(spans, 'execute_tool');
    expect(toolSpan.attributes['weave.display_name']).toBeUndefined();
    expect(toolSpan.events).toHaveLength(0);

    warnSpy.mockRestore();
  });
});
