import {SpanStatusCode} from '@opentelemetry/api';
import {Turn} from '../../genai/turn';

import {
  expectSpanTimesToMatch,
  findSpan,
  setupExporterPerTest,
  setupGenAITestEnvironment,
  spanSnapshot,
} from './common';

describe('Turn', () => {
  setupGenAITestEnvironment();
  const getExporter = setupExporterPerTest();

  it('emits an invoke_agent span with GenAI agent / model attributes', () => {
    const turn = Turn.create({
      model: 'gpt-4o',
      agentId: '12345',
      agentName: 'weather-bot',
      agentDescription: 'Finds the most accurate weather',
      agentVersion: '1.2.3',
      conversationId: 'conv-1',
      userMessage: "What's the weather?",
      systemInstructions: ['Be helpful', 'Be concise'],
    });
    turn.end();

    const span = findSpan(getExporter().getFinishedSpans(), 'invoke_agent');
    expect(spanSnapshot(span)).toMatchInlineSnapshot(`
      {
        "attributes": {
          "gen_ai.agent.description": "Finds the most accurate weather",
          "gen_ai.agent.id": "12345",
          "gen_ai.agent.name": "weather-bot",
          "gen_ai.agent.version": "1.2.3",
          "gen_ai.conversation.id": "<uuid>",
          "gen_ai.input.messages": "[{"role":"user","parts":[{"type":"text","content":"What's the weather?"}]}]",
          "gen_ai.operation.name": "invoke_agent",
          "gen_ai.request.model": "gpt-4o",
          "gen_ai.system_instructions": "[{"type":"text","content":"Be helpful"},{"type":"text","content":"Be concise"}]",
        },
        "endTime": "<timestamp>",
        "startTime": "<timestamp>",
      }
    `);
  });

  it('end() is idempotent', () => {
    const turn = Turn.create({});
    turn.end();
    turn.end();
    expect(getExporter().getFinishedSpans()).toHaveLength(1);
  });

  it('records the error and sets ERROR status when end({ error }) is called', () => {
    const turn = Turn.create({});
    turn.end({error: new Error('boom')});
    const span = findSpan(getExporter().getFinishedSpans(), 'invoke_agent');
    expect(span.status.code).toBe(SpanStatusCode.ERROR);
    expect(span.status.message).toBe('boom');
    expect(span.events.some(e => e.name === 'exception')).toBe(true);
  });
});

describe('Turn.setAttributes', () => {
  setupGenAITestEnvironment();
  const getExporter = setupExporterPerTest();

  it('writes multiple attributes to the underlying span', () => {
    const turn = Turn.create({});
    turn.setAttributes({'weave.cost.usd': 0.42, 'weave.tag': 'enterprise'});
    turn.end();
    const span = findSpan(getExporter().getFinishedSpans(), 'invoke_agent');
    expect(span.attributes['weave.cost.usd']).toBe(0.42);
    expect(span.attributes['weave.tag']).toBe('enterprise');
  });

  it('returns this for chaining', () => {
    const turn = Turn.create({});
    expect(turn.setAttributes({k: 'v'})).toBe(turn);
    turn.end();
  });

  it('warns and is a no-op after end()', () => {
    const warnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});
    const turn = Turn.create({});
    turn.end();
    turn.setAttributes({'after.end': 'x'});
    const spans = getExporter().getFinishedSpans();
    expect(
      findSpan(spans, 'invoke_agent').attributes['after.end']
    ).toBeUndefined();
    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining('Turn.setAttributes() called after end()')
    );
    warnSpy.mockRestore();
  });
});

// Deprecated singular alias, retained Turn-only for back-compat (delegates to
// setAttributes). The other emitters never shipped a singular form.
describe('Turn.setAttribute (deprecated alias)', () => {
  setupGenAITestEnvironment();
  const getExporter = setupExporterPerTest();

  it('writes an attribute to the underlying span', () => {
    const turn = Turn.create({});
    turn.setAttribute('weave.cost.usd', 0.42);
    turn.end();
    const spans = getExporter().getFinishedSpans();
    expect(findSpan(spans, 'invoke_agent').attributes['weave.cost.usd']).toBe(
      0.42
    );
  });

  it('returns this for chaining', () => {
    const turn = Turn.create({});
    expect(turn.setAttribute('k', 'v')).toBe(turn);
    turn.end();
  });

  it('warns and is a no-op after end()', () => {
    const warnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});
    const turn = Turn.create({});
    turn.end();
    turn.setAttribute('after.end', 'x');
    const spans = getExporter().getFinishedSpans();
    expect(
      findSpan(spans, 'invoke_agent').attributes['after.end']
    ).toBeUndefined();
    // Alias delegates to setAttributes, so the warning names setAttributes.
    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining('Turn.setAttributes() called after end()')
    );
    warnSpy.mockRestore();
  });
});

describe('Turn.addEvent', () => {
  setupGenAITestEnvironment();
  const getExporter = setupExporterPerTest();

  it('writes a named event with attributes', () => {
    const turn = Turn.create({});
    turn.addEvent('context_compacted', {items_before: 50, items_after: 10});
    turn.end();
    const spans = getExporter().getFinishedSpans();
    const ev = findSpan(spans, 'invoke_agent').events.find(
      e => e.name === 'context_compacted'
    );
    expect(ev?.attributes).toMatchObject({items_before: 50, items_after: 10});
  });

  it('returns this for chaining', () => {
    const turn = Turn.create({});
    expect(turn.addEvent('e')).toBe(turn);
    turn.end();
    const spans = getExporter().getFinishedSpans();
    expect(
      findSpan(spans, 'invoke_agent').events.find(e => e.name === 'e')
    ).toBeDefined();
  });

  it('warns and is a no-op after end()', () => {
    const warnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});
    const turn = Turn.create({});
    turn.end();
    turn.addEvent('after.end');
    const spans = getExporter().getFinishedSpans();
    expect(
      findSpan(spans, 'invoke_agent').events.find(e => e.name === 'after.end')
    ).toBeUndefined();
    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining('Turn.addEvent() called after end()')
    );
    warnSpy.mockRestore();
  });

  it('startTime/endTime backdate the invoke_agent span window', () => {
    const startedAt = new Date('2026-01-01T00:00:00Z');
    const endedAt = new Date('2026-01-01T00:00:05Z');
    const turn = Turn.create({startTime: startedAt});
    turn.end({endTime: endedAt});

    const span = findSpan(getExporter().getFinishedSpans(), 'invoke_agent');
    expectSpanTimesToMatch(span, startedAt, endedAt);
  });
});
