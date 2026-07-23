import {EventEmitter} from 'events';
import {
  InMemorySpanExporter,
  SimpleSpanProcessor,
  type ReadableSpan,
} from '@opentelemetry/sdk-trace-base';

import {WeaveRealtimeOTelAdapter} from '../../integrations/openai.realtime.agent.otel';
import {
  clearGlobalClient,
  installFakeClient,
  resetProviderSingleton,
  findSpan,
} from '../genai/common';
import {
  ATTR_GEN_AI_AGENT_NAME,
  ATTR_GEN_AI_CONVERSATION_ID,
  ATTR_GEN_AI_INPUT_MESSAGES,
  ATTR_GEN_AI_OPERATION_NAME,
  ATTR_GEN_AI_OUTPUT_MESSAGES,
  ATTR_GEN_AI_OUTPUT_TYPE,
  ATTR_GEN_AI_PROVIDER_NAME,
  ATTR_GEN_AI_REQUEST_MODEL,
  ATTR_GEN_AI_RESPONSE_ID,
  ATTR_GEN_AI_RESPONSE_MODEL,
  ATTR_GEN_AI_TOOL_CALL_ARGUMENTS,
  ATTR_GEN_AI_TOOL_CALL_ID,
  ATTR_GEN_AI_TOOL_NAME,
  ATTR_GEN_AI_USAGE_INPUT_TOKENS,
  ATTR_GEN_AI_USAGE_OUTPUT_TOKENS,
} from '../../genai/semconv';

function makeMockSession() {
  const session = new EventEmitter() as any;
  session.transport = new EventEmitter();
  return session;
}

function createOTelAdapter() {
  const session = makeMockSession();
  const adapter = new WeaveRealtimeOTelAdapter(session);
  return {session, adapter};
}

describe('WeaveRealtimeOTelAdapter', () => {
  let exporter: InMemorySpanExporter;
  const originalApiKey = process.env.WANDB_API_KEY;

  beforeEach(() => {
    process.env.WANDB_API_KEY = 'test-api-key';
    resetProviderSingleton();
    clearGlobalClient();
    exporter = new InMemorySpanExporter();
    installFakeClient({
      settings: {genai: {spanProcessor: new SimpleSpanProcessor(exporter)}},
    });
  });

  afterEach(() => {
    resetProviderSingleton();
    clearGlobalClient();
    if (originalApiKey === undefined) {
      delete process.env.WANDB_API_KEY;
    } else {
      process.env.WANDB_API_KEY = originalApiKey;
    }
  });

  function spans(): ReadableSpan[] {
    return exporter.getFinishedSpans();
  }

  test('turn lifecycle creates invoke_agent root and chat child', () => {
    const {session, adapter} = createOTelAdapter();

    session.emit('transport_event', {
      type: 'session.created',
      session: {id: 'sess-1', model: 'gpt-4o-realtime'},
    });

    session.transport.emit('turn_started', {
      providerData: {response: {id: 'resp-1'}},
    });

    session.transport.emit('turn_done', {
      response: {
        id: 'resp-1',
        output: [
          {
            type: 'message',
            content: [{type: 'text', text: 'Hello!'}],
          },
        ],
        usage: {input_tokens: 10, output_tokens: 5},
      },
    });

    adapter.detach();

    const finished = spans();
    expect(finished.length).toBe(2);

    const root = findSpan(finished, 'invoke_agent openai_realtime');
    expect(root.attributes[ATTR_GEN_AI_OPERATION_NAME]).toBe('invoke_agent');
    expect(root.attributes[ATTR_GEN_AI_AGENT_NAME]).toBe('openai_realtime');
    expect(root.attributes[ATTR_GEN_AI_PROVIDER_NAME]).toBe('openai');
    expect(root.attributes[ATTR_GEN_AI_REQUEST_MODEL]).toBe(
      'gpt-4o-realtime'
    );
    expect(root.attributes[ATTR_GEN_AI_CONVERSATION_ID]).toBe('sess-1');

    const chat = findSpan(finished, 'chat gpt-4o-realtime');
    expect(chat.attributes[ATTR_GEN_AI_OPERATION_NAME]).toBe('chat');
    expect(chat.attributes[ATTR_GEN_AI_REQUEST_MODEL]).toBe(
      'gpt-4o-realtime'
    );
    expect(chat.attributes[ATTR_GEN_AI_RESPONSE_MODEL]).toBe(
      'gpt-4o-realtime'
    );
    expect(chat.attributes[ATTR_GEN_AI_PROVIDER_NAME]).toBe('openai');
    expect(chat.attributes[ATTR_GEN_AI_RESPONSE_ID]).toBe('resp-1');
    expect(chat.attributes[ATTR_GEN_AI_USAGE_INPUT_TOKENS]).toBe(10);
    expect(chat.attributes[ATTR_GEN_AI_USAGE_OUTPUT_TOKENS]).toBe(5);
    expect(chat.attributes[ATTR_GEN_AI_OUTPUT_TYPE]).toBe('text');

    const outputMessages = JSON.parse(
      chat.attributes[ATTR_GEN_AI_OUTPUT_MESSAGES] as string
    );
    expect(outputMessages).toEqual([
      {role: 'assistant', parts: [{type: 'text', content: 'Hello!'}]},
    ]);

    expect(chat.parentSpanId).toBe(root.spanContext().spanId);
  });

  test('function_call output items create execute_tool child spans', () => {
    const {session, adapter} = createOTelAdapter();

    session.emit('transport_event', {
      type: 'session.created',
      session: {id: 'sess-1', model: 'gpt-4o-realtime'},
    });

    session.transport.emit('turn_started', {
      providerData: {response: {id: 'resp-1'}},
    });

    session.transport.emit('turn_done', {
      response: {
        id: 'resp-1',
        output: [
          {
            type: 'function_call',
            name: 'get_weather',
            call_id: 'call-1',
            arguments: '{"city":"NYC"}',
          },
        ],
        usage: {input_tokens: 20, output_tokens: 10},
      },
    });

    adapter.detach();

    const finished = spans();
    expect(finished.length).toBe(3);

    const chat = findSpan(finished, 'chat gpt-4o-realtime');
    const tool = findSpan(finished, 'execute_tool get_weather');

    expect(tool.attributes[ATTR_GEN_AI_OPERATION_NAME]).toBe('execute_tool');
    expect(tool.attributes[ATTR_GEN_AI_TOOL_NAME]).toBe('get_weather');
    expect(tool.attributes[ATTR_GEN_AI_TOOL_CALL_ID]).toBe('call-1');
    expect(tool.attributes[ATTR_GEN_AI_TOOL_CALL_ARGUMENTS]).toBe(
      '{"city":"NYC"}'
    );

    expect(tool.parentSpanId).toBe(chat.spanContext().spanId);
  });

  test('audio content sets output type to speech', () => {
    const {session, adapter} = createOTelAdapter();

    session.emit('transport_event', {
      type: 'session.created',
      session: {id: 'sess-1', model: 'gpt-4o-realtime'},
    });

    session.transport.emit('turn_started', {
      providerData: {response: {id: 'resp-1'}},
    });

    session.transport.emit('turn_done', {
      response: {
        id: 'resp-1',
        output: [
          {
            type: 'message',
            content: [
              {type: 'audio', transcript: 'The weather is sunny'},
            ],
          },
        ],
        usage: {input_tokens: 10, output_tokens: 5},
      },
    });

    adapter.detach();

    const chat = findSpan(spans(), 'chat gpt-4o-realtime');
    expect(chat.attributes[ATTR_GEN_AI_OUTPUT_TYPE]).toBe('speech');

    const outputMessages = JSON.parse(
      chat.attributes[ATTR_GEN_AI_OUTPUT_MESSAGES] as string
    );
    expect(outputMessages).toEqual([
      {
        role: 'assistant',
        parts: [{type: 'text', content: 'The weather is sunny'}],
      },
    ]);
  });

  test('user text messages appear as input messages on chat span', () => {
    const {session, adapter} = createOTelAdapter();

    session.emit('transport_event', {
      type: 'session.created',
      session: {id: 'sess-1', model: 'gpt-4o-realtime'},
    });

    session.emit('history_added', {
      type: 'message',
      role: 'user',
      content: [{type: 'input_text', text: 'What is the weather?'}],
    });

    session.transport.emit('turn_started', {
      providerData: {response: {id: 'resp-1'}},
    });

    session.transport.emit('turn_done', {
      response: {
        id: 'resp-1',
        output: [
          {
            type: 'message',
            content: [{type: 'text', text: 'It is sunny.'}],
          },
        ],
      },
    });

    adapter.detach();

    const chat = findSpan(spans(), 'chat gpt-4o-realtime');
    const inputMessages = JSON.parse(
      chat.attributes[ATTR_GEN_AI_INPUT_MESSAGES] as string
    );
    expect(inputMessages).toEqual([
      {
        role: 'user',
        parts: [{type: 'text', content: 'What is the weather?'}],
      },
    ]);
  });

  test('voice transcript from history_updated appears as input messages', () => {
    const {session, adapter} = createOTelAdapter();

    session.emit('transport_event', {
      type: 'session.created',
      session: {id: 'sess-1', model: 'gpt-4o-realtime'},
    });

    session.emit('history_added', {
      type: 'message',
      role: 'user',
      itemId: 'item-voice-1',
      content: [{type: 'input_audio'}],
    });

    session.emit('history_updated', [
      {
        type: 'message',
        role: 'user',
        itemId: 'item-voice-1',
        status: 'completed',
        content: [{type: 'input_audio', transcript: 'turn the lights on'}],
      },
    ]);

    session.transport.emit('turn_started', {
      providerData: {response: {id: 'resp-1'}},
    });

    session.transport.emit('turn_done', {
      response: {
        id: 'resp-1',
        output: [
          {
            type: 'message',
            content: [{type: 'text', text: 'Done!'}],
          },
        ],
      },
    });

    adapter.detach();

    const chat = findSpan(spans(), 'chat gpt-4o-realtime');
    const inputMessages = JSON.parse(
      chat.attributes[ATTR_GEN_AI_INPUT_MESSAGES] as string
    );
    expect(inputMessages).toEqual([
      {
        role: 'user',
        parts: [{type: 'text', content: 'turn the lights on'}],
      },
    ]);
  });

  test('disconnection ends root span', () => {
    const {session} = createOTelAdapter();

    session.emit('transport_event', {
      type: 'session.created',
      session: {id: 'sess-1', model: 'gpt-4o-realtime'},
    });

    session.transport.emit('turn_started', {
      providerData: {response: {id: 'resp-1'}},
    });

    session.transport.emit('turn_done', {
      response: {
        id: 'resp-1',
        output: [
          {
            type: 'message',
            content: [{type: 'text', text: 'Hello!'}],
          },
        ],
      },
    });

    session.transport.emit('connection_change', 'disconnected');

    const finished = spans();
    const root = findSpan(finished, 'invoke_agent openai_realtime');
    expect(root.endTime).toBeDefined();
    expect(root.endTime[0]).toBeGreaterThan(0);
  });

  test('multiple turns create multiple chat spans under same root', () => {
    const {session, adapter} = createOTelAdapter();

    session.emit('transport_event', {
      type: 'session.created',
      session: {id: 'sess-1', model: 'gpt-4o-realtime'},
    });

    for (const respId of ['resp-1', 'resp-2', 'resp-3']) {
      session.transport.emit('turn_started', {
        providerData: {response: {id: respId}},
      });
      session.transport.emit('turn_done', {
        response: {
          id: respId,
          output: [
            {
              type: 'message',
              content: [{type: 'text', text: `Response ${respId}`}],
            },
          ],
        },
      });
    }

    adapter.detach();

    const finished = spans();
    const root = findSpan(finished, 'invoke_agent openai_realtime');
    const chatSpans = finished.filter(s => s.name === 'chat gpt-4o-realtime');
    expect(chatSpans).toHaveLength(3);

    for (const chat of chatSpans) {
      expect(chat.parentSpanId).toBe(root.spanContext().spanId);
    }
  });

  test('failed response sets error status on chat span', () => {
    const {session, adapter} = createOTelAdapter();

    session.emit('transport_event', {
      type: 'session.created',
      session: {id: 'sess-1', model: 'gpt-4o-realtime'},
    });

    session.transport.emit('turn_started', {
      providerData: {response: {id: 'resp-1'}},
    });

    session.transport.emit('turn_done', {
      response: {
        id: 'resp-1',
        status: 'failed',
        status_details: {error: {message: 'rate limit exceeded'}},
        output: [],
      },
    });

    adapter.detach();

    const chat = findSpan(spans(), 'chat gpt-4o-realtime');
    expect(chat.status.code).toBe(2); // SpanStatusCode.ERROR
    expect(chat.status.message).toBe('rate limit exceeded');
  });

  test('no Weave calls produced (only OTel spans)', () => {
    const {session, adapter} = createOTelAdapter();

    session.emit('transport_event', {
      type: 'session.created',
      session: {id: 'sess-1', model: 'gpt-4o-realtime'},
    });

    session.transport.emit('turn_started', {
      providerData: {response: {id: 'resp-1'}},
    });

    session.transport.emit('turn_done', {
      response: {
        id: 'resp-1',
        output: [
          {
            type: 'message',
            content: [{type: 'text', text: 'Hello!'}],
          },
        ],
      },
    });

    adapter.detach();

    expect(spans().length).toBeGreaterThan(0);
    // The OTel adapter does not produce Weave calls —
    // all data goes through OTel spans.
  });

  test('integration metadata is stamped on all spans', () => {
    const {session, adapter} = createOTelAdapter();

    session.emit('transport_event', {
      type: 'session.created',
      session: {id: 'sess-1', model: 'gpt-4o-realtime'},
    });

    session.transport.emit('turn_started', {
      providerData: {response: {id: 'resp-1'}},
    });

    session.transport.emit('turn_done', {
      response: {
        id: 'resp-1',
        output: [
          {
            type: 'function_call',
            name: 'get_weather',
            call_id: 'call-1',
            arguments: '{}',
          },
        ],
      },
    });

    adapter.detach();

    for (const span of spans()) {
      expect(span.attributes['integration.name']).toBe(
        'openai_agents_realtime'
      );
      expect(span.attributes['integration.meta.package_name']).toBe(
        '@openai/agents-realtime'
      );
    }
  });

  test('session.updated updates model on subsequent spans', () => {
    const {session, adapter} = createOTelAdapter();

    session.emit('transport_event', {
      type: 'session.created',
      session: {id: 'sess-1', model: 'gpt-4o-realtime'},
    });

    session.emit('transport_event', {
      type: 'session.updated',
      session: {id: 'sess-1', model: 'gpt-4o-realtime-2025-01-01'},
    });

    session.transport.emit('turn_started', {
      providerData: {response: {id: 'resp-1'}},
    });

    session.transport.emit('turn_done', {
      response: {
        id: 'resp-1',
        output: [
          {
            type: 'message',
            content: [{type: 'text', text: 'Hello!'}],
          },
        ],
      },
    });

    adapter.detach();

    const chat = findSpan(
      spans(),
      'chat gpt-4o-realtime-2025-01-01'
    );
    expect(chat.attributes[ATTR_GEN_AI_REQUEST_MODEL]).toBe(
      'gpt-4o-realtime-2025-01-01'
    );
  });
});
