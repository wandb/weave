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
  InMemoryRunner,
  LlmAgent,
  type LlmRequest,
  type LlmResponse,
} from '@google/adk';

import {setGlobalClient} from '../../clientApi';
import {clearWeaveTracerProvider} from '../../genai/provider';
import {WeaveAdkPlugin} from '../../integrations/googleAdk';
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

function textResponse(text: string): LlmResponse {
  return {
    content: {role: 'model', parts: [{text}]},
    turnComplete: true,
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
    span => span.attributes['gen_ai.operation.name'] === operation
  );
}

describe('Google ADK integration — run spans', () => {
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
    expect(root.parentSpanId).toBeUndefined();
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

    const [root] = byOperation(exporter.getFinishedSpans(), 'invoke_agent');
    expect(root).toBeDefined();
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
