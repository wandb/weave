/**
 * Tests for the run-lifecycle tracing of the Google ADK (`@google/adk`)
 * integration. The plugin's run callbacks (`beforeRun` / `onEvent` /
 * `afterRun`) emit the root `invoke_agent` span carrying the GenAI semantic
 * conventions, exported to Weave's agents endpoint.
 *
 * These tests drive the plugin callbacks directly (rather than through ADK's
 * runner) so the run-span lifecycle is exercised in isolation; model and tool
 * span tracing — and the runner-driven tests that depend on them — are added
 * alongside those callbacks in later changes. Spans are captured with an
 * `InMemorySpanExporter` injected through `settings.genai.spanProcessor`,
 * exactly how a user-supplied processor plugs into the Weave tracer provider.
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
} from '../../genai/semconv';
import {WeaveAdkPlugin} from '../../integrations/googleAdk';
import {initWithCustomTraceServer} from '../clientMock';
import {InMemoryTraceServer} from '../helpers/inMemoryTraceServer';

const TEST_PROJECT = 'test-project';
const INVOCATION_ID = 'inv-1';

function userMessage(text: string) {
  return {role: 'user', parts: [{text}]};
}

function byOperation(spans: ReadableSpan[], operation: string): ReadableSpan[] {
  return spans.filter(
    span => span.attributes[ATTR_GEN_AI_OPERATION_NAME] === operation
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
