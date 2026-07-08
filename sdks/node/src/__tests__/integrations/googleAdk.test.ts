/**
 * Tests for the Google ADK (`@google/adk`) integration. The WeaveAdkPlugin
 * mirrors ADK's lifecycle callbacks into GenAI-semconv OTel spans on Weave's
 * agents endpoint.
 *
 * The plugin is exercised through the real ADK runner (InMemoryRunner + a
 * scripted BaseLlm, no network) and through direct callback calls for cases
 * that are hard to reach through the runner. Spans are captured with an
 * `InMemorySpanExporter` injected through `settings.genai.spanProcessor`,
 * exactly how a user-supplied processor plugs into the Weave tracer provider.
 */
import {
  InMemorySpanExporter,
  type ReadableSpan,
  SimpleSpanProcessor,
} from '@opentelemetry/sdk-trace-base';
import {
  BaseLlm,
  FunctionTool,
  InMemoryRunner,
  LlmAgent,
  SequentialAgent,
  type LlmRequest,
  type LlmResponse,
} from '@google/adk';
import {z} from 'zod';

import {setGlobalClient} from '../../clientApi';
import {clearWeaveTracerProvider} from '../../genai/provider';
import {
  commonPatchGoogleADK,
  WeaveAdkPlugin,
} from '../../integrations/googleAdk';
import {commonPatchGoogleGenAI} from '../../integrations/googleGenAI';
import {initWithCustomTraceServer} from '../clientMock';
import {InMemoryTraceServer} from '../helpers/inMemoryTraceServer';

const TEST_PROJECT = 'test-project';
const TEST_MODEL = 'gemini-test';
const INVOCATION_ID = 'inv-1';

/** A BaseLlm that replays a per-call script of responses. */
class ScriptedLlm extends BaseLlm {
  private callIndex = 0;

  constructor(
    model: string,
    private readonly script: LlmResponse[][]
  ) {
    super({model});
  }

  async *generateContentAsync(
    _llmRequest: LlmRequest,
    _stream?: boolean
  ): AsyncGenerator<LlmResponse, void> {
    const responses =
      this.script[Math.min(this.callIndex, this.script.length - 1)];
    this.callIndex++;
    for (const response of responses) {
      yield response;
    }
  }

  async connect(): Promise<never> {
    throw new Error('live connections are not supported in tests');
  }
}

function userMessage(text: string) {
  return {role: 'user', parts: [{text}]};
}

function textResponse(
  text: string,
  usage?: {prompt: number; completion: number}
): LlmResponse {
  return {
    content: {role: 'model', parts: [{text}]},
    turnComplete: true,
    ...(usage
      ? {
          usageMetadata: {
            promptTokenCount: usage.prompt,
            candidatesTokenCount: usage.completion,
            totalTokenCount: usage.prompt + usage.completion,
          },
        }
      : {}),
  };
}

function functionCallResponse(
  toolName: string,
  args: Record<string, unknown>,
  usage: {prompt: number; completion: number}
): LlmResponse {
  return {
    content: {
      role: 'model',
      parts: [{functionCall: {id: 'fc-1', name: toolName, args}}],
    },
    usageMetadata: {
      promptTokenCount: usage.prompt,
      candidatesTokenCount: usage.completion,
      totalTokenCount: usage.prompt + usage.completion,
    },
  };
}

async function runToCompletion(
  runner: InMemoryRunner,
  params: {userId: string; sessionId: string; newMessage: any}
) {
  const events = [];
  for await (const event of runner.runAsync(params)) {
    events.push(event);
  }
  return events;
}

function byOperation(spans: ReadableSpan[], operation: string): ReadableSpan[] {
  return spans.filter(
    span => span.attributes['gen_ai.operation.name'] === operation
  );
}

/** Narrows `span` to non-undefined, throwing (failing the test) if missing. */
function requireSpan(span: ReadableSpan | undefined): ReadableSpan {
  if (!span) {
    throw new Error('expected span to be defined');
  }
  return span;
}

function spanId(span: ReadableSpan): string {
  return span.spanContext().spanId;
}

/**
 * Sets an env var for the duration of `fn`, then restores it. The plugin
 * reads these env vars live at span-build time, so this is how the env-var
 * contracts get exercised through real span output.
 */
async function withEnv(
  name: string,
  value: string | undefined,
  fn: () => Promise<void>
): Promise<void> {
  const previous = process.env[name];
  if (value === undefined) {
    delete process.env[name];
  } else {
    process.env[name] = value;
  }
  try {
    await fn();
  } finally {
    if (previous === undefined) {
      delete process.env[name];
    } else {
      process.env[name] = previous;
    }
  }
}

describe('Google ADK integration', () => {
  let traceServer: InMemoryTraceServer;
  let exporter: InMemorySpanExporter;

  beforeEach(() => {
    traceServer = new InMemoryTraceServer();
    exporter = new InMemorySpanExporter();
    initWithCustomTraceServer(TEST_PROJECT, traceServer, {
      printCallLink: true,
      attributes: {},
      genai: {spanProcessor: new SimpleSpanProcessor(exporter)},
    });
    // Drop any provider built by a previous test so the next span pulls a
    // fresh provider wired to this test's exporter.
    clearWeaveTracerProvider();
  });

  function invocationContext(overrides: Record<string, unknown> = {}) {
    // A real ADK agent always exposes `subAgents` (its constructor defaults
    // the field to `[]`) and a `findAgent` method; mirror both so agent-tree
    // lookup exercises its real path instead of the cyclic-tree fallback.
    const agent = {
      name: 'agent_a',
      description: 'test agent',
      subAgents: [],
      findAgent: (name: string) => (name === 'agent_a' ? agent : undefined),
    };
    return {
      invocationId: INVOCATION_ID,
      agent,
      session: {id: 'sess-1', appName: 'app', userId: 'user-1'},
      userContent: userMessage('hello'),
      ...overrides,
    } as any;
  }

  function callbackContext(agentName = 'agent_a') {
    return {invocationId: INVOCATION_ID, agentName} as any;
  }

  describe('run spans', () => {
    test('traces an agent run with its input and output messages', async () => {
      const plugin = new WeaveAdkPlugin();
      await plugin.beforeRunCallback({
        invocationContext: invocationContext({
          userContent: userMessage('What is the weather in Paris?'),
        }),
      });
      await plugin.onEventCallback({
        invocationContext: invocationContext(),
        event: {
          content: {role: 'model', parts: [{text: 'It is sunny in Paris.'}]},
        } as any,
      });
      await plugin.afterRunCallback({invocationContext: invocationContext()});

      const [root] = byOperation(exporter.getFinishedSpans(), 'invoke_agent');
      expect(root).toBeDefined();
      expect(root.parentSpanContext?.spanId).toBeUndefined();
      expect(root.name).toBe('invoke_agent agent_a');
      expect(root.attributes).toMatchObject({
        'gen_ai.operation.name': 'invoke_agent',
        'gen_ai.agent.name': 'agent_a',
        'gen_ai.provider.name': 'gemini',
        'gen_ai.conversation.id': 'sess-1',
        'gen_ai.input.messages': expect.stringContaining(
          'What is the weather in Paris?'
        ),
        'gen_ai.output.messages': expect.stringContaining(
          'It is sunny in Paris.'
        ),
      });
    });

    test('explicit plugin is safe with the real ADK runner', async () => {
      const agent = new LlmAgent({
        name: 'runner_agent',
        description: 'runs through ADK',
        model: new ScriptedLlm(TEST_MODEL, [[textResponse('hello from ADK')]]),
      });
      const runner = new InMemoryRunner({
        agent,
        appName: 'weave-adk-test',
        plugins: [new WeaveAdkPlugin()],
      });
      const session = await runner.sessionService.createSession({
        appName: 'weave-adk-test',
        userId: 'user-1',
      });

      await runToCompletion(runner, {
        userId: 'user-1',
        sessionId: session.id,
        newMessage: userMessage('hello'),
      });

      const root = requireSpan(
        byOperation(exporter.getFinishedSpans(), 'invoke_agent').find(
          span => !span.parentSpanContext?.spanId
        )
      );
      expect(root.name).toBe('invoke_agent runner_agent');
      expect(root.attributes).toMatchObject({
        'gen_ai.agent.name': 'runner_agent',
        'gen_ai.input.messages': expect.stringContaining('hello'),
        'gen_ai.output.messages': expect.stringContaining('hello from ADK'),
      });
    });

    test('records an event error on the root span', async () => {
      const plugin = new WeaveAdkPlugin();
      await plugin.beforeRunCallback({invocationContext: invocationContext()});
      await plugin.onEventCallback({
        invocationContext: invocationContext(),
        event: {errorCode: 'BOOM', errorMessage: 'it broke'} as any,
      });
      await plugin.afterRunCallback({invocationContext: invocationContext()});

      const [root] = byOperation(exporter.getFinishedSpans(), 'invoke_agent');
      expect(root.status).toMatchObject({
        code: 2, // SpanStatusCode.ERROR
        message: expect.stringContaining('it broke'),
      });
    });

    test('completed invocations unregister their beforeExit cleanup', async () => {
      const beforeCount = process.listenerCount('beforeExit');

      for (let i = 0; i < 12; i++) {
        const plugin = new WeaveAdkPlugin();
        const ctx = invocationContext({invocationId: `listener-${i}`});
        await plugin.beforeRunCallback({invocationContext: ctx});
        await plugin.afterRunCallback({invocationContext: ctx});
      }

      // The Weave tracer provider may register one process-level flush hook,
      // but completed plugin instances should not add one listener each.
      expect(
        process.listenerCount('beforeExit') - beforeCount
      ).toBeLessThanOrEqual(1);
    });

    test('callbacks are safe without an initialized weave client', async () => {
      setGlobalClient(null);
      try {
        const plugin = new WeaveAdkPlugin();
        await expect(
          plugin.beforeRunCallback({invocationContext: invocationContext()})
        ).resolves.toBeUndefined();
        await expect(
          plugin.afterRunCallback({invocationContext: invocationContext()})
        ).resolves.toBeUndefined();
        expect(exporter.getFinishedSpans()).toHaveLength(0);
      } finally {
        initWithCustomTraceServer(TEST_PROJECT, traceServer);
      }
    });
  });

  describe('model / chat spans', () => {
    // Drives one model turn through the plugin callbacks and returns the
    // resulting chat span, so env-driven attributes (provider name, content
    // capture) can be asserted on real span output.
    async function runOneChat(): Promise<ReadableSpan> {
      const plugin = new WeaveAdkPlugin();
      await plugin.beforeRunCallback({invocationContext: invocationContext()});
      await plugin.beforeModelCallback({
        callbackContext: callbackContext(),
        llmRequest: {
          model: TEST_MODEL,
          contents: [{role: 'user', parts: [{text: 'hi'}]}],
        } as any,
      });
      await plugin.afterModelCallback({
        callbackContext: callbackContext(),
        llmResponse: {content: {role: 'model', parts: [{text: 'hello'}]}},
      });
      await plugin.afterRunCallback({invocationContext: invocationContext()});
      const [chat] = byOperation(exporter.getFinishedSpans(), 'chat');
      return chat;
    }

    test('records model errors as span errors and still closes the run', async () => {
      class ExplodingLlm extends BaseLlm {
        // eslint-disable-next-line require-yield -- deliberately throws before yielding
        async *generateContentAsync(): AsyncGenerator<LlmResponse, void> {
          throw new Error('model exploded');
        }
        async connect(): Promise<never> {
          throw new Error('not supported');
        }
      }

      const agent = new LlmAgent({
        name: 'fragile_agent',
        description: 'fails',
        model: new ExplodingLlm({model: TEST_MODEL}),
      });
      const runner = new InMemoryRunner({
        agent,
        appName: 'weave-adk-test',
        plugins: [new WeaveAdkPlugin()],
      });
      const session = await runner.sessionService.createSession({
        appName: 'weave-adk-test',
        userId: 'user-1',
      });

      await runToCompletion(runner, {
        userId: 'user-1',
        sessionId: session.id,
        newMessage: userMessage('boom'),
      });

      const spans = exporter.getFinishedSpans();
      const chatSpans = byOperation(spans, 'chat');
      const root = requireSpan(
        byOperation(spans, 'invoke_agent').find(span => !span.parentSpanContext?.spanId)
      );

      expect(chatSpans).toHaveLength(1);
      // 2 = SpanStatusCode.ERROR
      expect(chatSpans[0].status).toMatchObject({
        code: 2,
        message: expect.stringContaining('model exploded'),
      });
      expect(root.status).toMatchObject({
        code: 2,
        message: expect.stringContaining('model exploded'),
      });
    });

    test('closes chat spans when beforeModelCallback returns a cached response', async () => {
      class FailIfCalledLlm extends BaseLlm {
        // eslint-disable-next-line require-yield -- this test fails if ADK calls the model
        async *generateContentAsync(): AsyncGenerator<LlmResponse, void> {
          throw new Error('model should have been skipped');
        }
        async connect(): Promise<never> {
          throw new Error('not supported');
        }
      }

      const agent = new LlmAgent({
        name: 'cached_agent',
        description: 'serves cached responses',
        model: new FailIfCalledLlm({model: TEST_MODEL}),
        beforeModelCallback: () =>
          textResponse('served from cache', {prompt: 1, completion: 1}),
      });
      const runner = new InMemoryRunner({
        agent,
        appName: 'weave-adk-test',
        plugins: [new WeaveAdkPlugin()],
      });
      const session = await runner.sessionService.createSession({
        appName: 'weave-adk-test',
        userId: 'user-1',
      });

      await runToCompletion(runner, {
        userId: 'user-1',
        sessionId: session.id,
        newMessage: userMessage('use the cache'),
      });

      const [chatSpan] = byOperation(exporter.getFinishedSpans(), 'chat');
      expect(chatSpan).toMatchObject({
        status: {code: 0}, // SpanStatusCode.UNSET — closed normally, not errored
        attributes: {
          'gen_ai.output.messages':
            expect.stringContaining('served from cache'),
        },
      });
      expect(
        chatSpan.attributes['weave.google_adk.interrupted']
      ).toBeUndefined();
    });

    test('streaming: partial responses do not close the chat span', async () => {
      const plugin = new WeaveAdkPlugin();
      await plugin.beforeRunCallback({
        invocationContext: invocationContext(),
      });
      await plugin.beforeModelCallback({
        callbackContext: callbackContext(),
        llmRequest: {model: TEST_MODEL, contents: []} as any,
      });
      await plugin.afterModelCallback({
        callbackContext: callbackContext(),
        llmResponse: {
          partial: true,
          content: {role: 'model', parts: [{text: 'It is'}]},
        },
      });
      await plugin.afterModelCallback({
        callbackContext: callbackContext(),
        llmResponse: {
          content: {role: 'model', parts: [{text: 'It is sunny.'}]},
          usageMetadata: {
            promptTokenCount: 3,
            candidatesTokenCount: 4,
            totalTokenCount: 7,
          },
        },
      });
      await plugin.afterRunCallback({invocationContext: invocationContext()});

      const chatSpans = byOperation(exporter.getFinishedSpans(), 'chat');
      expect(chatSpans).toHaveLength(1);
      expect(chatSpans[0].attributes).toMatchObject({
        'gen_ai.output.messages': expect.stringContaining('It is sunny.'),
        'gen_ai.usage.total_tokens': 7,
      });
    });

    test('afterRun ends dangling spans and marks them interrupted', async () => {
      const plugin = new WeaveAdkPlugin();
      await plugin.beforeRunCallback({
        invocationContext: invocationContext(),
      });
      await plugin.beforeModelCallback({
        callbackContext: callbackContext(),
        llmRequest: {model: TEST_MODEL, contents: []} as any,
      });
      // No afterModelCallback — simulates an aborted run.
      await plugin.afterRunCallback({invocationContext: invocationContext()});

      const spans = exporter.getFinishedSpans();
      const chatSpans = byOperation(spans, 'chat');
      expect(chatSpans).toHaveLength(1);
      expect(chatSpans[0].attributes).toMatchObject({
        'weave.google_adk.interrupted': true,
      });
      // Every started span was ended (it would not be finished otherwise).
      expect(byOperation(spans, 'invoke_agent').length).toBeGreaterThan(0);
    });

    test('message content stays off spans when ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS=false', async () => {
      await withEnv(
        'ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS',
        'false',
        async () => {
          const plugin = new WeaveAdkPlugin();
          await plugin.beforeRunCallback({
            invocationContext: invocationContext(),
          });
          await plugin.beforeModelCallback({
            callbackContext: callbackContext(),
            llmRequest: {
              model: TEST_MODEL,
              contents: [{role: 'user', parts: [{text: 'secret'}]}],
            } as any,
          });
          await plugin.afterModelCallback({
            callbackContext: callbackContext(),
            llmResponse: {content: {role: 'model', parts: [{text: 'hush'}]}},
          });
          await plugin.afterRunCallback({
            invocationContext: invocationContext(),
          });

          const spans = exporter.getFinishedSpans();
          for (const span of spans) {
            expect(span.attributes['gen_ai.input.messages']).toBeUndefined();
            expect(span.attributes['gen_ai.output.messages']).toBeUndefined();
          }
          // Non-content attributes still flow.
          const chatSpans = byOperation(spans, 'chat');
          expect(chatSpans[0].attributes).toMatchObject({
            'gen_ai.request.model': TEST_MODEL,
          });
        }
      );
    });

    // provider.name must track how google-genai itself resolves the env var,
    // including that "1" is NOT vertex (its stringToBoolean accepts only
    // "true"), so the span reports the backend actually used.
    const providerCases: Array<[string, string | undefined, string]> = [
      ['unset', undefined, 'gemini'],
      ['true', 'true', 'vertex_ai'],
      ['TRUE', 'TRUE', 'vertex_ai'],
      ['1', '1', 'gemini'],
      ['false', 'false', 'gemini'],
    ];
    test.each(providerCases)(
      'provider.name follows google-genai for GOOGLE_GENAI_USE_VERTEXAI=%s',
      async (_label, value, expected) => {
        await withEnv('GOOGLE_GENAI_USE_VERTEXAI', value, async () => {
          const chat = await runOneChat();
          expect(chat.attributes).toMatchObject({
            'gen_ai.provider.name': expected,
          });
        });
      }
    );

    // Content capture must match ADK's own gate: case-sensitive "true"/"1",
    // and unset/empty defaults to capturing.
    const captureCases: Array<[string, string, boolean]> = [
      ['1', '1', true],
      ['empty', '', true],
      ['false', 'false', false],
    ];
    test.each(captureCases)(
      'content capture follows ADK for ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS=%s',
      async (_label, value, shouldCapture) => {
        await withEnv(
          'ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS',
          value,
          async () => {
            const chat = await runOneChat();
            if (shouldCapture) {
              expect(chat.attributes).toMatchObject({
                'gen_ai.output.messages': expect.stringContaining('hello'),
              });
            } else {
              expect(chat.attributes['gen_ai.output.messages']).toBeUndefined();
            }
          }
        );
      }
    );
  });

  describe('tool spans', () => {
    test('traces a single-agent tool-using run end to end', async () => {
      const getWeather = new FunctionTool({
        name: 'get_weather',
        description: 'Returns the weather for a city.',
        parameters: z.object({city: z.string()}),
        execute: async ({city}: {city: string}) => ({
          city,
          weather: 'sunny',
        }),
      });

      const model = new ScriptedLlm(TEST_MODEL, [
        [
          functionCallResponse(
            'get_weather',
            {city: 'Paris'},
            {prompt: 10, completion: 5}
          ),
        ],
        [textResponse('It is sunny in Paris.', {prompt: 20, completion: 8})],
      ]);

      const agent = new LlmAgent({
        name: 'weather_agent',
        description: 'Answers weather questions.',
        model,
        tools: [getWeather],
      });

      const runner = new InMemoryRunner({
        agent,
        appName: 'weave-adk-test',
        plugins: [new WeaveAdkPlugin()],
      });
      const session = await runner.sessionService.createSession({
        appName: 'weave-adk-test',
        userId: 'user-1',
      });

      await runToCompletion(runner, {
        userId: 'user-1',
        sessionId: session.id,
        newMessage: userMessage('What is the weather in Paris?'),
      });

      const spans = exporter.getFinishedSpans();
      const invokeAgentSpans = byOperation(spans, 'invoke_agent');
      const chatSpans = byOperation(spans, 'chat');
      const toolSpans = byOperation(spans, 'execute_tool');

      // Root invocation + the synthesized per-agent span.
      expect(invokeAgentSpans).toHaveLength(2);
      expect(chatSpans).toHaveLength(2);
      expect(toolSpans).toHaveLength(1);

      const root = requireSpan(
        invokeAgentSpans.find(span => !span.parentSpanContext?.spanId)
      );
      const agentSpan = requireSpan(
        invokeAgentSpans.find(span => span.parentSpanContext?.spanId)
      );
      const [toolSpan] = toolSpans;

      // Every span shares the root's OTel trace and the session id.
      for (const span of spans) {
        expect(span.spanContext().traceId).toBe(root.spanContext().traceId);
        expect(span.attributes).toMatchObject({
          'gen_ai.conversation.id': session.id,
          'gen_ai.provider.name': 'gemini',
        });
      }

      // Structure: root invoke_agent → invoke_agent → (chat, chat, tool).
      expect(root.name).toBe('invoke_agent weather_agent');
      expect(agentSpan.parentSpanContext?.spanId).toBe(spanId(root));
      expect(agentSpan.attributes).toMatchObject({
        'gen_ai.agent.name': 'weather_agent',
      });
      for (const span of [...chatSpans, ...toolSpans]) {
        expect(span.parentSpanContext?.spanId).toBe(spanId(agentSpan));
      }

      // Root carries the user message in and the final answer out.
      expect(root.attributes).toMatchObject({
        'gen_ai.input.messages': expect.stringContaining(
          'What is the weather in Paris?'
        ),
        'gen_ai.output.messages': expect.stringContaining(
          'It is sunny in Paris.'
        ),
      });

      // Chat spans carry request/response messages and token usage.
      const firstChat = requireSpan(
        chatSpans.find(span =>
          String(span.attributes['gen_ai.output.messages']).includes(
            'tool_call'
          )
        )
      );
      const secondChat = requireSpan(
        chatSpans.find(span =>
          String(span.attributes['gen_ai.output.messages']).includes(
            'It is sunny in Paris.'
          )
        )
      );
      expect(firstChat.name).toBe(`chat ${TEST_MODEL}`);
      expect(firstChat.attributes).toMatchObject({
        'gen_ai.request.model': TEST_MODEL,
        'gen_ai.input.messages': expect.stringContaining(
          'What is the weather in Paris?'
        ),
        'gen_ai.usage.input_tokens': 10,
        'gen_ai.usage.output_tokens': 5,
        'gen_ai.usage.total_tokens': 15,
      });
      expect(secondChat.attributes).toMatchObject({
        'gen_ai.usage.input_tokens': 20,
        'gen_ai.usage.output_tokens': 8,
      });

      // Tool span records its name, call id, args and result.
      expect(toolSpan.name).toBe('execute_tool get_weather');
      expect(toolSpan.attributes).toMatchObject({
        'gen_ai.tool.name': 'get_weather',
        'gen_ai.tool.call.id': 'fc-1',
        'gen_ai.tool.call.arguments': expect.stringContaining('Paris'),
        'gen_ai.tool.call.result': expect.stringContaining('sunny'),
      });
    });

    test('nests sub-agents under workflow agents', async () => {
      const first = new LlmAgent({
        name: 'first_agent',
        description: 'first',
        model: new ScriptedLlm(TEST_MODEL, [[textResponse('first done')]]),
      });
      const second = new LlmAgent({
        name: 'second_agent',
        description: 'second',
        model: new ScriptedLlm(TEST_MODEL, [[textResponse('second done')]]),
      });
      const pipeline = new SequentialAgent({
        name: 'pipeline',
        description: 'runs both agents',
        subAgents: [first, second],
      });

      const runner = new InMemoryRunner({
        agent: pipeline,
        appName: 'weave-adk-test',
        plugins: [new WeaveAdkPlugin()],
      });
      const session = await runner.sessionService.createSession({
        appName: 'weave-adk-test',
        userId: 'user-1',
      });

      await runToCompletion(runner, {
        userId: 'user-1',
        sessionId: session.id,
        newMessage: userMessage('go'),
      });

      const spans = exporter.getFinishedSpans();
      const invokeAgentSpans = byOperation(spans, 'invoke_agent');
      const chatSpans = byOperation(spans, 'chat');

      const root = requireSpan(
        invokeAgentSpans.find(span => !span.parentSpanContext?.spanId)
      );
      const byAgent = (name: string) =>
        requireSpan(
          invokeAgentSpans.find(
            span =>
              span.parentSpanContext?.spanId && span.attributes['gen_ai.agent.name'] === name
          )
        );
      const pipelineSpan = byAgent('pipeline');
      const firstSpan = byAgent('first_agent');
      const secondSpan = byAgent('second_agent');

      expect(pipelineSpan.parentSpanContext?.spanId).toBe(spanId(root));
      expect(firstSpan.parentSpanContext?.spanId).toBe(spanId(pipelineSpan));
      expect(secondSpan.parentSpanContext?.spanId).toBe(spanId(pipelineSpan));

      expect(chatSpans).toHaveLength(2);
      const chatParents = chatSpans.map(span => span.parentSpanContext?.spanId).sort();
      expect(chatParents).toEqual(
        [spanId(firstSpan), spanId(secondSpan)].sort()
      );
    });

    test('agents outside the agent tree nest under the innermost open tool span', async () => {
      const plugin = new WeaveAdkPlugin();
      const tool = {name: 'agent_tool', description: 'wraps an agent'} as any;
      const toolContext = {
        invocationId: INVOCATION_ID,
        agentName: 'agent_a',
        functionCallId: 'fc-2',
      } as any;

      await plugin.beforeRunCallback({
        invocationContext: invocationContext(),
      });
      await plugin.beforeToolCallback({tool, toolArgs: {}, toolContext});
      // An AgentTool-wrapped agent is not in the root agent's tree.
      await plugin.beforeModelCallback({
        callbackContext: callbackContext('outside_agent'),
        llmRequest: {model: TEST_MODEL, contents: []} as any,
      });
      await plugin.afterModelCallback({
        callbackContext: callbackContext('outside_agent'),
        llmResponse: {content: {role: 'model', parts: [{text: 'ok'}]}},
      });
      await plugin.afterToolCallback({
        tool,
        toolArgs: {},
        toolContext,
        result: {ok: true},
      });
      await plugin.afterRunCallback({invocationContext: invocationContext()});

      const spans = exporter.getFinishedSpans();
      const toolSpan = byOperation(spans, 'execute_tool')[0];
      const outsideAgent = requireSpan(
        byOperation(spans, 'invoke_agent').find(
          span => span.attributes['gen_ai.agent.name'] === 'outside_agent'
        )
      );
      expect(outsideAgent.parentSpanContext?.spanId).toBe(spanId(toolSpan));
    });

    test('tool errors record span errors; the late afterToolCallback is ignored', async () => {
      const plugin = new WeaveAdkPlugin();
      const tool = {name: 'fails', description: 'always fails'} as any;
      const toolContext = {
        invocationId: INVOCATION_ID,
        agentName: 'agent_a',
        functionCallId: 'fc-9',
      } as any;

      await plugin.beforeRunCallback({
        invocationContext: invocationContext(),
      });
      await plugin.beforeToolCallback({tool, toolArgs: {x: 1}, toolContext});
      await plugin.onToolErrorCallback({
        tool,
        toolArgs: {x: 1},
        toolContext,
        error: new Error('tool failed'),
      });
      // ADK invokes afterToolCallback even after a tool error.
      await plugin.afterToolCallback({
        tool,
        toolArgs: {x: 1},
        toolContext,
        result: null,
      });
      await plugin.afterRunCallback({invocationContext: invocationContext()});

      const toolSpans = byOperation(
        exporter.getFinishedSpans(),
        'execute_tool'
      );
      expect(toolSpans).toHaveLength(1);
      // 2 = SpanStatusCode.ERROR
      expect(toolSpans[0].status).toMatchObject({
        code: 2,
        message: expect.stringContaining('tool failed'),
      });
      expect(
        toolSpans[0].attributes['gen_ai.tool.call.result']
      ).toBeUndefined();
    });

    test('tool results with cycles and bigints are sanitized, not dropped', async () => {
      const plugin = new WeaveAdkPlugin();
      const tool = {
        name: 'cyclic_tool',
        description: 'returns a self-referential object',
      } as any;
      const toolContext = {
        invocationId: INVOCATION_ID,
        agentName: 'agent_a',
        functionCallId: 'fc-1',
      } as any;

      const result: Record<string, unknown> = {count: BigInt(42), label: 'ok'};
      result.self = result; // cycle — JSON.stringify would otherwise throw

      await plugin.beforeRunCallback({invocationContext: invocationContext()});
      await plugin.beforeToolCallback({tool, toolArgs: {}, toolContext});
      await plugin.afterToolCallback({tool, toolArgs: {}, toolContext, result});
      await plugin.afterRunCallback({invocationContext: invocationContext()});

      const [toolSpan] = byOperation(
        exporter.getFinishedSpans(),
        'execute_tool'
      );
      // bigint stringified to its digits; the cycle replaced with [Circular].
      const parsed = JSON.parse(
        String(toolSpan.attributes['gen_ai.tool.call.result'])
      );
      expect(parsed).toEqual({count: '42', label: 'ok', self: '[Circular]'});
    });

    test('auto-registers the plugin when the module hook has run', async () => {
      // Jest's module registry bypasses Module.prototype.require, so the
      // CJS loader hook never fires here; apply the hook function directly.
      // The real loader path is covered by host-app/e2e runs.
      // eslint-disable-next-line @typescript-eslint/no-require-imports -- pass the required CJS module to the hook, mirroring the real loader
      commonPatchGoogleADK(require('@google/adk'));

      const agent = new LlmAgent({
        name: 'auto_agent',
        description: 'auto instrumented',
        model: new ScriptedLlm(TEST_MODEL, [[textResponse('hello')]]),
      });
      // No plugins passed — the patched Runner.prototype.runAsync
      // self-registers the shared Weave plugin.
      const runner = new InMemoryRunner({agent, appName: 'weave-adk-test'});
      const session = await runner.sessionService.createSession({
        appName: 'weave-adk-test',
        userId: 'user-1',
      });

      await runToCompletion(runner, {
        userId: 'user-1',
        sessionId: session.id,
        newMessage: userMessage('hi'),
      });

      expect(runner.pluginManager.getPlugin('weave')).toBeDefined();

      const spans = exporter.getFinishedSpans();
      expect(byOperation(spans, 'invoke_agent').length).toBeGreaterThan(0);
      expect(byOperation(spans, 'chat')).toHaveLength(1);
    });

    test('auto-instrument finalizes the run when the consumer breaks early', async () => {
      // ADK only dispatches afterRunCallback after the event loop drains
      // normally. A consumer that breaks out of runAsync abandons the
      // generator, so without the wrapper's finally the root span never ends
      // and the invocation state leaks. The patched Runner must finalize it.
      // eslint-disable-next-line @typescript-eslint/no-require-imports -- pass the required CJS module to the hook, mirroring the real loader
      commonPatchGoogleADK(require('@google/adk'));

      const agent = new LlmAgent({
        name: 'early_break_agent',
        description: 'consumer stops early',
        model: new ScriptedLlm(TEST_MODEL, [[textResponse('partial answer')]]),
      });
      const runner = new InMemoryRunner({agent, appName: 'weave-adk-test'});
      const session = await runner.sessionService.createSession({
        appName: 'weave-adk-test',
        userId: 'user-1',
      });

      for await (const _event of runner.runAsync({
        userId: 'user-1',
        sessionId: session.id,
        newMessage: userMessage('hi'),
      })) {
        void _event;
        break; // abandon the generator mid-stream
      }

      const roots = byOperation(
        exporter.getFinishedSpans(),
        'invoke_agent'
      ).filter(span => !span.parentSpanContext?.spanId);
      // The run-root span was ended (and thus exported) despite the early
      // break — the invocation did not leak.
      expect(roots).toHaveLength(1);
      expect(roots[0].attributes).toMatchObject({
        'weave.google_adk.interrupted': true,
      });
    });
  });

  describe('google genai client exclusion', () => {
    function fakeGenAIExports() {
      class FakeModels {
        async generateContent(..._args: any[]) {
          return {text: 'ok'};
        }
        async generateContentStream(..._args: any[]) {
          return (async function* () {})();
        }
      }
      class FakeGoogleGenAI {
        models: any;
        constructor(public readonly options: any) {
          this.models = new FakeModels();
        }
      }
      return {GoogleGenAI: FakeGoogleGenAI};
    }

    test('ADK-internal clients (x-goog-api-client: google-adk/…) are not wrapped', () => {
      const exports = commonPatchGoogleGenAI(fakeGenAIExports());
      const adkClient = new exports.GoogleGenAI({
        apiKey: 'k',
        httpOptions: {
          headers: {
            'x-goog-api-client': 'google-adk/1.2.0 gl-typescript/v24.0.0',
            'user-agent': 'google-adk/1.2.0 gl-typescript/v24.0.0',
          },
        },
      });
      // Unwrapped: plain models object, no weave op replacement.
      expect(adkClient.models.generateContent.name).toBe('generateContent');

      const userClient = new exports.GoogleGenAI({apiKey: 'k'});
      // Wrapped: generateContent is replaced by a weave op.
      expect(userClient.models.generateContent.name).not.toBe(
        'generateContent'
      );
    });
  });
});
