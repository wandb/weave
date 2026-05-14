import {SpanKind, SpanStatusCode} from '@opentelemetry/api';

import {GEN_AI_ATTR} from '../../genai/semconv';
import {Turn} from '../../genai/turn';

import {
  findSpan,
  setupExporterPerTest,
  setupGenAITestEnvironment,
} from './common';

describe('Turn', () => {
  setupGenAITestEnvironment();
  const getExporter = setupExporterPerTest();

  it('emits an invoke_agent span with GenAI agent / model attributes', async () => {
    const turn = await Turn.create({
      agentName: 'weather-bot',
      model: 'gpt-4o',
      conversationId: 'conv-1',
    });
    await turn.end();

    const span = findSpan(getExporter().getFinishedSpans(), 'invoke_agent');
    expect(span.kind).toBe(SpanKind.CLIENT);
    expect(span.attributes[GEN_AI_ATTR.GEN_AI_OPERATION_NAME]).toBe(
      'invoke_agent'
    );
    expect(span.attributes[GEN_AI_ATTR.GEN_AI_AGENT_NAME]).toBe('weather-bot');
    expect(span.attributes[GEN_AI_ATTR.GEN_AI_REQUEST_MODEL]).toBe('gpt-4o');
    expect(span.attributes[GEN_AI_ATTR.GEN_AI_CONVERSATION_ID]).toBe('conv-1');
    expect(span.parentSpanId).toBeUndefined();
  });

  it('end() is idempotent', async () => {
    const turn = await Turn.create({});
    await turn.end();
    await turn.end();
    expect(getExporter().getFinishedSpans()).toHaveLength(1);
  });

  it('records the error and sets ERROR status when end({ error }) is called', async () => {
    const turn = await Turn.create({});
    await turn.end({error: new Error('boom')});
    const span = findSpan(getExporter().getFinishedSpans(), 'invoke_agent');
    expect(span.status.code).toBe(SpanStatusCode.ERROR);
    expect(span.status.message).toBe('boom');
    expect(span.events.some(e => e.name === 'exception')).toBe(true);
  });
});
