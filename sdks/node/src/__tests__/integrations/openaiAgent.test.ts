import {
  Agent,
  run,
  setTraceProcessors,
  setTracingDisabled,
  tool,
  Usage,
  withAgentSpan,
  withFunctionSpan,
  withGuardrailSpan,
  withTrace,
} from '@openai/agents';
import type {Model, ModelRequest, ModelResponse} from '@openai/agents';
import {
  InMemorySpanExporter,
  type ReadableSpan,
  SimpleSpanProcessor,
} from '@opentelemetry/sdk-trace-base';
import {z} from 'zod';
import * as weave from '../..';
import {clearWeaveTracerProvider} from '../../genai/provider';
import {Settings} from '../../settings';
import {initWithCustomTraceServer} from '../clientMock';
import {InMemoryTraceServer, Call} from '../helpers/inMemoryTraceServer';
import {agentsInstrumentedHolder} from 'weave/integrations/openai.agent';

describe('OpenAI Agents Integration', () => {
  withOpenAITracingEnabled();

  let inMemoryTraceServer: InMemoryTraceServer;
  const testProjectName = 'test-project';

  beforeEach(async () => {
    inMemoryTraceServer = new InMemoryTraceServer();
    initWithCustomTraceServer(testProjectName, inMemoryTraceServer);

    setTraceProcessors([]);
    agentsInstrumentedHolder.value = false;
    await weave.instrumentOpenAIAgents();
  });

  test('trace lifecycle creates and finishes call', async () => {
    withTrace('Agent Workflow', async () => {}, {
      traceId: 'test-trace-123',
      metadata: {},
    });

    const calls = await inMemoryTraceServer.getCalls(testProjectName);
    expect(calls).toHaveLength(1);
    expect(calls[0].op_name).toBe('openai_agent_trace');
    expect(calls[0].display_name).toBe('Agent Workflow');
    expect(calls[0].attributes).toMatchObject({
      kind: 'agent',
      agent_trace_id: 'test-trace-123',
    });
    expect(calls[0].ended_at).not.toBeNull();
  });

  test('maps span types to correct kinds', async () => {
    // Test key span types
    const spans = [
      {id: 'span-agent', expectedKind: 'agent'},
      {id: 'span-function', expectedKind: 'tool'},
      {id: 'span-guardrail', expectedKind: 'guardrail'},
    ];

    await withTrace('Test', async () => {
      await withAgentSpan(async () => {}, {
        spanId: spans[0].id,
        data: {
          name: 'test-agent',
          tools: [],
          handoffs: [],
          output_type: 'text',
        },
      });

      await withFunctionSpan(async () => {}, {
        spanId: spans[1].id,
        data: {name: 'test-function', input: '', output: ''},
      });

      await withGuardrailSpan(async () => {}, {
        spanId: spans[2].id,
        data: {name: 'test-guardrail', triggered: false},
      });
    });

    const calls = await inMemoryTraceServer.getCalls(testProjectName);

    for (const {id, expectedKind} of spans) {
      const call = calls.find(c => c.attributes?.agent_span_id === id);
      expect(call?.attributes?.kind).toBe(expectedKind);
    }
  });

  test('creates parent-child hierarchy', async () => {
    await withTrace('Workflow', async () => {
      await withAgentSpan(async () => {}, {spanId: 'span-123'});
    });

    const calls = await inMemoryTraceServer.getCalls(testProjectName);
    expect(calls).toHaveLength(2);

    const traceCall = calls.find(c => c.op_name === 'openai_agent_trace');
    const spanCall = calls.find(
      c => c.attributes?.agent_span_id === 'span-123'
    );

    expect(spanCall!.parent_id).toBe(traceCall!.id);
    expect(spanCall!.trace_id).toBe(traceCall!.trace_id);
  });

  test('agent run with tool call emits expected calls', async () => {
    const getWeather = tool({
      name: 'get_weather',
      description: 'Get the current weather for a given city.',
      parameters: z.object({city: z.string()}),
      execute: ({city}) => `${city}: Sunny, 22°C`,
    });

    const agent = new Agent({
      name: 'Assistant',
      instructions: 'You are a helpful assistant.',
      tools: [getWeather],
      model: new MockAgent([
        toolCall('get_weather', {city: 'Tokyo'}, 'call-tokyo'),
        assistantMessage('Tokyo is sunny.', 'msg-final'),
      ]),
    });

    const result = await run(agent, 'What is the weather in Tokyo?');
    expect(result.finalOutput).toBe('Tokyo is sunny.');

    const calls = await inMemoryTraceServer.getCalls(testProjectName);

    expect(calls).toHaveLength(3);

    expect(callData(calls[0])).toMatchInlineSnapshot(`
      {
        "attributes": {
          "kind": "agent",
        },
        "display_name": "Agent workflow",
        "inputs": {
          "name": "Agent workflow",
        },
        "op_name": "openai_agent_trace",
        "outputs": {
          "metadata": {},
          "metrics": {},
          "status": "completed",
        },
        "project_id": "test-project",
      }
    `);
    expect(callData(calls[1])).toMatchInlineSnapshot(`
      {
        "attributes": {
          "kind": "agent",
        },
        "display_name": "Assistant",
        "inputs": {
          "name": "Assistant",
        },
        "op_name": "openai_agent_agent",
        "outputs": {
          "error": null,
          "metadata": {
            "handoffs": [],
            "output_type": "text",
            "tools": [
              "get_weather",
            ],
          },
          "metrics": {},
          "output": null,
        },
        "project_id": "test-project",
      }
    `);
    expect(callData(calls[2])).toMatchInlineSnapshot(`
      {
        "attributes": {
          "kind": "tool",
        },
        "display_name": "get_weather",
        "inputs": {
          "name": "get_weather",
        },
        "op_name": "openai_agent_function",
        "outputs": {
          "error": null,
          "metadata": {},
          "metrics": {},
          "output": "Tokyo: Sunny, 22°C",
        },
        "project_id": "test-project",
      }
    `);

    // openai_agent_trace
    // ├── openai_agent_agent
    //     └── openai_agent_function
    expect(calls[1].parent_id).toBe(calls[0].id);
    expect(calls[2].parent_id).toBe(calls[1].id);

    for (const call of calls) {
      expect(call.trace_id).toBe(calls[0].trace_id);
    }
  });
});

describe('OpenAI Agents Integration (with WEAVE_USE_OTEL_V2=true)', () => {
  withEnv({WEAVE_USE_OTEL_V2: true, WANDB_API_KEY: 'test-api-key'});
  withOpenAITracingEnabled();

  let inMemoryTraceServer: InMemoryTraceServer;
  let exporter: InMemorySpanExporter;
  const testProjectName = 'test-project-otel';

  beforeEach(async () => {
    inMemoryTraceServer = new InMemoryTraceServer();
    exporter = new InMemorySpanExporter();

    initWithCustomTraceServer(
      testProjectName,
      inMemoryTraceServer,
      new Settings(true, {}, {spanProcessor: new SimpleSpanProcessor(exporter)})
    );

    clearWeaveTracerProvider();
    setTraceProcessors([]);
    agentsInstrumentedHolder.value = false;
    await weave.instrumentOpenAIAgents();
  });

  test('empty trace emits no OTel spans', async () => {
    await withTrace('Agent Workflow', async () => {}, {
      traceId: 'test-trace-123',
    });

    expect(await emittedSpans()).toHaveLength(0);
    expect(await inMemoryTraceServer.getCalls(testProjectName)).toHaveLength(0);
  });

  test('emits `invoke_agent` and `execute_tool` spans', async () => {
    await withTrace('Test', async () => {
      await withAgentSpan(async () => {}, {
        spanId: 'span-agent',
        data: {
          name: 'test-agent',
          tools: ['t1'],
          handoffs: ['h1'],
          output_type: 'text',
        },
      });
      await withFunctionSpan(async () => {}, {
        spanId: 'span-function',
        data: {
          name: 'test-function',
          input: '{"city":"Tokyo"}',
          output: 'sunny, 22C',
        },
      });
      await withGuardrailSpan(async () => {}, {
        spanId: 'span-guardrail',
        data: {name: 'test-guardrail', triggered: false},
      });
    });

    const spans = await emittedSpans();
    expect(spans).toHaveLength(3);

    const agent = spans.find(s => s.name === 'invoke_agent test-agent')!;
    expect(agent.attributes).toMatchObject({
      'gen_ai.operation.name': 'invoke_agent',
      'gen_ai.agent.name': 'test-agent',
      'gen_ai.provider.name': 'openai',
      'weave.openai_agents.agent.tools': ['t1'],
      'weave.openai_agents.agent.handoffs': ['h1'],
      'weave.openai_agents.agent.output_type': 'text',
      'weave.openai_agents.span_id': 'span-agent',
    });

    const executeToolSpan = spans.find(
      s => s.name === 'execute_tool test-function'
    )!;
    expect(executeToolSpan.attributes).toMatchObject({
      'gen_ai.operation.name': 'execute_tool',
      'gen_ai.tool.name': 'test-function',
      'gen_ai.tool.call.arguments': '{"city":"Tokyo"}',
      'gen_ai.tool.call.result': 'sunny, 22C',
      'weave.openai_agents.span_id': 'span-function',
    });
  });

  test('preserves parent-child relationship', async () => {
    await withTrace('Workflow', async () => {
      await withAgentSpan(
        async () => {
          await withFunctionSpan(async () => {}, {
            spanId: 'span-fn',
            data: {name: 'inner', input: '', output: ''},
          });
        },
        {
          spanId: 'span-agent',
          data: {
            name: 'test-agent',
            tools: [],
            handoffs: [],
            output_type: 'text',
          },
        }
      );
    });

    const spans = await emittedSpans();
    expect(spans).toHaveLength(2);

    const agent = spans.find(s => s.name === 'invoke_agent test-agent')!;
    const fn = findBySpanId(spans, 'span-fn')!;

    // Child OTel span points back at the agent OTel span via parentSpanId,
    // and they share the same traceId.
    expect(fn.parentSpanId).toBe(agent.spanContext().spanId);
    expect(fn.spanContext().traceId).toBe(agent.spanContext().traceId);
    expect(agent.parentSpanId).toBeUndefined();
  });

  test('agent run with tool call emits expected OTel spans', async () => {
    const getWeather = tool({
      name: 'get_weather',
      description: 'Get the current weather for a given city.',
      parameters: z.object({city: z.string()}),
      execute: ({city}) => `${city}: Sunny, 22°C`,
    });

    const agent = new Agent({
      name: 'Assistant',
      instructions: 'You are a helpful assistant.',
      tools: [getWeather],
      model: new MockAgent([
        toolCall('get_weather', {city: 'Tokyo'}, 'call-tokyo'),
        assistantMessage('Tokyo is sunny.', 'msg-final'),
      ]),
    });

    const result = await run(agent, 'What is the weather in Tokyo?');
    expect(result.finalOutput).toBe('Tokyo is sunny.');

    const spans = await emittedSpans();

    const agentSpan = spans.find(s => s.name === 'invoke_agent Assistant');
    expect(agentSpan).toBeDefined();
    expect(agentSpan!.attributes).toMatchObject({
      'gen_ai.operation.name': 'invoke_agent',
      'gen_ai.agent.name': 'Assistant',
      'gen_ai.provider.name': 'openai',
      'weave.openai_agents.agent.tools': ['get_weather'],
    });

    const executeToolSpan = spans.find(
      s => s.name === 'execute_tool get_weather'
    )!;
    expect(executeToolSpan).toBeDefined();
    expect(executeToolSpan.attributes).toMatchObject({
      'gen_ai.operation.name': 'execute_tool',
      'gen_ai.tool.name': 'get_weather',
      // The Agents SDK serializes the tool's JSON args/result as strings
      // on the FunctionSpanData, which we lift straight to semconv.
      'gen_ai.tool.call.arguments': '{"city":"Tokyo"}',
      'gen_ai.tool.call.result': 'Tokyo: Sunny, 22°C',
    });
    // Span is a child of the agent span.
    expect(executeToolSpan.parentSpanId).toBe(agentSpan!.spanContext().spanId);
    expect(executeToolSpan.spanContext().traceId).toBe(
      agentSpan!.spanContext().traceId
    );
  });

  async function emittedSpans(): Promise<ReadableSpan[]> {
    await weave.flushOTel();
    return exporter.getFinishedSpans();
  }

  function findBySpanId(
    spans: ReadableSpan[],
    spanId: string
  ): ReadableSpan | undefined {
    return spans.find(
      s => s.attributes['weave.openai_agents.span_id'] === spanId
    );
  }
});

/**
 * Returns canned responses in sequence.
 */
class MockAgent implements Model {
  private turn = 0;

  constructor(private readonly responses: ModelResponse[]) {}

  async getResponse(_req: ModelRequest): Promise<ModelResponse> {
    const response = this.responses[this.turn];
    if (!response) {
      throw new Error(`MockAgent: no response for turn ${this.turn}`);
    }
    this.turn += 1;
    return response;
  }

  getStreamedResponse(): AsyncIterable<never> {
    throw new Error('MockAgent.getStreamedResponse not implemented');
  }
}

function callData(call: Call) {
  return {
    project_id: call.project_id,
    op_name: call.op_name,
    display_name: call.display_name,
    attributes: {kind: call.attributes.kind},
    inputs: call.inputs,
    outputs: call.output,
  };
}

function assistantMessage(text: string, id = 'msg'): ModelResponse {
  return {
    output: [
      {
        id,
        type: 'message',
        role: 'assistant',
        status: 'completed',
        content: [{type: 'output_text', text}],
      },
    ],
    usage: new Usage({inputTokens: 3, outputTokens: 4, totalTokens: 7}),
    responseId: `resp-${id}`,
  };
}

function toolCall(
  name: string,
  args: Record<string, unknown>,
  callId = 'call-1'
): ModelResponse {
  return {
    output: [
      {
        id: `fcall-${callId}`,
        type: 'function_call',
        callId,
        name,
        status: 'completed',
        arguments: JSON.stringify(args),
      },
    ],
    usage: new Usage({inputTokens: 5, outputTokens: 6, totalTokens: 11}),
    responseId: `resp-${callId}`,
  };
}

function withOpenAITracingEnabled() {
  beforeEach(async () => {
    setTracingDisabled(false);
  });
  afterEach(() => {
    setTracingDisabled(true);
  });
}

function withEnv(vars: Record<string, string | boolean | undefined>) {
  const original: Record<string, string | undefined> = {};

  beforeEach(() => {
    for (const [key, value] of Object.entries(vars)) {
      original[key] = process.env[key];
      if (value === undefined) delete process.env[key];
      else process.env[key] = String(value);
    }
  });

  afterEach(() => {
    for (const key of Object.keys(vars)) {
      if (original[key] === undefined) delete process.env[key];
      else process.env[key] = original[key];
    }
  });
}
