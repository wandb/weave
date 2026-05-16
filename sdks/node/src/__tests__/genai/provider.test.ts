import {
  BasicTracerProvider,
  InMemorySpanExporter,
  SimpleSpanProcessor,
} from '@opentelemetry/sdk-trace-base';

import {setGlobalClient} from '../../clientApi';
import {Api as TraceServerApi} from '../../generated/traceServerApi';
import {flushWeaveOTel} from '../../genai/flush';
import {
  getWeaveTracer,
  getWeaveTracerProvider,
  PROVIDER_HOLDER_SYMBOL_NAME,
} from '../../genai/provider';
import {WEAVE_RESOURCE_ATTR} from '../../genai/weaveResource';
import {Settings, type SettingsInit} from '../../settings';
import {packageVersion} from '../../utils/packageVersion';
import {WandbServerApi} from '../../wandb/wandbServerApi';
import {WeaveClient} from '../../weaveClient';

const TEST_BASE_URL = 'http://localhost:8080';
const TEST_PROJECT = 'test-entity/test-project';

function installFakeClient(settings: SettingsInit = {}): WeaveClient {
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

function clearGlobalClient(): void {
  // setGlobalClient is typed for a real client, but the underlying holder
  // accepts null. Tests need this to exercise the "weave.init() not called"
  // branch.
  setGlobalClient(null);
}

// Reach into the global singleton's holder directly to reset its state.
function resetProviderSingleton(): void {
  const holder = (globalThis as Record<symbol, unknown>)[
    Symbol.for(PROVIDER_HOLDER_SYMBOL_NAME)
  ] as {provider: unknown; beforeExitRegistered: boolean} | undefined;
  if (holder) {
    holder.provider = null;
    holder.beforeExitRegistered = false;
  }
}

describe('otel/provider', () => {
  const originalApiKey = process.env.WANDB_API_KEY;

  beforeEach(() => {
    process.env.WANDB_API_KEY = 'test-api-key';
    resetProviderSingleton();
    clearGlobalClient();
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

  it('returns a non-recording tracer when weave.init() has not been called', () => {
    const tracer = getWeaveTracer('weave-genai');
    const span = tracer.startSpan('test-span');
    expect(span.isRecording()).toBe(false);
    span.end();
    expect(getWeaveTracerProvider()).toBeNull();
  });

  it('returns the same provider across multiple tracer fetches (singleton)', () => {
    installFakeClient();
    getWeaveTracer('emitter-a');
    const providerA = getWeaveTracerProvider();
    expect(providerA).toBeInstanceOf(BasicTracerProvider);
    getWeaveTracer('emitter-b');
    expect(getWeaveTracerProvider()).toBe(providerA);
  });

  it('stamps the wandb + weave SDK resource attributes on the provider', () => {
    installFakeClient();
    getWeaveTracer('weave-genai');
    const provider = getWeaveTracerProvider();
    expect(provider).not.toBeNull();
    const attrs = provider!.resource.attributes;
    expect(attrs[WEAVE_RESOURCE_ATTR.WANDB_ENTITY]).toBe('test-entity');
    expect(attrs[WEAVE_RESOURCE_ATTR.WANDB_PROJECT]).toBe('test-project');
    expect(attrs[WEAVE_RESOURCE_ATTR.WEAVE_SDK_VERSION]).toBe(packageVersion);
    expect(attrs[WEAVE_RESOURCE_ATTR.WEAVE_SDK_LANGUAGE]).toBe('node');
  });

  it('honors a user-supplied SpanProcessor and routes spans through it', async () => {
    const exporter = new InMemorySpanExporter();
    const processor = new SimpleSpanProcessor(exporter);
    installFakeClient({genai: {spanProcessor: processor}});

    const tracer = getWeaveTracer('weave-genai');
    tracer.startSpan('user-supplied-processor-span').end();
    await flushWeaveOTel();

    const finished = exporter.getFinishedSpans();
    expect(finished).toHaveLength(1);
    expect(finished[0].name).toBe('user-supplied-processor-span');
    // Resource attributes propagate from the provider to the exported span.
    expect(
      finished[0].resource.attributes[WEAVE_RESOURCE_ATTR.WANDB_ENTITY]
    ).toBe('test-entity');
  });

  it('flushWeaveOTel is a no-op when no provider has been built', async () => {
    await expect(flushWeaveOTel()).resolves.toBeUndefined();
  });

  it('flushWeaveOTel triggers forceFlush on the active provider', async () => {
    installFakeClient();
    getWeaveTracer('weave-genai');
    const provider = getWeaveTracerProvider()!;
    const flushSpy = jest.spyOn(provider, 'forceFlush').mockResolvedValue();
    await flushWeaveOTel();
    expect(flushSpy).toHaveBeenCalledTimes(1);
    flushSpy.mockRestore();
  });
});
