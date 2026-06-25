import type {ReadableSpan} from '@opentelemetry/sdk-trace-base';

import {
  ATTR_GEN_AI_AGENT_NAME,
  ATTR_GEN_AI_REQUEST_MODEL,
} from '../../genai/semconv';
import {Turn} from '../../genai/turn';

import {
  expectSpanTimesToMatch,
  setupExporterPerTest,
  setupGenAITestEnvironment,
} from './common';

describe('SubAgent', () => {
  setupGenAITestEnvironment();
  const getExporter = setupExporterPerTest();

  it('emits a nested invoke_agent span as a child of the turn', () => {
    const turn = Turn.create({agentName: 'parent'});
    const sub = turn.startSubagent({name: 'child-bot', model: 'gpt-4o'});
    sub.end();
    turn.end();

    const spans = getExporter().getFinishedSpans();
    // Two spans, both named 'invoke_agent'. Differentiate by agent name.
    const subSpan = spans.find(
      s =>
        s.name === 'invoke_agent' &&
        s.attributes[ATTR_GEN_AI_AGENT_NAME] === 'child-bot'
    );
    const parentTurnSpan = spans.find(
      s =>
        s.name === 'invoke_agent' &&
        s.attributes[ATTR_GEN_AI_AGENT_NAME] === 'parent'
    );
    expect(subSpan).toBeDefined();
    expect(parentTurnSpan).toBeDefined();
    expect(subSpan!.parentSpanId).toBe(parentTurnSpan!.spanContext().spanId);
    expect(subSpan!.attributes[ATTR_GEN_AI_REQUEST_MODEL]).toBe('gpt-4o');
  });

  const findSub = (spans: ReadableSpan[]) => {
    const found = spans.find(
      s =>
        s.name === 'invoke_agent' &&
        s.attributes[ATTR_GEN_AI_AGENT_NAME] === 'researcher'
    );
    if (!found) throw new Error('no researcher invoke_agent span found');
    return found;
  };

  it('setAttributes records attributes on the subagent span; warns + no-op after end()', () => {
    const warnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});
    const turn = Turn.create({});
    const sub = turn.startSubagent({name: 'researcher'});
    sub.setAttributes({
      'weave.claude_code.display_name': 'Agent: research-bot',
      'weave.tag': 'enterprise',
    });
    sub.end();
    sub.setAttributes({'after.end': 'x'});
    turn.end();

    const subSpan = findSub(getExporter().getFinishedSpans());
    expect(subSpan.attributes['weave.claude_code.display_name']).toBe(
      'Agent: research-bot'
    );
    expect(subSpan.attributes['weave.tag']).toBe('enterprise');
    expect(subSpan.attributes['after.end']).toBeUndefined();
    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining('SubAgent.setAttributes() called after end()')
    );
    warnSpy.mockRestore();
  });

  it('addEvent records a span event on the subagent span; warns + no-op after end()', () => {
    const warnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});
    const turn = Turn.create({});
    const sub = turn.startSubagent({name: 'researcher'});
    sub.addEvent('weave.lifecycle', {state: 'spawned'});
    sub.end();
    sub.addEvent('after.end');
    turn.end();

    const subSpan = findSub(getExporter().getFinishedSpans());
    expect(subSpan.events).toHaveLength(1);
    expect(subSpan.events[0].name).toBe('weave.lifecycle');
    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining('SubAgent.addEvent() called after end()')
    );
    warnSpy.mockRestore();
  });

  it('startTime/endTime backdate the invoke_agent span window', () => {
    const startedAt = new Date('2026-01-01T00:00:00Z');
    const endedAt = new Date('2026-01-01T00:00:05Z');
    const turn = Turn.create({});
    const sub = turn.startSubagent({name: 'researcher', startTime: startedAt});
    sub.end({endTime: endedAt});
    turn.end();

    expectSpanTimesToMatch(
      findSub(getExporter().getFinishedSpans()),
      startedAt,
      endedAt
    );
  });

  it('nests child LLM and Tool spans under the subagent span', () => {
    const turn = Turn.create({agentName: 'parent'});
    const sub = turn.startSubagent({name: 'researcher', model: 'gpt-4o'});
    sub.startLLM({model: 'gpt-4o', providerName: 'openai'}).end();
    sub.startTool({name: 'search'}).end();
    sub.end();
    turn.end();

    const spans = getExporter().getFinishedSpans();
    const subSpan = findSub(spans);
    const chatSpan = spans.find(s => s.name === 'chat');
    const toolSpan = spans.find(s => s.name === 'execute_tool');
    expect(chatSpan).toBeDefined();
    expect(toolSpan).toBeDefined();
    // Both children parent to the sub-agent, not the enclosing Turn.
    expect(chatSpan!.parentSpanId).toBe(subSpan.spanContext().spanId);
    expect(toolSpan!.parentSpanId).toBe(subSpan.spanContext().spanId);
  });
});
