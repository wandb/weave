import {SpanKind} from '@opentelemetry/api';

import {
  ATTR_GEN_AI_INPUT_MESSAGES,
  ATTR_GEN_AI_OUTPUT_MESSAGES,
  ATTR_GEN_AI_USAGE_CACHE_CREATION_INPUT_TOKENS,
  ATTR_GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS,
  ATTR_GEN_AI_USAGE_INPUT_TOKENS,
  ATTR_GEN_AI_USAGE_OUTPUT_TOKENS,
  ATTR_GEN_AI_USAGE_REASONING_OUTPUT_TOKENS,
} from '../../genai/semconv';
import {Turn} from '../../genai/turn';

import {
  expectSpanTimesToMatch,
  findSpan,
  setupExporterPerTest,
  setupGenAITestEnvironment,
  spanSnapshot,
} from './common';

describe('LLM (via Turn.startLLM)', () => {
  setupGenAITestEnvironment();
  const getExporter = setupExporterPerTest();

  it("emits a 'chat' span as a child of the turn's invoke_agent span", () => {
    const turn = Turn.create({agentName: 'a', conversationId: 'conv-1'});
    const llm = turn.startLLM({
      model: 'gpt-4o',
      providerName: 'openai',
      systemInstructions: ['Be helpful', 'Be concise'],
    });
    llm.end();
    turn.end();

    const spans = getExporter().getFinishedSpans();
    const llmSpan = findSpan(spans, 'chat');
    const turnSpan = findSpan(spans, 'invoke_agent');

    expect(llmSpan.kind).toBe(SpanKind.CLIENT);
    expect(llmSpan.parentSpanId).toBe(turnSpan.spanContext().spanId);
    expect(llmSpan.spanContext().traceId).toBe(turnSpan.spanContext().traceId);

    expect(spanSnapshot(llmSpan)).toMatchInlineSnapshot(`
      {
        "attributes": {
          "gen_ai.conversation.id": "<uuid>",
          "gen_ai.operation.name": "chat",
          "gen_ai.provider.name": "openai",
          "gen_ai.request.model": "gpt-4o",
          "gen_ai.system_instructions": "[{"type":"text","content":"Be helpful"},{"type":"text","content":"Be concise"}]",
        },
        "endTime": "<timestamp>",
        "startTime": "<timestamp>",
      }
    `);
  });

  it('serializes input/output messages and usage at end()', () => {
    const turn = Turn.create({});
    const llm = turn.startLLM({model: 'gpt-4o'});
    llm.inputMessages = [{role: 'user', content: 'hi'}];
    llm.outputMessages = [{role: 'assistant', content: 'hello'}];
    llm.usage = {
      inputTokens: 10,
      outputTokens: 5,
      reasoningTokens: 2,
      cacheReadInputTokens: 1,
      cacheCreationInputTokens: 3,
    };
    llm.end();
    turn.end();

    const llmSpan = findSpan(getExporter().getFinishedSpans(), 'chat');
    expect(
      JSON.parse(llmSpan.attributes[ATTR_GEN_AI_INPUT_MESSAGES] as string)
    ).toEqual([{role: 'user', content: 'hi'}]);
    expect(
      JSON.parse(llmSpan.attributes[ATTR_GEN_AI_OUTPUT_MESSAGES] as string)
    ).toEqual([{role: 'assistant', content: 'hello'}]);
    expect(llmSpan.attributes[ATTR_GEN_AI_USAGE_INPUT_TOKENS]).toBe(10);
    expect(llmSpan.attributes[ATTR_GEN_AI_USAGE_OUTPUT_TOKENS]).toBe(5);
    expect(llmSpan.attributes[ATTR_GEN_AI_USAGE_REASONING_OUTPUT_TOKENS]).toBe(
      2
    );
    expect(llmSpan.attributes[ATTR_GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS]).toBe(
      1
    );
    expect(
      llmSpan.attributes[ATTR_GEN_AI_USAGE_CACHE_CREATION_INPUT_TOKENS]
    ).toBe(3);
  });

  it("omits message + usage attributes when fields aren't populated", () => {
    const turn = Turn.create({});
    const llm = turn.startLLM({model: 'gpt-4o'});
    llm.end();
    turn.end();

    const llmSpan = findSpan(getExporter().getFinishedSpans(), 'chat');
    expect(llmSpan.attributes[ATTR_GEN_AI_INPUT_MESSAGES]).toBeUndefined();
    expect(llmSpan.attributes[ATTR_GEN_AI_OUTPUT_MESSAGES]).toBeUndefined();
    expect(llmSpan.attributes[ATTR_GEN_AI_USAGE_INPUT_TOKENS]).toBeUndefined();
  });

  // ---------------------------------------------------------------------------
  // Enrichment surface
  // ---------------------------------------------------------------------------

  describe('enrichment', () => {
    it('output(content) appends a new assistant message', () => {
      const turn = Turn.create({});
      const llm = turn.startLLM({model: 'gpt-4o'});
      llm.output('Hello!');
      llm.end();
      turn.end();

      const llmSpan = findSpan(getExporter().getFinishedSpans(), 'chat');
      expect(
        JSON.parse(llmSpan.attributes[ATTR_GEN_AI_OUTPUT_MESSAGES] as string)
      ).toEqual([{role: 'assistant', content: 'Hello!'}]);
    });

    it('each output() call adds its own assistant message', () => {
      const turn = Turn.create({});
      const llm = turn.startLLM({model: 'gpt-4o'});
      llm.output('first').output('second');
      llm.end();
      turn.end();

      const llmSpan = findSpan(getExporter().getFinishedSpans(), 'chat');
      const messages = JSON.parse(
        llmSpan.attributes[ATTR_GEN_AI_OUTPUT_MESSAGES] as string
      );
      expect(messages).toEqual([
        {role: 'assistant', content: 'first'},
        {role: 'assistant', content: 'second'},
      ]);
    });

    it('think(content) accumulates into the reasoning field', () => {
      const turn = Turn.create({});
      const llm = turn.startLLM({model: 'gpt-4o'});
      llm.think('First, ').think('I need to check the weather.');
      expect(llm.reasoning).toEqual({
        content: 'First, I need to check the weather.',
      });
      llm.end();
      turn.end();
    });

    it('end() folds reasoning into the last assistant message as a ReasoningPart', () => {
      const turn = Turn.create({});
      const llm = turn.startLLM({model: 'gpt-4o'});
      llm.output('hello').think('thinking out loud');
      llm.end();
      turn.end();

      const llmSpan = findSpan(getExporter().getFinishedSpans(), 'chat');
      const messages = JSON.parse(
        llmSpan.attributes[ATTR_GEN_AI_OUTPUT_MESSAGES] as string
      );
      expect(messages).toHaveLength(1);
      // output() produced {role:'assistant', content:'hello'}; end() promoted
      // it to parts and appended the ReasoningPart.
      expect(messages[0].parts).toEqual([
        {type: 'text', content: 'hello'},
        {type: 'reasoning', content: 'thinking out loud'},
      ]);
    });

    it('attachMedia({content, mimeType, modality}) appends a blob part to the last input message', () => {
      const turn = Turn.create({});
      const llm = turn.startLLM({model: 'gpt-4o'});
      llm.inputMessages = [{role: 'user', content: 'Listen to this:'}];
      llm.attachMedia({
        content: 'base64data',
        mimeType: 'audio/mp3',
        modality: 'audio',
      });
      llm.end();
      turn.end();

      const llmSpan = findSpan(getExporter().getFinishedSpans(), 'chat');
      const messages = JSON.parse(
        llmSpan.attributes[ATTR_GEN_AI_INPUT_MESSAGES] as string
      );
      expect(messages).toHaveLength(1);
      expect(messages[0].role).toBe('user');
      expect(messages[0].parts).toEqual([
        {type: 'text', content: 'Listen to this:'},
        {
          type: 'blob',
          content: 'base64data',
          mimeType: 'audio/mp3',
          modality: 'audio',
        },
      ]);
    });

    it('attachMedia({uri, modality}) appends a uri part', () => {
      const turn = Turn.create({});
      const llm = turn.startLLM({model: 'gpt-4o'});
      llm.attachMedia({uri: 'https://example.com/a.png', modality: 'image'});
      llm.end();
      turn.end();

      const llmSpan = findSpan(getExporter().getFinishedSpans(), 'chat');
      const messages = JSON.parse(
        llmSpan.attributes[ATTR_GEN_AI_INPUT_MESSAGES] as string
      );
      expect(messages[0].parts).toEqual([
        {type: 'uri', uri: 'https://example.com/a.png', modality: 'image'},
      ]);
    });

    it('attachMedia({fileId, modality, mimeType}) appends a file part', () => {
      const turn = Turn.create({});
      const llm = turn.startLLM({model: 'gpt-4o'});
      llm.attachMedia({
        fileId: 'f-123',
        modality: 'document',
        mimeType: 'application/pdf',
      });
      llm.end();
      turn.end();

      const llmSpan = findSpan(getExporter().getFinishedSpans(), 'chat');
      const messages = JSON.parse(
        llmSpan.attributes[ATTR_GEN_AI_INPUT_MESSAGES] as string
      );
      expect(messages[0].parts).toEqual([
        {
          type: 'file',
          fileId: 'f-123',
          modality: 'document',
          mimeType: 'application/pdf',
        },
      ]);
    });

    it('attachMediaUrl(url, opts) delegates to the uri form', () => {
      const turn = Turn.create({});
      const llm = turn.startLLM({model: 'gpt-4o'});
      llm.attachMediaUrl('https://example.com/v.mp4', {modality: 'video'});
      llm.end();
      turn.end();

      const llmSpan = findSpan(getExporter().getFinishedSpans(), 'chat');
      const messages = JSON.parse(
        llmSpan.attributes[ATTR_GEN_AI_INPUT_MESSAGES] as string
      );
      expect(messages[0].parts).toEqual([
        {type: 'uri', uri: 'https://example.com/v.mp4', modality: 'video'},
      ]);
    });

    it('record(opts) replaces the data fields', () => {
      const turn = Turn.create({});
      const llm = turn.startLLM({model: 'gpt-4o'});
      llm.inputMessages = [{role: 'user', content: 'will be replaced'}];
      llm.record({
        inputMessages: [{role: 'user', content: 'hi'}],
        outputMessages: [{role: 'assistant', content: 'hello'}],
        usage: {inputTokens: 7, outputTokens: 3},
        reasoning: {content: 'thinking'},
      });
      expect(llm.inputMessages).toEqual([{role: 'user', content: 'hi'}]);
      expect(llm.outputMessages).toEqual([
        {role: 'assistant', content: 'hello'},
      ]);
      expect(llm.usage).toEqual({inputTokens: 7, outputTokens: 3});
      expect(llm.reasoning).toEqual({content: 'thinking'});
      llm.end();
      turn.end();
    });

    it('chains: output / think / attachMedia / record all return `this`', () => {
      const turn = Turn.create({});
      const llm = turn.startLLM({model: 'gpt-4o'});
      const result = llm
        .output('hi')
        .think('thoughts')
        .attachMediaUrl('https://example.com/a.png', {modality: 'image'})
        .record({usage: {inputTokens: 1}});
      expect(result).toBe(llm);
      llm.end();
      turn.end();
    });

    it('startTime/endTime backdate the chat span window', () => {
      const turn = Turn.create({});
      const startedAt = new Date('2026-01-01T00:00:00Z');
      const endedAt = new Date('2026-01-01T00:00:05Z');
      const llm = turn.startLLM({model: 'gpt-4o', startTime: startedAt});
      llm.end({endTime: endedAt});
      turn.end();

      const llmSpan = findSpan(getExporter().getFinishedSpans(), 'chat');
      expectSpanTimesToMatch(llmSpan, startedAt, endedAt);
    });

    it('setAttributes records attributes on the chat span; warns + no-op after end()', () => {
      const warnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});
      const turn = Turn.create({});
      const llm = turn.startLLM({model: 'gpt-4o'});
      llm.setAttributes({
        'gen_ai.response.id': 'resp-abc',
        'gen_ai.output.type': 'text',
      });
      llm.end();
      llm.setAttributes({'after.end': 'x'});
      turn.end();

      const llmSpan = findSpan(getExporter().getFinishedSpans(), 'chat');
      expect(llmSpan.attributes['gen_ai.response.id']).toBe('resp-abc');
      expect(llmSpan.attributes['gen_ai.output.type']).toBe('text');
      expect(llmSpan.attributes['after.end']).toBeUndefined();
      expect(warnSpy).toHaveBeenCalledWith(
        expect.stringContaining('LLM.setAttributes() called after end()')
      );
      warnSpy.mockRestore();
    });

    it('addEvent records a span event on the chat span; warns + no-op after end()', () => {
      const warnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});
      const turn = Turn.create({});
      const llm = turn.startLLM({model: 'gpt-4o'});
      llm.addEvent('gen_ai.content.completion', {finish_reason: 'stop'});
      llm.end();
      llm.addEvent('after.end');
      turn.end();

      const llmSpan = findSpan(getExporter().getFinishedSpans(), 'chat');
      expect(llmSpan.events).toHaveLength(1);
      expect(llmSpan.events[0].name).toBe('gen_ai.content.completion');
      expect(warnSpy).toHaveBeenCalledWith(
        expect.stringContaining('LLM.addEvent() called after end()')
      );
      warnSpy.mockRestore();
    });

    it('accumulators called after end() warn and do not mutate state', () => {
      const warnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});

      const turn = Turn.create({});
      const llm = turn.startLLM({model: 'gpt-4o'});
      llm.end();

      llm.output('after end');
      llm.think('after end');
      llm.attachMedia({
        content: 'x',
        mimeType: 'audio/mp3',
        modality: 'audio',
      });
      llm.attachMediaUrl('https://example.com/x', {modality: 'image'});
      llm.record({inputMessages: [{role: 'user', content: 'after end'}]});

      // One warning per method.
      expect(warnSpy).toHaveBeenCalledTimes(5);
      for (const method of [
        'output',
        'think',
        'attachMedia',
        'attachMediaUrl',
        'record',
      ]) {
        expect(warnSpy).toHaveBeenCalledWith(
          expect.stringContaining(`LLM.${method}() called after end()`)
        );
      }

      // State on the instance is untouched.
      expect(llm.outputMessages).toEqual([]);
      expect(llm.inputMessages).toEqual([]);
      expect(llm.reasoning).toBeUndefined();

      turn.end();
      warnSpy.mockRestore();
    });
  });
});
