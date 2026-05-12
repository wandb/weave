/**
 * Tests for the Weave Session SDK (TypeScript port).
 *
 * Covers the same shapes as the Python tests in
 * `tests/session/test_session_otel.py`: invariants on the data types and
 * end-to-end OTel attribute emission.
 */

import {trace} from '@opentelemetry/api';
import {
  BasicTracerProvider,
  InMemorySpanExporter,
  SimpleSpanProcessor,
} from '@opentelemetry/sdk-trace-base';

import {
  endLlm,
  endSession,
  endTurn,
  executeToolAttributes,
  getCurrentSession,
  getCurrentTurn,
  invokeAgentAttributes,
  LLM,
  llmAttributes,
  LogResult,
  logTurn,
  Message,
  Reasoning,
  Session,
  startSession,
  toJsonString,
  Tool,
  toolCallPart,
  Turn,
  Usage,
} from '../session';

// ---------------------------------------------------------------------------
// Test harness — install an in-memory OTel exporter
// ---------------------------------------------------------------------------

let exporter: InMemorySpanExporter;
let provider: BasicTracerProvider;

beforeEach(() => {
  exporter = new InMemorySpanExporter();
  provider = new BasicTracerProvider({
    spanProcessors: [new SimpleSpanProcessor(exporter)],
  });
  trace.setGlobalTracerProvider(provider);
});

afterEach(async () => {
  // Reset module-level "current" pointers in case a test left state behind.
  endLlm();
  endTurn();
  endSession();
  await provider.shutdown();
  trace.disable();
});

function findSpan(name: string) {
  return exporter.getFinishedSpans().find(s => s.name === name);
}

// ---------------------------------------------------------------------------
// Data types
// ---------------------------------------------------------------------------

describe('Message', () => {
  it('builds user/system/assistant from static helpers', () => {
    expect(Message.user('hi').content).toBe('hi');
    expect(Message.system('be helpful').role).toBe('system');
    const asst = Message.assistant('done');
    expect(asst.role).toBe('assistant');
    expect(asst.parts).toEqual([]);
  });

  it('promotes assistant to parts when tool_calls present', () => {
    const msg = Message.assistant('let me check', {
      toolCalls: [
        toolCallPart({id: 'c1', name: 'get_weather', arguments: {q: 'sf'}}),
      ],
    });
    expect(msg.parts).toHaveLength(2);
    expect(msg.parts[0]).toEqual({type: 'text', content: 'let me check'});
    expect(msg.parts[1]).toEqual({
      type: 'tool_call',
      id: 'c1',
      name: 'get_weather',
      arguments: '{"q":"sf"}',
    });
  });

  it('toolResult JSON-encodes non-string output', () => {
    const msg = Message.toolResult('c1', {temp: 72});
    expect(msg.parts[0]).toEqual({
      type: 'tool_call_response',
      id: 'c1',
      response: '{"temp":72}',
    });
  });
});

describe('Usage', () => {
  it('defaults to zeros', () => {
    expect(new Usage().inputTokens).toBe(0);
    expect(new Usage().outputTokens).toBe(0);
  });
});

describe('toJsonString', () => {
  it('passes through strings, encodes objects, empties for null/undefined', () => {
    expect(toJsonString('hi')).toBe('hi');
    expect(toJsonString({a: 1})).toBe('{"a":1}');
    expect(toJsonString(null)).toBe('');
    expect(toJsonString(undefined)).toBe('');
    expect(toJsonString(42)).toBe('42');
  });
});

describe('LogResult', () => {
  it('defaults', () => {
    const r = new LogResult();
    expect(r.sessionId).toBe('');
    expect(r.traceIds).toEqual([]);
    expect(r.spanCount).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// Attribute builders
// ---------------------------------------------------------------------------

describe('invokeAgentAttributes', () => {
  it('sets required fields', () => {
    const attrs = invokeAgentAttributes({
      agentName: 'weather-bot',
      conversationId: 'sess-1',
      model: 'gpt-4',
    });
    expect(attrs['gen_ai.operation.name']).toBe('invoke_agent');
    expect(attrs['gen_ai.agent.name']).toBe('weather-bot');
    expect(attrs['gen_ai.conversation.id']).toBe('sess-1');
    expect(attrs['gen_ai.request.model']).toBe('gpt-4');
  });

  it('serializes input messages to JSON parts model', () => {
    const attrs = invokeAgentAttributes({
      agentName: 'a',
      inputMessages: [Message.user('hi')],
    });
    const parsed = JSON.parse(attrs['gen_ai.input.messages'] as string);
    expect(parsed).toEqual([
      {role: 'user', parts: [{type: 'text', content: 'hi'}]},
    ]);
  });
});

describe('llmAttributes', () => {
  it('emits usage only when non-zero', () => {
    const attrs = llmAttributes({
      model: 'gpt-4',
      usage: new Usage({inputTokens: 10, outputTokens: 5}),
    });
    expect(attrs['gen_ai.usage.input_tokens']).toBe(10);
    expect(attrs['gen_ai.usage.output_tokens']).toBe(5);
    expect(attrs['gen_ai.usage.reasoning_tokens']).toBeUndefined();
  });

  it('folds reasoning into the last assistant output message', () => {
    const attrs = llmAttributes({
      model: 'gpt-4',
      outputMessages: [Message.assistant('the answer is 42')],
      reasoning: new Reasoning({content: 'thinking...'}),
    });
    const parsed = JSON.parse(attrs['gen_ai.output.messages'] as string);
    expect(parsed[0].parts[0]).toEqual({
      type: 'reasoning',
      content: 'thinking...',
    });
    expect(parsed[0].parts[1]).toEqual({
      type: 'text',
      content: 'the answer is 42',
    });
  });

  it('attaches finish_reason to the last output message', () => {
    const attrs = llmAttributes({
      model: 'gpt-4',
      outputMessages: [Message.assistant('done')],
      finishReasons: ['stop'],
    });
    const parsed = JSON.parse(attrs['gen_ai.output.messages'] as string);
    expect(parsed[0].finish_reason).toBe('stop');
    expect(attrs['gen_ai.response.finish_reasons']).toEqual(['stop']);
  });
});

describe('executeToolAttributes', () => {
  it('sets operation and tool name', () => {
    const attrs = executeToolAttributes({
      toolName: 'get_weather',
      toolCallArguments: '{"q":"sf"}',
      toolCallResult: '{"temp":72}',
    });
    expect(attrs['gen_ai.operation.name']).toBe('execute_tool');
    expect(attrs['gen_ai.tool.name']).toBe('get_weather');
    expect(attrs['gen_ai.tool.call.arguments']).toBe('{"q":"sf"}');
    expect(attrs['gen_ai.tool.call.result']).toBe('{"temp":72}');
  });
});

// ---------------------------------------------------------------------------
// Span lifecycle — Session / Turn / LLM / Tool
// ---------------------------------------------------------------------------

describe('Session / Turn lifecycle', () => {
  it('creates a turn with invoke_agent attributes and registers current', () => {
    const session = startSession({agentName: 'weather', model: 'gpt-4'});
    expect(getCurrentSession()).toBe(session);

    const turn = session.startTurn({userMessage: 'hi'});
    expect(getCurrentTurn()).toBe(turn);

    turn.end();
    session.end();

    const span = findSpan('invoke_agent weather');
    expect(span).toBeDefined();
    expect(span!.attributes['gen_ai.operation.name']).toBe('invoke_agent');
    expect(span!.attributes['gen_ai.agent.name']).toBe('weather');
    expect(span!.attributes['gen_ai.conversation.id']).toBe(session.sessionId);
  });

  it('auto-ends the previous turn when starting a new one', () => {
    const session = startSession({agentName: 'a'});
    session.startTurn({userMessage: 'first'});
    session.startTurn({userMessage: 'second'});
    session.end();
    expect(exporter.getFinishedSpans()).toHaveLength(2);
  });

  it('records input messages on the turn span when includeContent=true', () => {
    const session = startSession({agentName: 'a'});
    const turn = session.startTurn({userMessage: 'hello'});
    turn.end();
    session.end();
    const span = findSpan('invoke_agent a')!;
    const msgs = JSON.parse(span.attributes['gen_ai.input.messages'] as string);
    expect(msgs).toEqual([
      {role: 'user', parts: [{type: 'text', content: 'hello'}]},
    ]);
  });

  it('omits content when includeContent=false', () => {
    const session = startSession({agentName: 'a', includeContent: false});
    const turn = session.startTurn({userMessage: 'secret'});
    turn.end();
    session.end();
    const span = findSpan('invoke_agent a')!;
    expect(span.attributes['gen_ai.input.messages']).toBeUndefined();
  });
});

describe('LLM lifecycle', () => {
  it('emits chat span with usage and messages', () => {
    const session = startSession({agentName: 'a', model: 'gpt-4'});
    const turn = session.startTurn({userMessage: 'hi'});
    const llm = turn.llm({providerName: 'openai'}).start();
    llm.record({
      inputMessages: [Message.user('hi')],
      outputMessages: [Message.assistant('hello!')],
      usage: new Usage({inputTokens: 10, outputTokens: 5}),
      finishReasons: ['stop'],
    });
    llm.end();
    turn.end();
    session.end();

    const span = findSpan('chat gpt-4')!;
    expect(span.attributes['gen_ai.provider.name']).toBe('openai');
    expect(span.attributes['gen_ai.usage.input_tokens']).toBe(10);
    expect(span.attributes['gen_ai.usage.output_tokens']).toBe(5);
    expect(span.attributes['gen_ai.response.finish_reasons']).toEqual(['stop']);
  });
});

describe('Tool lifecycle', () => {
  it('emits execute_tool span with arguments/result', () => {
    const session = startSession({agentName: 'a'});
    const turn = session.startTurn({});
    const tool = new Tool({
      name: 'get_weather',
      arguments: {q: 'sf'},
      toolCallId: 'c1',
    });
    tool.start();
    tool.result = {temp: 72};
    tool.end();
    turn.end();
    session.end();

    const span = findSpan('execute_tool get_weather')!;
    expect(span.attributes['gen_ai.operation.name']).toBe('execute_tool');
    expect(span.attributes['gen_ai.tool.call.arguments']).toBe('{"q":"sf"}');
    expect(span.attributes['gen_ai.tool.call.result']).toBe('{"temp":72}');
    expect(span.attributes['gen_ai.tool.call.id']).toBe('c1');
  });
});

// ---------------------------------------------------------------------------
// Batch logging
// ---------------------------------------------------------------------------

describe('logTurn', () => {
  it('emits one parent invoke_agent span and child spans', () => {
    const startedAt = new Date(2026, 0, 1);
    const endedAt = new Date(2026, 0, 1, 0, 0, 1);

    const llm = new LLM({model: 'gpt-4', providerName: 'openai'});
    llm.startedAt = startedAt;
    llm.endedAt = endedAt;
    llm.record({
      inputMessages: [Message.user('hi')],
      outputMessages: [Message.assistant('hello')],
    });

    const result = logTurn({
      sessionId: 'sess-1',
      agentName: 'demo',
      sessionName: 'My Session',
      model: 'gpt-4',
      messages: [Message.user('hi')],
      spans: [llm],
      startedAt,
      endedAt,
    });

    expect(result.spanCount).toBe(2);
    expect(result.traceIds).toHaveLength(1);
    const all = exporter.getFinishedSpans();
    const turnSpan = all.find(s => s.name === 'invoke_agent demo')!;
    const chatSpan = all.find(s => s.name === 'chat gpt-4')!;
    expect(chatSpan.parentSpanId).toBe(turnSpan.spanContext().spanId);
    expect(turnSpan.attributes['gen_ai.conversation.name']).toBe('My Session');
  });
});

// ---------------------------------------------------------------------------
// LLM helpers
// ---------------------------------------------------------------------------

describe('LLM helpers', () => {
  it('attachMediaUrl handles data: URLs and plain URIs', () => {
    const llm = new LLM({model: 'gpt-4'});
    llm.attachMediaUrl('data:image/png;base64,AAAA');
    llm.attachMediaUrl('https://example.com/img.png');
    expect(llm.mediaAttachments).toHaveLength(2);
    expect(llm.mediaAttachments[0].kind).toBe('blob');
    expect(llm.mediaAttachments[0].mimeType).toBe('image/png');
    expect(llm.mediaAttachments[0].modality).toBe('image');
    expect(llm.mediaAttachments[1].kind).toBe('uri');
  });

  it('record only sets fields that are explicitly passed', () => {
    const llm = new LLM({model: 'gpt-4'});
    llm.responseId = 'r-1';
    llm.record({outputMessages: [Message.assistant('hi')]});
    expect(llm.responseId).toBe('r-1');
    expect(llm.outputMessages).toHaveLength(1);
  });

  it('record accepts a string for reasoning', () => {
    const llm = new LLM({model: 'gpt-4'});
    llm.record({reasoning: 'thinking...'});
    expect(llm.reasoning.content).toBe('thinking...');
  });
});

// ---------------------------------------------------------------------------
// Adapters
// ---------------------------------------------------------------------------

describe('OpenAI adapter', () => {
  it('messageFromOpenAIResponsesInput converts user + function_call items', async () => {
    const {messageFromOpenAIResponsesInput} = await import(
      '../session/adapters/openai'
    );
    const {messages, attachments} = messageFromOpenAIResponsesInput([
      {role: 'user', content: 'what is the weather?'},
      {
        type: 'function_call',
        call_id: 'c1',
        name: 'get_weather',
        arguments: '{"q":"sf"}',
      },
      {
        type: 'function_call_output',
        call_id: 'c1',
        output: '{"temp":72}',
      },
    ]);
    expect(messages).toHaveLength(3);
    expect(messages[0].content).toBe('what is the weather?');
    expect(messages[1].role).toBe('assistant');
    expect(messages[1].parts[0]).toMatchObject({
      type: 'tool_call',
      name: 'get_weather',
    });
    expect(messages[2].role).toBe('tool');
    expect(attachments).toHaveLength(0);
  });

  it('usageFromOpenAIResponses handles missing usage', async () => {
    const {usageFromOpenAIResponses} = await import(
      '../session/adapters/openai'
    );
    expect(usageFromOpenAIResponses({} as never).inputTokens).toBe(0);
    expect(
      usageFromOpenAIResponses({
        usage: {
          input_tokens: 10,
          output_tokens: 5,
          output_tokens_details: {reasoning_tokens: 3},
        },
      } as never).reasoningTokens
    ).toBe(3);
  });
});

describe('Anthropic adapter', () => {
  it('usageFromAnthropic extracts tokens, defaults cache fields', async () => {
    const {usageFromAnthropic} = await import('../session/adapters/anthropic');
    const u = usageFromAnthropic({
      usage: {input_tokens: 100, output_tokens: 50},
    });
    expect(u.inputTokens).toBe(100);
    expect(u.outputTokens).toBe(50);
    expect(u.cacheCreationInputTokens).toBe(0);
  });
});
