/**
 * Tests for the Google ADK (`@google/adk`) integration.
 *
 * The main tests run the real ADK runner (InMemoryRunner + a scripted
 * BaseLlm, no network) so they exercise ADK's actual plugin dispatch — this
 * matters because the integration depends on which callbacks ADK invokes
 * (e.g. ADK 1.2.0 never dispatches plugin agent callbacks). Edge cases that
 * are hard to reach through the runner (streaming partials, synthetic tool
 * keys, dangling-span cleanup) drive the plugin callbacks directly.
 *
 * Spans are captured with an `InMemorySpanExporter` injected through
 * `settings.genai.spanProcessor`, exactly how a user-supplied processor
 * plugs into the Weave tracer provider that otherwise exports to the
 * agents endpoint (`/agents/otel/v1/traces`).
 *
 * Note: @google/adk's CJS build does `require("lodash-es")` (an ESM-only
 * package). Node >= 22 allows that via require(esm), but jest's module
 * runtime does not, so the default jest project maps `lodash-es` to its
 * API-identical CJS twin `lodash` (declared as a devDependency). This is a
 * test-only resolution shim — the weave SDK itself does not use lodash.
 */
import {
  InMemorySpanExporter,
  type ReadableSpan,
  SimpleSpanProcessor,
} from '@opentelemetry/sdk-trace-base';

import * as weave from '../..';
import {clearWeaveTracerProvider} from '../../genai/provider';
import {WeaveAdkPlugin} from '../../integrations/googleAdk';
import {commonPatchGoogleGenAI} from '../../integrations/googleGenAI';
import {Settings} from '../../settings';
import {initWithCustomTraceServer} from '../clientMock';
import {InMemoryTraceServer} from '../helpers/inMemoryTraceServer';

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

const TEST_PROJECT = 'test-project';
const TEST_MODEL = 'gemini-test';

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
  } as LlmResponse;
}

function functionCallResponse(
  toolName: string,
  args: Record<string, unknown>,
  usage?: {prompt: number; completion: number}
): LlmResponse {
  return {
    content: {
      role: 'model',
      parts: [{functionCall: {id: 'fc-1', name: toolName, args}}],
    },
    ...(usage
      ? {
          usageMetadata: {
            promptTokenCount: usage.prompt,
            candidatesTokenCount: usage.completion,
            totalTokenCount: usage.prompt + usage.completion,
          },
        }
      : {}),
  } as LlmResponse;
}

function userMessage(text: string) {
  return {role: 'user', parts: [{text}]};
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
    initWithCustomTraceServer(
      TEST_PROJECT,
      traceServer,
      new Settings(true, {}, {spanProcessor: new SimpleSpanProcessor(exporter)})
    );
    // Drop any provider built by a previous test so the next span pulls a
    // fresh provider wired to this test's exporter.
    clearWeaveTracerProvider();
  });

  describe('with the real ADK runner', () => {
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

      const root = invokeAgentSpans.find(span => !span.parentSpanId);
      const agentSpan = invokeAgentSpans.find(span => span.parentSpanId);
      const [toolSpan] = toolSpans;
      expect(root).toBeDefined();
      expect(agentSpan).toBeDefined();

      // Every span shares the root's OTel trace and the session id.
      for (const span of spans) {
        expect(span.spanContext().traceId).toBe(root!.spanContext().traceId);
        expect(span.attributes['gen_ai.conversation.id']).toBe(session.id);
        expect(span.attributes['gen_ai.provider.name']).toBe('gemini');
      }

      // Structure: root invoke_agent → invoke_agent → (chat, chat, tool).
      expect(root!.name).toBe('invoke_agent weather_agent');
      expect(agentSpan!.parentSpanId).toBe(spanId(root!));
      expect(agentSpan!.attributes['gen_ai.agent.name']).toBe('weather_agent');
      for (const span of [...chatSpans, ...toolSpans]) {
        expect(span.parentSpanId).toBe(spanId(agentSpan!));
      }

      // Root carries the user message in and the final answer out.
      expect(root!.attributes['gen_ai.input.messages']).toContain(
        'What is the weather in Paris?'
      );
      expect(root!.attributes['gen_ai.output.messages']).toContain(
        'It is sunny in Paris.'
      );

      // Chat spans carry request/response messages and token usage.
      const firstChat = chatSpans.find(span =>
        String(span.attributes['gen_ai.output.messages']).includes('tool_call')
      );
      const secondChat = chatSpans.find(span =>
        String(span.attributes['gen_ai.output.messages']).includes(
          'It is sunny in Paris.'
        )
      );
      expect(firstChat).toBeDefined();
      expect(secondChat).toBeDefined();
      expect(firstChat!.name).toBe(`chat ${TEST_MODEL}`);
      expect(firstChat!.attributes['gen_ai.request.model']).toBe(TEST_MODEL);
      expect(firstChat!.attributes['gen_ai.input.messages']).toContain(
        'What is the weather in Paris?'
      );
      expect(firstChat!.attributes['gen_ai.usage.input_tokens']).toBe(10);
      expect(firstChat!.attributes['gen_ai.usage.output_tokens']).toBe(5);
      expect(firstChat!.attributes['gen_ai.usage.total_tokens']).toBe(15);
      expect(secondChat!.attributes['gen_ai.usage.input_tokens']).toBe(20);
      expect(secondChat!.attributes['gen_ai.usage.output_tokens']).toBe(8);

      // Tool span records its name, call id, args and result.
      expect(toolSpan.name).toBe('execute_tool get_weather');
      expect(toolSpan.attributes['gen_ai.tool.name']).toBe('get_weather');
      expect(toolSpan.attributes['gen_ai.tool.call.id']).toBe('fc-1');
      expect(toolSpan.attributes['gen_ai.tool.call.arguments']).toContain(
        'Paris'
      );
      expect(toolSpan.attributes['gen_ai.tool.call.result']).toContain('sunny');
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

      const root = invokeAgentSpans.find(span => !span.parentSpanId);
      const byAgent = (name: string) =>
        invokeAgentSpans.find(
          span =>
            span.parentSpanId && span.attributes['gen_ai.agent.name'] === name
        );
      const pipelineSpan = byAgent('pipeline');
      const firstSpan = byAgent('first_agent');
      const secondSpan = byAgent('second_agent');
      expect(root).toBeDefined();
      expect(pipelineSpan).toBeDefined();
      expect(firstSpan).toBeDefined();
      expect(secondSpan).toBeDefined();

      expect(pipelineSpan!.parentSpanId).toBe(spanId(root!));
      expect(firstSpan!.parentSpanId).toBe(spanId(pipelineSpan!));
      expect(secondSpan!.parentSpanId).toBe(spanId(pipelineSpan!));

      expect(chatSpans).toHaveLength(2);
      const chatParents = chatSpans.map(span => span.parentSpanId).sort();
      expect(chatParents).toEqual(
        [spanId(firstSpan!), spanId(secondSpan!)].sort()
      );
    });

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
      const root = byOperation(spans, 'invoke_agent').find(
        span => !span.parentSpanId
      );

      expect(chatSpans).toHaveLength(1);
      expect(chatSpans[0].status.code).toBe(2); // SpanStatusCode.ERROR
      expect(chatSpans[0].status.message).toContain('model exploded');
      expect(root).toBeDefined();
      expect(root!.status.code).toBe(2); // SpanStatusCode.ERROR
      expect(root!.status.message).toContain('model exploded');
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
      expect(chatSpan).toBeDefined();
      expect(chatSpan.status.code).not.toBe(2); // SpanStatusCode.ERROR
      expect(
        chatSpan.attributes['weave.google_adk.interrupted']
      ).toBeUndefined();
      expect(chatSpan.attributes['gen_ai.output.messages']).toContain(
        'served from cache'
      );
    });
  });

  describe('plugin callback edge cases', () => {
    const INVOCATION_ID = 'inv-1';

    function invocationContext(overrides: Record<string, unknown> = {}) {
      return {
        invocationId: INVOCATION_ID,
        agent: {name: 'agent_a', description: 'test agent'},
        session: {id: 'sess-1', appName: 'app', userId: 'user-1'},
        userContent: userMessage('hello'),
        ...overrides,
      } as any;
    }

    function callbackContext(agentName = 'agent_a') {
      return {invocationId: INVOCATION_ID, agentName} as any;
    }

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
        },
      });
      await plugin.afterModelCallback({
        callbackContext: callbackContext(),
        llmResponse: {content: {role: 'model', parts: [{text: 'hello'}]}},
      });
      await plugin.afterRunCallback({invocationContext: invocationContext()});
      const [chat] = byOperation(exporter.getFinishedSpans(), 'chat');
      return chat;
    }

    test('streaming: partial responses do not close the chat span', async () => {
      const plugin = new WeaveAdkPlugin();
      await plugin.beforeRunCallback({
        invocationContext: invocationContext(),
      });
      await plugin.beforeModelCallback({
        callbackContext: callbackContext(),
        llmRequest: {model: TEST_MODEL, contents: []},
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
      expect(chatSpans[0].attributes['gen_ai.output.messages']).toContain(
        'It is sunny.'
      );
      expect(chatSpans[0].attributes['gen_ai.usage.total_tokens']).toBe(7);
    });

    test('tool errors record span errors; the late afterToolCallback is ignored', async () => {
      const plugin = new WeaveAdkPlugin();
      const tool = {name: 'fails', description: 'always fails'};
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
      expect(toolSpans[0].status.code).toBe(2); // SpanStatusCode.ERROR
      expect(toolSpans[0].status.message).toContain('tool failed');
      expect(
        toolSpans[0].attributes['gen_ai.tool.call.result']
      ).toBeUndefined();
    });

    test('agents outside the agent tree nest under the innermost open tool span', async () => {
      const plugin = new WeaveAdkPlugin();
      const tool = {name: 'agent_tool', description: 'wraps an agent'};
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
        llmRequest: {model: TEST_MODEL, contents: []},
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
      const outsideAgent = byOperation(spans, 'invoke_agent').find(
        span => span.attributes['gen_ai.agent.name'] === 'outside_agent'
      );
      expect(outsideAgent).toBeDefined();
      expect(outsideAgent!.parentSpanId).toBe(spanId(toolSpan));
    });

    test('afterRun ends dangling spans and marks them interrupted', async () => {
      const plugin = new WeaveAdkPlugin();
      await plugin.beforeRunCallback({
        invocationContext: invocationContext(),
      });
      await plugin.beforeModelCallback({
        callbackContext: callbackContext(),
        llmRequest: {model: TEST_MODEL, contents: []},
      });
      // No afterModelCallback — simulates an aborted run.
      await plugin.afterRunCallback({invocationContext: invocationContext()});

      const spans = exporter.getFinishedSpans();
      const chatSpans = byOperation(spans, 'chat');
      expect(chatSpans).toHaveLength(1);
      expect(chatSpans[0].attributes['weave.google_adk.interrupted']).toBe(
        true
      );
      // Every started span was ended (it would not be finished otherwise).
      expect(byOperation(spans, 'invoke_agent').length).toBeGreaterThan(0);
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

    test('message content stays off spans when ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS=false', async () => {
      const previous = process.env.ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS;
      process.env.ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS = 'false';
      try {
        const plugin = new WeaveAdkPlugin();
        await plugin.beforeRunCallback({
          invocationContext: invocationContext(),
        });
        await plugin.beforeModelCallback({
          callbackContext: callbackContext(),
          llmRequest: {
            model: TEST_MODEL,
            contents: [{role: 'user', parts: [{text: 'secret'}]}],
          },
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
        expect(chatSpans[0].attributes['gen_ai.request.model']).toBe(
          TEST_MODEL
        );
      } finally {
        if (previous === undefined) {
          delete process.env.ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS;
        } else {
          process.env.ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS = previous;
        }
      }
    });

    test('callbacks are safe without an initialized weave client', async () => {
      const {setGlobalClient} = require('../../clientApi');
      setGlobalClient(null);
      try {
        const plugin = new WeaveAdkPlugin();
        await expect(
          plugin.beforeRunCallback({invocationContext: invocationContext()})
        ).resolves.toBeUndefined();
        await expect(
          plugin.beforeModelCallback({
            callbackContext: callbackContext(),
            llmRequest: {model: TEST_MODEL},
          })
        ).resolves.toBeUndefined();
        await expect(
          plugin.afterRunCallback({invocationContext: invocationContext()})
        ).resolves.toBeUndefined();
        expect(exporter.getFinishedSpans()).toHaveLength(0);
      } finally {
        initWithCustomTraceServer(TEST_PROJECT, traceServer);
      }
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
          expect(chat.attributes['gen_ai.provider.name']).toBe(expected);
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
              expect(chat.attributes['gen_ai.output.messages']).toContain(
                'hello'
              );
            } else {
              expect(chat.attributes['gen_ai.output.messages']).toBeUndefined();
            }
          }
        );
      }
    );

    test('tool results with cycles and bigints are sanitized, not dropped', async () => {
      const plugin = new WeaveAdkPlugin();
      const tool = {
        name: 'cyclic_tool',
        description: 'returns a self-referential object',
      };
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
      const resultAttr = String(toolSpan.attributes['gen_ai.tool.call.result']);
      expect(resultAttr).toContain('"count":"42"'); // bigint stringified
      expect(resultAttr).toContain('"label":"ok"');
      expect(resultAttr).toContain('[Circular]'); // cycle replaced
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
