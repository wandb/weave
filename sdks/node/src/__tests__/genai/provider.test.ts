import {
  BasicTracerProvider,
  InMemorySpanExporter,
  SimpleSpanProcessor,
} from '@opentelemetry/sdk-trace-base';

import {flushOTel} from '../../genai/flush';
import {
  getWeaveTracer,
  getWeaveTracerProvider,
  resetTracerProviderForReinit,
} from '../../genai/provider';
import {WEAVE_RESOURCE_ATTR} from '../../genai/weaveResource';
import {packageVersion} from '../../utils/packageVersion';

import {installFakeClient, setupGenAITestEnvironment} from './common';

describe('otel/provider', () => {
  setupGenAITestEnvironment();

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

  it('stamps exactly the weave/wandb resource attributes (target project stays off the Resource)', () => {
    installFakeClient();
    getWeaveTracer('weave-genai');
    const provider = getWeaveTracerProvider();
    expect(provider).not.toBeNull();
    // Snapshot the full set of attributes in our own `weave.`/`wandb.`
    // namespaces (ignoring OTel's default telemetry.* / service.name). The
    // exact match is the regression guard: server precedence ranks
    // `wandb.entity`/`wandb.project` Resource attrs above the exporter's
    // project_id header, so if either ever crept back onto the (immutable)
    // Resource it would pin routing to the first project and bleed a later
    // init()'s spans into it. A stray `wandb.*` key here fails the snapshot.
    const attrs = provider!.resource.attributes;
    const weaveOwned = Object.fromEntries(
      Object.entries(attrs).filter(
        ([k]) => k.startsWith('weave.') || k.startsWith('wandb.')
      )
    );
    expect(weaveOwned).toEqual({
      [WEAVE_RESOURCE_ATTR.WEAVE_SDK_VERSION]: packageVersion,
      [WEAVE_RESOURCE_ATTR.WEAVE_SDK_LANGUAGE]: 'node',
    });
  });

  it('honors a user-supplied SpanProcessor and routes spans through it', async () => {
    const exporter = new InMemorySpanExporter();
    const processor = new SimpleSpanProcessor(exporter);
    installFakeClient({genai: {spanProcessor: processor}});

    const tracer = getWeaveTracer('weave-genai');
    tracer.startSpan('user-supplied-processor-span').end();
    await flushOTel();

    const finished = exporter.getFinishedSpans();
    expect(finished).toHaveLength(1);
    expect(finished[0].name).toBe('user-supplied-processor-span');
    // Resource attributes propagate from the provider to the exported span.
    expect(
      finished[0].resource.attributes[WEAVE_RESOURCE_ATTR.WEAVE_SDK_LANGUAGE]
    ).toBe('node');
  });

  it('flushOTel is a no-op when no provider has been built', async () => {
    await expect(flushOTel()).resolves.toBeUndefined();
  });

  it('flushOTel triggers forceFlush on the active provider', async () => {
    installFakeClient();
    getWeaveTracer('weave-genai');
    const provider = getWeaveTracerProvider()!;
    const flushSpy = jest.spyOn(provider, 'forceFlush').mockResolvedValue();
    await flushOTel();
    expect(flushSpy).toHaveBeenCalledTimes(1);
    flushSpy.mockRestore();
  });

  describe('project re-routing across weave.init() calls', () => {
    // Simulate a re-init to `projectId`: install the client (as init() does)
    // and run the teardown init() drives, then pull a tracer to (re)build the
    // provider. Keeps these tests exercising the same reset path as init(),
    // without standing up the full network-touching init().
    function reinit(projectId: string): void {
      installFakeClient({}, {projectId});
      resetTracerProviderForReinit(projectId);
      getWeaveTracer('weave-genai');
    }

    // TODO(#7512 review): this reaches into OTLP proto exporter internals to
    // read the `project_id` header a couple of layers deep. It's the concrete
    // routing target a re-init must follow, but it's coupled to exporter
    // internals — better replaced by an integration test that asserts the
    // header on a captured export once we have that harness.
    function exporterProjectId(provider: BasicTracerProvider): string {
      const processor = (provider as any)._registeredSpanProcessors?.[0];
      const exporter = processor?._exporter;
      const headers = exporter?._transport?._transport?._parameters?.headers;
      return headers?.project_id;
    }

    it('reuses the cached provider when re-init targets the same project', () => {
      reinit('ent/A');
      const first = getWeaveTracerProvider();

      // Same project again: the cached provider is reused, not rebuilt.
      reinit('ent/A');
      expect(getWeaveTracerProvider()).toBe(first);
    });

    it('rebuilds the provider when re-init targets a different project', () => {
      reinit('ent/A');
      const providerA = getWeaveTracerProvider();
      expect(providerA).toBeInstanceOf(BasicTracerProvider);

      // Re-init to a different project must NOT hand back A's cached provider,
      // or B's agent spans would export under A (the reported bleed).
      reinit('ent/B');
      const providerB = getWeaveTracerProvider();
      expect(providerB).toBeInstanceOf(BasicTracerProvider);
      expect(providerB).not.toBe(providerA);
    });

    it('shuts down the old provider when switching projects', () => {
      reinit('ent/A');
      const providerA = getWeaveTracerProvider()!;
      const shutdownSpy = jest.spyOn(providerA, 'shutdown').mockResolvedValue();

      reinit('ent/B');

      // The abandoned provider is torn down (its shutdown() force-flushes
      // A's queued spans, then disposes it) so we don't leak an exporter.
      expect(shutdownSpy).toHaveBeenCalledTimes(1);
      shutdownSpy.mockRestore();
    });

    it('routes the rebuilt provider to the new project via the project_id header', () => {
      reinit('ent/A');
      expect(exporterProjectId(getWeaveTracerProvider()!)).toBe('ent/A');

      reinit('ent/B');
      expect(exporterProjectId(getWeaveTracerProvider()!)).toBe('ent/B');
    });
  });
});
