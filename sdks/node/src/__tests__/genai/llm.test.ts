import {SpanKind} from '@opentelemetry/api';

import {GEN_AI_ATTR} from '../../genai/semconv';
import {Turn} from '../../genai/turn';

import {
  findSpan,
  setupExporterPerTest,
  setupGenAITestEnvironment,
} from './common';

describe('LLM (via Turn.llm)', () => {
  setupGenAITestEnvironment();
  const getExporter = setupExporterPerTest();

  it("emits a 'chat' span as a child of the turn's invoke_agent span", async () => {
    const turn = await Turn.create({agentName: 'a', conversationId: 'conv-1'});
    const llm = await turn.llm({model: 'gpt-4o', providerName: 'openai'});
    await llm.end();
    await turn.end();

    const spans = getExporter().getFinishedSpans();
    const llmSpan = findSpan(spans, 'chat');
    const turnSpan = findSpan(spans, 'invoke_agent');

    expect(llmSpan.kind).toBe(SpanKind.CLIENT);
    expect(llmSpan.attributes[GEN_AI_ATTR.GEN_AI_OPERATION_NAME]).toBe('chat');
    expect(llmSpan.attributes[GEN_AI_ATTR.GEN_AI_REQUEST_MODEL]).toBe('gpt-4o');
    expect(llmSpan.attributes[GEN_AI_ATTR.GEN_AI_PROVIDER_NAME]).toBe('openai');
    expect(llmSpan.attributes[GEN_AI_ATTR.GEN_AI_CONVERSATION_ID]).toBe(
      'conv-1'
    );
    expect(llmSpan.parentSpanId).toBe(turnSpan.spanContext().spanId);
    expect(llmSpan.spanContext().traceId).toBe(turnSpan.spanContext().traceId);
  });

  it('serializes input/output messages and usage at end()', async () => {
    const turn = await Turn.create({});
    const llm = await turn.llm({model: 'gpt-4o'});
    llm.inputMessages = [{role: 'user', content: 'hi'}];
    llm.outputMessages = [{role: 'assistant', content: 'hello'}];
    llm.usage = {
      inputTokens: 10,
      outputTokens: 5,
      reasoningTokens: 2,
      cacheReadInputTokens: 1,
      cacheCreationInputTokens: 3,
    };
    await llm.end();
    await turn.end();

    const llmSpan = findSpan(getExporter().getFinishedSpans(), 'chat');
    expect(
      JSON.parse(
        llmSpan.attributes[GEN_AI_ATTR.GEN_AI_INPUT_MESSAGES] as string
      )
    ).toEqual([{role: 'user', content: 'hi'}]);
    expect(
      JSON.parse(
        llmSpan.attributes[GEN_AI_ATTR.GEN_AI_OUTPUT_MESSAGES] as string
      )
    ).toEqual([{role: 'assistant', content: 'hello'}]);
    expect(llmSpan.attributes[GEN_AI_ATTR.GEN_AI_USAGE_INPUT_TOKENS]).toBe(10);
    expect(llmSpan.attributes[GEN_AI_ATTR.GEN_AI_USAGE_OUTPUT_TOKENS]).toBe(5);
    expect(
      llmSpan.attributes[GEN_AI_ATTR.GEN_AI_USAGE_REASONING_OUTPUT_TOKENS]
    ).toBe(2);
    expect(
      llmSpan.attributes[GEN_AI_ATTR.GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS]
    ).toBe(1);
    expect(
      llmSpan.attributes[GEN_AI_ATTR.GEN_AI_USAGE_CACHE_CREATION_INPUT_TOKENS]
    ).toBe(3);
  });

  it("omits message + usage attributes when fields aren't populated", async () => {
    const turn = await Turn.create({});
    const llm = await turn.llm({model: 'gpt-4o'});
    await llm.end();
    await turn.end();

    const llmSpan = findSpan(getExporter().getFinishedSpans(), 'chat');
    expect(
      llmSpan.attributes[GEN_AI_ATTR.GEN_AI_INPUT_MESSAGES]
    ).toBeUndefined();
    expect(
      llmSpan.attributes[GEN_AI_ATTR.GEN_AI_OUTPUT_MESSAGES]
    ).toBeUndefined();
    expect(
      llmSpan.attributes[GEN_AI_ATTR.GEN_AI_USAGE_INPUT_TOKENS]
    ).toBeUndefined();
  });
});
