import type {ReadableSpan} from '@opentelemetry/sdk-trace-base';

import {ATTR_GEN_AI_AGENT_NAME} from '../../genai/semconv';
import {Turn} from '../../genai/turn';

import {
  expectSpanTimesToMatch,
  setupExporterPerTest,
  setupGenAITestEnvironment,
  spanSnapshot,
} from './common';

describe('SubAgent', () => {
  setupGenAITestEnvironment();
  const getExporter = setupExporterPerTest();

  it('emits a nested invoke_agent span as a child of the turn', () => {
    const turn = Turn.create({agentName: 'parent'});
    const sub = turn.startSubagent({
      name: 'child-bot',
      model: 'gpt-4o',
      systemInstructions: ['Be helpful', 'Be concise'],
    });
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

    expect(spanSnapshot(subSpan!)).toMatchInlineSnapshot(`
      {
        "attributes": {
          "gen_ai.agent.name": "child-bot",
          "gen_ai.operation.name": "invoke_agent",
          "gen_ai.request.model": "gpt-4o",
          "gen_ai.system_instructions": "[{"type":"text","content":"Be helpful"},{"type":"text","content":"Be concise"}]",
        },
        "endTime": "<timestamp>",
        "startTime": "<timestamp>",
      }
    `);
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
});
