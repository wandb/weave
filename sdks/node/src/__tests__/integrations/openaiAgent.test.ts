import {
  Agent,
  run,
  Runner,
  setTraceProcessors,
  setTracingDisabled,
  tool,
  Usage,
  withAgentSpan,
  withCustomSpan,
  withFunctionSpan,
  withGenerationSpan,
  withGuardrailSpan,
  withHandoffSpan,
  withMCPListToolsSpan,
  withResponseSpan,
  withSpeechGroupSpan,
  withSpeechSpan,
  withTrace,
  withTranscriptionSpan,
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
import {initWithCustomTraceServer} from '../clientMock';
import {wrapOpenAIChatCompletionsCreate} from '../../integrations/openai';
import {makeAPIPromiseShim} from '../openaiMock';
import {InMemoryTraceServer, type Call} from '../helpers/inMemoryTraceServer';
import state from 'weave/state';
import {packageVersion} from 'weave/utils/packageVersion';

describe('OpenAI Agents Integration', () => {
  withEnv({WEAVE_USE_OTEL_V2: false});
  withOpenAITracingEnabled();

  let inMemoryTraceServer: InMemoryTraceServer;
  const testProjectName = 'test-project';

  beforeEach(async () => {
    inMemoryTraceServer = new InMemoryTraceServer();
    initWithCustomTraceServer(testProjectName, inMemoryTraceServer);

    setTraceProcessors([]);
    state.integrations.openaiAgents.instrumented = false;
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
      const call = calls.find(c => c.attributes.agent_span_id === id);
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
    const spanCall = calls.find(c => c.attributes.agent_span_id === 'span-123');

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

    // calls_complete writes each call when it closes, so the root trace lands
    // last; assert by op_name rather than by write order.
    const traceCall = calls.find(c => c.op_name === 'openai_agent_trace')!;
    const agentCall = calls.find(c => c.op_name === 'openai_agent_agent')!;
    const funcCall = calls.find(c => c.op_name === 'openai_agent_function')!;

    expect(callData(traceCall)).toMatchInlineSnapshot(`
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
    expect(callData(agentCall)).toMatchInlineSnapshot(`
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
    expect(callData(funcCall)).toMatchInlineSnapshot(`
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

    // Integration-tracking metadata is stamped on calls this processor
    // produces. The trace also contains nested OpenAI SDK calls with their
    // own integration block, so match by name rather than by index.
    const stamped = calls.map(c => c.attributes.integration).filter(Boolean);
    const mine = stamped.filter(i => i.name === 'openai_agents');
    expect(mine.length).toBeGreaterThan(0);
    expect(mine.every(i => i.meta?.package_name === '@openai/agents')).toBe(
      true
    );

    // openai_agent_trace
    // ├── openai_agent_agent
    //     └── openai_agent_function
    expect(agentCall.parent_id).toBe(traceCall.id);
    expect(funcCall.parent_id).toBe(agentCall.id);

    for (const call of calls) {
      expect(call.trace_id).toBe(traceCall.trace_id);
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

    initWithCustomTraceServer(testProjectName, inMemoryTraceServer, {
      genai: {spanProcessor: new SimpleSpanProcessor(exporter)},
    });

    clearWeaveTracerProvider();
    setTraceProcessors([]);
    state.integrations.openaiAgents.instrumented = false;
    await weave.instrumentOpenAIAgents();
  });

  test('empty trace emits no OTel spans', async () => {
    await withTrace('Agent Workflow', async () => {}, {
      traceId: 'test-trace-123',
    });

    expect(await emittedSpans()).toHaveLength(0);
    expect(await inMemoryTraceServer.getCalls(testProjectName)).toHaveLength(0);
  });

  test('starting and ending OpenaAI spans (via `with*`) emit `invoke_agent`, `execute_tool`, `chat`, `handoff`, `guardrail`, `transcription`, `speech`, `speech_group`, `mcp_list_tools` and custom OTel spans', async () => {
    await withTrace(
      'Test',
      async () => {
        await withAgentSpan(
          async () => {
            await withFunctionSpan(async () => {}, {
              spanId: 'span-function',
              data: {
                name: 'test-function',
                input: '{"city":"Tokyo"}',
                output: 'sunny, 22C',
              },
            });
            await withResponseSpan(async span => {
              span.spanData._input = [
                {role: 'user', content: 'What is the weather in Tokyo?'},
              ];
              span.spanData._response = {
                object: 'response',
                id: 'resp-abc',
                model: 'gpt-4o-mini',
                status: 'completed',
                usage: {
                  input_tokens: 12,
                  output_tokens: 7,
                  input_tokens_details: {cached_tokens: 4},
                  output_tokens_details: {reasoning_tokens: 3},
                },
                output: [
                  {
                    type: 'reasoning',
                    summary: [
                      {text: 'Tokyo is a city in Japan.'},
                      {text: 'Sunny.'},
                    ],
                  },
                  {
                    type: 'function_call',
                    callId: 'call-1',
                    name: 'get_weather',
                    arguments: '{"city":"Tokyo"}',
                  },
                  {
                    type: 'function_call_output',
                    callId: 'call-1',
                    output: 'Tokyo: Sunny, 22C',
                  },
                  {
                    type: 'message',
                    role: 'assistant',
                    content: [{type: 'output_text', text: 'Tokyo is sunny.'}],
                  },
                ],
              };
            });
            await withGenerationSpan(async () => {}, {
              data: {
                model: 'gpt-3.5-turbo',
                usage: {
                  input_tokens: 9,
                  output_tokens: 4,
                  details: {
                    cached_tokens: 2,
                    reasoning_tokens: 1,
                  },
                },
                input: [{role: 'user', content: 'hi'}],
                output: [{role: 'assistant', content: 'hello'}],
                model_config: {
                  temperature: 0.7,
                  top_p: 0.9,
                  max_tokens: 200,
                  frequency_penalty: 0.1,
                  presence_penalty: 0.2,
                  seed: 42,
                  stop: 'STOP',
                  n: 3,
                  unknown_key: 'ignored',
                },
              },
            });
            await withGuardrailSpan(async () => {}, {
              spanId: 'span-guardrail',
              data: {name: 'test-guardrail', triggered: false},
            });
            await withHandoffSpan(async () => {}, {
              spanId: 'span-handoff',
              data: {from_agent: 'Triage', to_agent: 'Specialist'},
            });
            await withTranscriptionSpan(async () => {}, {
              spanId: 'span-transcription',
              data: {
                input: {data: 'base64audio', format: 'pcm'},
                output: 'hello world',
                model: 'whisper-1',
              },
            });
            await withSpeechSpan(async () => {}, {
              spanId: 'span-speech',
              data: {
                input: 'say hello',
                output: {data: 'base64audio', format: 'pcm'},
                model: 'tts-1',
              },
            });
            await withSpeechGroupSpan(async () => {}, {
              spanId: 'span-speech-group',
              data: {input: 'narration script'},
            });
            await withMCPListToolsSpan(async () => {}, {
              spanId: 'span-mcp',
              data: {
                server: 'http://localhost:9000',
                result: ['search', 'fetch'],
              },
            });
            await withCustomSpan(async () => {}, {
              spanId: 'span-custom',
              data: {
                name: 'my_step',
                // Each non-null key in `data` becomes its own
                // weave.openai_agents.custom.<key> attribute; null is dropped.
                data: {kind: 'cache_lookup', hits: 3, miss: null},
              },
            });
          },
          {
            spanId: 'span-agent',
            data: {
              name: 'test-agent',
              tools: ['t1'],
              handoffs: ['h1'],
              output_type: 'text',
            },
          }
        );
      },
      {groupId: 'some-conversation-id'}
    );

    const spans = await emittedSpans();
    expect(spans).toHaveLength(11);

    const agent = spans.find(s => s.name === 'invoke_agent test-agent')!;
    expect(agent.attributes).toMatchObject({
      'gen_ai.operation.name': 'invoke_agent',
      'gen_ai.agent.name': 'test-agent',
      'gen_ai.conversation.id': 'some-conversation-id',
      'gen_ai.provider.name': 'openai',
      'weave.openai_agents.agent.tools': ['t1'],
      'weave.openai_agents.agent.handoffs': ['h1'],
      'weave.openai_agents.agent.output_type': 'text',
      'weave.openai_agents.span_id': 'span-agent',
      'integration.meta.package_name': '@openai/agents',
      'integration.name': 'openai_agents',
      'integration.version': packageVersion,
    });

    const executeToolSpan = spans.find(
      s => s.name === 'execute_tool test-function'
    )!;
    expect(executeToolSpan.attributes).toMatchObject({
      'gen_ai.operation.name': 'execute_tool',
      'gen_ai.agent.name': 'test-agent',
      'gen_ai.conversation.id': 'some-conversation-id',
      'gen_ai.tool.name': 'test-function',
      'gen_ai.tool.call.arguments': '{"city":"Tokyo"}',
      'gen_ai.tool.call.result': 'sunny, 22C',
      'weave.openai_agents.span_id': 'span-function',
      'integration.meta.package_name': '@openai/agents',
      'integration.name': 'openai_agents',
      'integration.version': packageVersion,
    });

    const resp = spans.find(s => s.name === 'chat gpt-4o-mini')!;
    expect(resp.attributes).toMatchObject({
      'gen_ai.operation.name': 'chat',
      'gen_ai.agent.name': 'test-agent',
      'gen_ai.conversation.id': 'some-conversation-id',
      'gen_ai.provider.name': 'openai',
      'gen_ai.output.type': 'text',
      'gen_ai.request.model': 'gpt-4o-mini',
      'gen_ai.response.model': 'gpt-4o-mini',
      'gen_ai.response.id': 'resp-abc',
      'gen_ai.usage.input_tokens': 12,
      'gen_ai.usage.output_tokens': 7,
      'gen_ai.usage.cache_read.input_tokens': 4,
      'gen_ai.usage.reasoning.output_tokens': 3,
      'integration.meta.package_name': '@openai/agents',
      'integration.name': 'openai_agents',
      'integration.version': packageVersion,
    });
    expect(resp.attributes['gen_ai.input.messages']).toMatchInlineSnapshot(
      `"[{"role":"user","parts":[{"type":"text","content":"What is the weather in Tokyo?"}]}]"`
    );
    expect(resp.attributes['gen_ai.output.messages']).toMatchInlineSnapshot(
      `"[{"role":"assistant","parts":[{"type":"tool_call","toolName":"get_weather","arguments":"{\\"city\\":\\"Tokyo\\"}"}]},{"role":"tool","parts":[{"type":"tool_result","result":"Tokyo: Sunny, 22C"}]},{"role":"assistant","parts":[{"type":"reasoning","content":"Tokyo is a city in Japan.\\nSunny."},{"type":"text","content":"Tokyo is sunny."}]}]"`
    );

    const gen = spans.find(s => s.name === 'chat gpt-3.5-turbo')!;
    expect(gen.attributes).toMatchObject({
      'gen_ai.operation.name': 'chat',
      'gen_ai.agent.name': 'test-agent',
      'gen_ai.conversation.id': 'some-conversation-id',
      'gen_ai.provider.name': 'openai',
      'gen_ai.output.type': 'text',
      'gen_ai.request.model': 'gpt-3.5-turbo',
      'gen_ai.usage.input_tokens': 9,
      'gen_ai.usage.output_tokens': 4,
      'gen_ai.usage.cache_read.input_tokens': 2,
      'gen_ai.usage.reasoning.output_tokens': 1,
      'gen_ai.request.temperature': 0.7,
      'gen_ai.request.top_p': 0.9,
      'gen_ai.request.max_tokens': 200,
      'gen_ai.request.frequency_penalty': 0.1,
      'gen_ai.request.presence_penalty': 0.2,
      'gen_ai.request.seed': 42,
      'gen_ai.request.stop_sequences': ['STOP'],
      'gen_ai.request.choice.count': 3,
      'integration.meta.package_name': '@openai/agents',
      'integration.name': 'openai_agents',
      'integration.version': packageVersion,
    });
    expect(gen.attributes['gen_ai.input.messages']).toMatchInlineSnapshot(
      `"[{"role":"user","parts":[{"type":"text","content":"hi"}]}]"`
    );
    expect(gen.attributes['gen_ai.output.messages']).toMatchInlineSnapshot(
      `"[{"role":"assistant","parts":[{"type":"text","content":"hello"}]}]"`
    );
    expect(gen.attributes['gen_ai.response.id']).toBeUndefined();

    const handoff = spans.find(s => s.name === 'handoff Triage -> Specialist')!;
    expect(handoff.attributes).toMatchObject({
      'gen_ai.agent.name': 'test-agent',
      'gen_ai.conversation.id': 'some-conversation-id',
      'weave.openai_agents.handoff.from_agent': 'Triage',
      'weave.openai_agents.handoff.to_agent': 'Specialist',
      'weave.openai_agents.span_id': 'span-handoff',
      'integration.meta.package_name': '@openai/agents',
      'integration.name': 'openai_agents',
      'integration.version': packageVersion,
    });
    expect(handoff.attributes['gen_ai.operation.name']).toBeUndefined();

    const guard = spans.find(s => s.name === 'guardrail test-guardrail')!;
    expect(guard.attributes).toMatchObject({
      'gen_ai.agent.name': 'test-agent',
      'gen_ai.conversation.id': 'some-conversation-id',
      'weave.openai_agents.guardrail.name': 'test-guardrail',
      'weave.openai_agents.guardrail.triggered': false,
      'weave.openai_agents.span_id': 'span-guardrail',
      'integration.meta.package_name': '@openai/agents',
      'integration.name': 'openai_agents',
      'integration.version': packageVersion,
    });
    expect(guard.attributes['gen_ai.operation.name']).toBeUndefined();

    const transcription = spans.find(s => s.name === 'transcription')!;
    expect(transcription.attributes).toMatchObject({
      'gen_ai.agent.name': 'test-agent',
      'gen_ai.conversation.id': 'some-conversation-id',
      'weave.openai_agents.transcription.model': 'whisper-1',
      'weave.openai_agents.transcription.input': 'base64audio',
      'weave.openai_agents.transcription.input_format': 'pcm',
      'weave.openai_agents.transcription.output': 'hello world',
      'weave.openai_agents.span_id': 'span-transcription',
      'integration.meta.package_name': '@openai/agents',
      'integration.name': 'openai_agents',
      'integration.version': packageVersion,
    });
    expect(transcription.attributes['gen_ai.operation.name']).toBeUndefined();

    const speech = spans.find(s => s.name === 'speech')!;
    expect(speech.attributes).toMatchObject({
      'gen_ai.agent.name': 'test-agent',
      'gen_ai.conversation.id': 'some-conversation-id',
      'weave.openai_agents.speech.model': 'tts-1',
      'weave.openai_agents.speech.input': 'say hello',
      'weave.openai_agents.speech.output': 'base64audio',
      'weave.openai_agents.speech.output_format': 'pcm',
      'weave.openai_agents.span_id': 'span-speech',
      'integration.meta.package_name': '@openai/agents',
      'integration.name': 'openai_agents',
      'integration.version': packageVersion,
    });
    expect(speech.attributes['gen_ai.operation.name']).toBeUndefined();

    const speechGroup = spans.find(s => s.name === 'speech_group')!;
    expect(speechGroup.attributes).toMatchObject({
      'gen_ai.agent.name': 'test-agent',
      'gen_ai.conversation.id': 'some-conversation-id',
      'weave.openai_agents.speech_group.input': 'narration script',
      'weave.openai_agents.span_id': 'span-speech-group',
      'integration.meta.package_name': '@openai/agents',
      'integration.name': 'openai_agents',
      'integration.version': packageVersion,
    });
    expect(speechGroup.attributes['gen_ai.operation.name']).toBeUndefined();

    const mcp = spans.find(s => s.name === 'mcp_list_tools')!;
    expect(mcp.attributes).toMatchObject({
      'gen_ai.agent.name': 'test-agent',
      'gen_ai.conversation.id': 'some-conversation-id',
      'weave.openai_agents.mcp.server': 'http://localhost:9000',
      'weave.openai_agents.mcp.result': ['search', 'fetch'],
      'weave.openai_agents.span_id': 'span-mcp',
      'integration.meta.package_name': '@openai/agents',
      'integration.name': 'openai_agents',
      'integration.version': packageVersion,
    });
    expect(mcp.attributes['gen_ai.operation.name']).toBeUndefined();

    // CustomSpan uses the user-supplied name with no prefix.
    const custom = spans.find(s => s.name === 'my_step')!;
    expect(custom.attributes).toMatchObject({
      'gen_ai.agent.name': 'test-agent',
      'gen_ai.conversation.id': 'some-conversation-id',
      'weave.openai_agents.custom.kind': 'cache_lookup',
      'weave.openai_agents.custom.hits': 3,
      'weave.openai_agents.span_id': 'span-custom',
      'integration.meta.package_name': '@openai/agents',
      'integration.name': 'openai_agents',
      'integration.version': packageVersion,
    });
    // Null values dropped — `miss: null` doesn't produce an attribute.
    expect(
      custom.attributes['weave.openai_agents.custom.miss']
    ).toBeUndefined();
    expect(custom.attributes['gen_ai.operation.name']).toBeUndefined();
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

    const runner = new Runner({groupId: 'some-conversation-id'});
    const result = await runner.run(agent, 'What is the weather in Tokyo?');
    expect(result.finalOutput).toBe('Tokyo is sunny.');

    const spans = await emittedSpans();

    const agentSpan = spans.find(s => s.name === 'invoke_agent Assistant');
    expect(agentSpan).toBeDefined();
    expect(agentSpan!.attributes).toMatchObject({
      'gen_ai.operation.name': 'invoke_agent',
      'gen_ai.agent.name': 'Assistant',
      'gen_ai.conversation.id': 'some-conversation-id',
      'gen_ai.provider.name': 'openai',
      'weave.openai_agents.agent.tools': ['get_weather'],
      'integration.meta.package_name': '@openai/agents',
      'integration.name': 'openai_agents',
      'integration.version': packageVersion,
    });

    const executeToolSpan = spans.find(
      s => s.name === 'execute_tool get_weather'
    )!;
    expect(executeToolSpan).toBeDefined();
    expect(executeToolSpan.attributes).toMatchObject({
      'gen_ai.operation.name': 'execute_tool',
      'gen_ai.agent.name': 'Assistant',
      'gen_ai.conversation.id': 'some-conversation-id',
      'gen_ai.tool.name': 'get_weather',
      // The Agents SDK serializes the tool's JSON args/result as strings
      // on the FunctionSpanData, which we lift straight to semconv.
      'gen_ai.tool.call.arguments': '{"city":"Tokyo"}',
      'gen_ai.tool.call.result': 'Tokyo: Sunny, 22°C',
      'integration.meta.package_name': '@openai/agents',
      'integration.name': 'openai_agents',
      'integration.version': packageVersion,
    });
    // Span is a child of the agent span.
    expect(executeToolSpan.parentSpanId).toBe(agentSpan!.spanContext().spanId);
    expect(executeToolSpan.spanContext().traceId).toBe(
      agentSpan!.spanContext().traceId
    );
  });

  test('OpenAI SDK calls inside an agent context are not double-traced', async () => {
    // Under OTel V2 the agents OTel processor already emits a `chat` span
    // for every model call (with messages + usage). The OpenAI integration's
    // own Weave call would duplicate that record, so it should bypass when
    // an agents trace is active.
    const mockResponse = {
      id: 'resp-1',
      object: 'chat.completion',
      model: 'gpt-4o-mini',
      choices: [{index: 0, message: {role: 'assistant', content: 'hi'}}],
      usage: {prompt_tokens: 1, completion_tokens: 1, total_tokens: 2},
    };
    const mockCreate = jest.fn(() => makeAPIPromiseShim(mockResponse));
    const wrapped = wrapOpenAIChatCompletionsCreate(
      mockCreate as any,
      'openai.chat.completions.create'
    );

    await withTrace('Workflow', async () => {
      await wrapped({
        model: 'gpt-4o-mini',
        messages: [{role: 'user', content: 'hi'}],
      });
    });

    expect(mockCreate).toHaveBeenCalledTimes(1);

    // Wait for any fire-and-forget finishCall — if suppression failed and
    // a call WAS created, we want to see it.
    await new Promise(resolve => setTimeout(resolve, 300));
    const calls = await inMemoryTraceServer.getCalls(testProjectName);
    expect(
      calls.find(c => c.op_name === 'openai.chat.completions.create')
    ).toBeUndefined();
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
