import {SpanKind, SpanStatusCode} from '@opentelemetry/api';

import {
  ATTR_GEN_AI_AGENT_NAME,
  ATTR_GEN_AI_CONVERSATION_ID,
  ATTR_GEN_AI_OPERATION_NAME,
  ATTR_GEN_AI_REQUEST_MODEL,
} from '../../genai/semconv';
import {Turn} from '../../genai/turn';

import {
  findSpan,
  setupExporterPerTest,
  setupGenAITestEnvironment,
} from './common';

describe('Turn', () => {
  setupGenAITestEnvironment();
  const getExporter = setupExporterPerTest();

  it('emits an invoke_agent span with GenAI agent / model attributes', () => {
    const turn = Turn.create({
      agentName: 'weather-bot',
      model: 'gpt-4o',
      conversationId: 'conv-1',
    });
    turn.end();

    const span = findSpan(getExporter().getFinishedSpans(), 'invoke_agent');
    expect(span.kind).toBe(SpanKind.CLIENT);
    expect(span.attributes[ATTR_GEN_AI_OPERATION_NAME]).toBe('invoke_agent');
    expect(span.attributes[ATTR_GEN_AI_AGENT_NAME]).toBe('weather-bot');
    expect(span.attributes[ATTR_GEN_AI_REQUEST_MODEL]).toBe('gpt-4o');
    expect(span.attributes[ATTR_GEN_AI_CONVERSATION_ID]).toBe('conv-1');
    expect(span.parentSpanId).toBeUndefined();
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
});
