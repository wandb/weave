/**
 * Tests for the run- and model-lifecycle tracing of the Google ADK
 * (`@google/adk`) integration. The plugin's run callbacks emit the root
 * `invoke_agent` span and its model callbacks emit nested `chat` spans, both
 * carrying the GenAI semantic conventions and exported to Weave's agents
 * endpoint.
 *
 * Run-only edge cases drive the plugin callbacks directly; model behaviour is
 * exercised both through the real ADK runner (InMemoryRunner + a scripted
 * BaseLlm, no network) and through direct callback calls for cases that are
 * hard to reach through the runner (streaming partials, dangling-span
 * cleanup). Spans are captured with an `InMemorySpanExporter` injected through
 * `settings.genai.spanProcessor`, exactly how a user-supplied processor plugs
 * into the Weave tracer provider.
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

import {clearWeaveTracerProvider} from '../../genai/provider';
import {
  ATTR_GEN_AI_AGENT_NAME,
  ATTR_GEN_AI_CONVERSATION_ID,
  ATTR_GEN_AI_INPUT_MESSAGES,
  ATTR_GEN_AI_OPERATION_NAME,
  ATTR_GEN_AI_OUTPUT_MESSAGES,
  ATTR_GEN_AI_PROVIDER_NAME,
  ATTR_GEN_AI_REQUEST_MODEL,
  ATTR_GEN_AI_TOOL_CALL_ARGUMENTS,
  ATTR_GEN_AI_TOOL_CALL_ID,
  ATTR_GEN_AI_TOOL_CALL_RESULT,
  ATTR_GEN_AI_TOOL_NAME,
  ATTR_GEN_AI_USAGE_INPUT_TOKENS,
  ATTR_GEN_AI_USAGE_OUTPUT_TOKENS,
  ATTR_GEN_AI_USAGE_TOTAL_TOKENS,
} from '../../genai/semconv';
import {WeaveAdkPlugin} from '../../integrations/googleAdk';
import {commonPatchGoogleGenAI} from '../../integrations/googleGenAI';
import {initWithCustomTraceServer} from '../clientMock';
import {InMemoryTraceServer} from '../helpers/inMemoryTraceServer';

import {
  BaseLlm,
  FunctionTool,
  InMemoryRunner,
  LlmAgent,
  type LlmRequest,
  type LlmResponse,
} from '@google/adk';
import {z} from 'zod';

const TEST_PROJECT = 'test-project';
const TEST_MODEL = 'gemini-test';
const INVOCATION_ID = 'inv-1';

function userMessage(text: string) {
  return {role: 'user', parts: [{text}]};
}

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
    span => span.attributes[ATTR_GEN_AI_OPERATION_NAME] === operation
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
        },
      });
      await plugin.afterRunCallback({invocationContext: invocationContext()});

      const [root] = byOperation(exporter.getFinishedSpans(), 'invoke_agent');
      expect(root).toBeDefined();
      expect(root.parentSpanId).toBeUndefined();
      expect(root.name).toBe('invoke_agent agent_a');
      expect(root.attributes).toMatchObject({
        [ATTR_GEN_AI_OPERATION_NAME]: 'invoke_agent',
        [ATTR_GEN_AI_AGENT_NAME]: 'agent_a',
        [ATTR_GEN_AI_PROVIDER_NAME]: 'gemini',
        [ATTR_GEN_AI_CONVERSATION_ID]: 'sess-1',
        [ATTR_GEN_AI_INPUT_MESSAGES]: expect.stringContaining(
          'What is the weather in Paris?'
        ),
        [ATTR_GEN_AI_OUTPUT_MESSAGES]: expect.stringContaining(
          'It is sunny in Paris.'
        ),
      });
    });

    test('records an event error on the root span', async () => {
      const plugin = new WeaveAdkPlugin();
      await plugin.beforeRunCallback({invocationContext: invocationContext()});
      await plugin.onEventCallback({
        invocationContext: invocationContext(),
        event: {errorCode: 'BOOM', errorMessage: 'it broke'},
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
      const {setGlobalClient} = require('../../clientApi');
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
      // 2 = SpanStatusCode.ERROR
      expect(chatSpans[0].status).toMatchObject({
        code: 2,
        message: expect.stringContaining('model exploded'),
      });
      expect(root).toBeDefined();
      expect(root!.status).toMatchObject({
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
      expect(chatSpan).toBeDefined();
      expect(chatSpan.status.code).not.toBe(2); // SpanStatusCode.ERROR
      expect(
        chatSpan.attributes['weave.google_adk.interrupted']
      ).toBeUndefined();
      expect(chatSpan.attributes[ATTR_GEN_AI_OUTPUT_MESSAGES]).toContain(
        'served from cache'
      );
    });

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
      expect(chatSpans[0].attributes).toMatchObject({
        [ATTR_GEN_AI_OUTPUT_MESSAGES]: expect.stringContaining('It is sunny.'),
        [ATTR_GEN_AI_USAGE_TOTAL_TOKENS]: 7,
      });
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
            expect(span.attributes[ATTR_GEN_AI_INPUT_MESSAGES]).toBeUndefined();
            expect(
              span.attributes[ATTR_GEN_AI_OUTPUT_MESSAGES]
            ).toBeUndefined();
          }
          // Non-content attributes still flow.
          const chatSpans = byOperation(spans, 'chat');
          expect(chatSpans[0].attributes[ATTR_GEN_AI_REQUEST_MODEL]).toBe(
            TEST_MODEL
          );
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
          expect(chat.attributes[ATTR_GEN_AI_PROVIDER_NAME]).toBe(expected);
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
              expect(chat.attributes[ATTR_GEN_AI_OUTPUT_MESSAGES]).toContain(
                'hello'
              );
            } else {
              expect(
                chat.attributes[ATTR_GEN_AI_OUTPUT_MESSAGES]
              ).toBeUndefined();
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

      expect(invokeAgentSpans).toHaveLength(1);
      expect(chatSpans).toHaveLength(2);
      expect(toolSpans).toHaveLength(1);

      const [root] = invokeAgentSpans;
      const [toolSpan] = toolSpans;
      expect(root.parentSpanId).toBeUndefined();

      // Every span shares the root's OTel trace and the session id.
      for (const span of spans) {
        expect(span.spanContext().traceId).toBe(root.spanContext().traceId);
        expect(span.attributes[ATTR_GEN_AI_CONVERSATION_ID]).toBe(session.id);
        expect(span.attributes[ATTR_GEN_AI_PROVIDER_NAME]).toBe('gemini');
      }

      // Structure: root invoke_agent → (chat, chat, tool).
      expect(root.name).toBe('invoke_agent weather_agent');
      expect(root.attributes[ATTR_GEN_AI_AGENT_NAME]).toBe('weather_agent');
      for (const span of [...chatSpans, ...toolSpans]) {
        expect(span.parentSpanId).toBe(spanId(root));
      }

      // Root carries the user message in and the final answer out.
      expect(root.attributes).toMatchObject({
        [ATTR_GEN_AI_INPUT_MESSAGES]: expect.stringContaining(
          'What is the weather in Paris?'
        ),
        [ATTR_GEN_AI_OUTPUT_MESSAGES]: expect.stringContaining(
          'It is sunny in Paris.'
        ),
      });

      // Chat spans carry request/response messages and token usage.
      const firstChat = chatSpans.find(span =>
        String(span.attributes[ATTR_GEN_AI_OUTPUT_MESSAGES]).includes(
          'tool_call'
        )
      );
      const secondChat = chatSpans.find(span =>
        String(span.attributes[ATTR_GEN_AI_OUTPUT_MESSAGES]).includes(
          'It is sunny in Paris.'
        )
      );
      expect(firstChat).toBeDefined();
      expect(secondChat).toBeDefined();
      expect(firstChat!.name).toBe(`chat ${TEST_MODEL}`);
      expect(firstChat!.attributes).toMatchObject({
        [ATTR_GEN_AI_REQUEST_MODEL]: TEST_MODEL,
        [ATTR_GEN_AI_INPUT_MESSAGES]: expect.stringContaining(
          'What is the weather in Paris?'
        ),
        [ATTR_GEN_AI_USAGE_INPUT_TOKENS]: 10,
        [ATTR_GEN_AI_USAGE_OUTPUT_TOKENS]: 5,
        [ATTR_GEN_AI_USAGE_TOTAL_TOKENS]: 15,
      });
      expect(secondChat!.attributes).toMatchObject({
        [ATTR_GEN_AI_USAGE_INPUT_TOKENS]: 20,
        [ATTR_GEN_AI_USAGE_OUTPUT_TOKENS]: 8,
      });

      // Tool span records its name, call id, args and result.
      expect(toolSpan.name).toBe('execute_tool get_weather');
      expect(toolSpan.attributes).toMatchObject({
        [ATTR_GEN_AI_TOOL_NAME]: 'get_weather',
        [ATTR_GEN_AI_TOOL_CALL_ID]: 'fc-1',
        [ATTR_GEN_AI_TOOL_CALL_ARGUMENTS]: expect.stringContaining('Paris'),
        [ATTR_GEN_AI_TOOL_CALL_RESULT]: expect.stringContaining('sunny'),
      });
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
      // 2 = SpanStatusCode.ERROR
      expect(toolSpans[0].status).toMatchObject({
        code: 2,
        message: expect.stringContaining('tool failed'),
      });
      expect(
        toolSpans[0].attributes[ATTR_GEN_AI_TOOL_CALL_RESULT]
      ).toBeUndefined();
    });

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
      // bigint stringified to its digits; the cycle replaced with [Circular].
      const parsed = JSON.parse(
        String(toolSpan.attributes[ATTR_GEN_AI_TOOL_CALL_RESULT])
      );
      expect(parsed).toEqual({count: '42', label: 'ok', self: '[Circular]'});
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
