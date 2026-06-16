import {
  InMemorySpanExporter,
  type ReadableSpan,
  SimpleSpanProcessor,
} from '@opentelemetry/sdk-trace-base';

import {setGlobalClient} from '../../clientApi';
import {type Api as TraceServerApi} from '../../generated/traceServerApi';
import {Settings, type SettingsInit} from '../../settings';
import {WeaveClient} from '../../weaveClient';
import state from 'weave/state';

export const TEST_BASE_URL = 'http://localhost:8080';
export const TEST_PROJECT = 'test-entity/test-project';

export function installFakeClient(settings: SettingsInit = {}): WeaveClient {
  const traceServerApi = {baseUrl: TEST_BASE_URL} as TraceServerApi<any>;
  const client = new WeaveClient({
    traceServerApi,
    projectId: TEST_PROJECT,
    settings: new Settings(
      settings.printCallLink ?? true,
      settings.globalAttributes ?? {},
      settings.genai ?? {}
    ),
  });
  setGlobalClient(client);
  return client;
}

export function clearGlobalClient(): void {
  // setGlobalClient is typed for a real client, but the underlying holder
  // accepts null. Tests need this to exercise the "weave.init() not called"
  // branch.
  setGlobalClient(null as unknown as WeaveClient);
}

// Reach into the global singleton's holder directly to reset its state.
export function resetProviderSingleton(): void {
  state.genAi.provider = null;
  state.genAi.providerRegistered = false;
}

// Reach into the GenAI default-state singleton and null out its slots so each
// test body starts clean even when prior tests in the same worker mutated it.
export function resetGenaiDefaultState(): void {
  state.genAi.defaultState.session = null;
  state.genAi.defaultState.turn = null;
  state.genAi.defaultState.llm = null;
}

/**
 * Install the standard before/after-each pattern for GenAI tests: stubs
 * `WANDB_API_KEY` (so the provider's OTLP exporter can be built), resets
 * the provider singleton, and clears the global Weave client. Call inside
 * the consumer's `describe` block.
 */
export function setupGenAITestEnvironment(): void {
  const originalApiKey = process.env.WANDB_API_KEY;

  beforeEach(() => {
    process.env.WANDB_API_KEY = 'test-api-key';
    resetProviderSingleton();
    clearGlobalClient();
    resetGenaiDefaultState();
  });

  afterEach(() => {
    resetProviderSingleton();
    clearGlobalClient();
    resetGenaiDefaultState();
    if (originalApiKey === undefined) {
      delete process.env.WANDB_API_KEY;
    } else {
      process.env.WANDB_API_KEY = originalApiKey;
    }
  });
}

/** Find a finished span by name; throw with a helpful message if missing. */
export function findSpan(spans: ReadableSpan[], name: string): ReadableSpan {
  const span = spans.find(s => s.name === name);
  if (!span) {
    throw new Error(
      `no span named '${name}' (saw: ${spans.map(s => s.name).join(', ')})`
    );
  }
  return span;
}

/**
 * Assert that a span's exported start/end times match the given dates to
 * second precision. OTel records times as HrTime `[seconds, nanos]`, so we
 * compare the seconds component. Used to verify that post-hoc
 * `startTime`/`endTime` backdating flows through to the exported span.
 */
export function expectSpanTimesToMatch(
  span: ReadableSpan,
  startedAt: Date,
  endedAt: Date
): void {
  const MS_PER_SECOND = 1000;
  expect(span.startTime[0]).toBe(
    Math.floor(startedAt.getTime() / MS_PER_SECOND)
  );
  expect(span.endTime[0]).toBe(Math.floor(endedAt.getTime() / MS_PER_SECOND));
}

/**
 * Per-test setup that installs a fresh `InMemorySpanExporter` + fake client.
 * Returns a getter so tests can read `getExporter().getFinishedSpans()` after
 * spans are ended.
 *
 * Call inside a describe block, after `setupGenAITestEnvironment()` so the
 * API key and singleton resets happen first.
 */
export function setupExporterPerTest(): () => InMemorySpanExporter {
  let current: InMemorySpanExporter;
  beforeEach(() => {
    current = new InMemorySpanExporter();
    installFakeClient({
      genai: {spanProcessor: new SimpleSpanProcessor(current)},
    });
  });
  return () => current;
}
