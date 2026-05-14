import {
  InMemorySpanExporter,
  type ReadableSpan,
  SimpleSpanProcessor,
} from '@opentelemetry/sdk-trace-base';

import {setGlobalClient} from '../../clientApi';
import {_currentLLM, _currentSession, _currentTurn} from '../../genai/context';
import {Api as TraceServerApi} from '../../generated/traceServerApi';
import {PROVIDER_HOLDER_SYMBOL_NAME} from '../../genai/provider';
import {Settings, type SettingsInit} from '../../settings';
import {WandbServerApi} from '../../wandb/wandbServerApi';
import {WeaveClient} from '../../weaveClient';

export const TEST_BASE_URL = 'http://localhost:8080';
export const TEST_PROJECT = 'test-entity/test-project';

export function installFakeClient(settings: SettingsInit = {}): WeaveClient {
  const traceServerApi = {baseUrl: TEST_BASE_URL} as TraceServerApi<any>;
  const client = new WeaveClient(
    traceServerApi,
    {} as WandbServerApi,
    TEST_PROJECT,
    new Settings(
      settings.printCallLink ?? true,
      settings.globalAttributes ?? {},
      settings.genai ?? {}
    )
  );
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
  const holder = (globalThis as Record<symbol, unknown>)[
    Symbol.for(PROVIDER_HOLDER_SYMBOL_NAME)
  ] as {provider: unknown; beforeExitRegistered: boolean} | undefined;
  if (holder) {
    holder.provider = null;
    holder.beforeExitRegistered = false;
  }
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
    // Clear ALS stores so test bodies start without inherited Session/Turn/LLM
    // state from any prior test in the same async chain.
    _currentSession.enterWith(undefined);
    _currentTurn.enterWith(undefined);
    _currentLLM.enterWith(undefined);
  });

  afterEach(() => {
    resetProviderSingleton();
    clearGlobalClient();
    _currentSession.enterWith(undefined);
    _currentTurn.enterWith(undefined);
    _currentLLM.enterWith(undefined);
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
