import {
  BasicTracerProvider,
  InMemorySpanExporter,
  SimpleSpanProcessor,
} from '@opentelemetry/sdk-trace-base';

import {flushOTel} from '../../genai/flush';
import {getWeaveTracer, getWeaveTracerProvider} from '../../genai/provider';
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

  it('stamps the weave SDK resource attributes on the provider', () => {
    installFakeClient();
    getWeaveTracer('weave-genai');
    const provider = getWeaveTracerProvider();
    expect(provider).not.toBeNull();
    const attrs = provider!.resource.attributes;
    expect(attrs[WEAVE_RESOURCE_ATTR.WEAVE_SDK_VERSION]).toBe(packageVersion);
    expect(attrs[WEAVE_RESOURCE_ATTR.WEAVE_SDK_LANGUAGE]).toBe('node');
  });

  it('keeps the target project off the immutable Resource (routing rides the project_id header)', () => {
    installFakeClient();
    getWeaveTracer('weave-genai');
    const provider = getWeaveTracerProvider();
    expect(provider).not.toBeNull();
    const attrs = provider!.resource.attributes;
    // Regression guard: server precedence ranks these Resource attrs above the
    // exporter's project_id header, so baking them in pins routing to the first
    // project and bleeds a later init()'s spans into it.
    expect(attrs['wandb.entity']).toBeUndefined();
    expect(attrs['wandb.project']).toBeUndefined();
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
    // The OTLP proto exporter buries its request headers a couple of layers
    // deep. Reaching in here (in the test only) lets us assert the concrete
    // routing target — the `project_id` header — that a re-init must follow.
    function exporterProjectId(provider: BasicTracerProvider): string {
      const processor = (provider as any)._registeredSpanProcessors?.[0];
      const exporter = processor?._exporter;
      const headers = exporter?._transport?._transport?._parameters?.headers;
      return headers?.project_id;
    }

    it('reuses the cached provider when re-init targets the same project', () => {
      installFakeClient({}, 'ent/A');
      getWeaveTracer('weave-genai');
      const first = getWeaveTracerProvider();

      // Same project again: the cached provider is reused, not rebuilt.
      installFakeClient({}, 'ent/A');
      getWeaveTracer('weave-genai');
      expect(getWeaveTracerProvider()).toBe(first);
    });

    it('rebuilds the provider when re-init targets a different project', () => {
      installFakeClient({}, 'ent/A');
      getWeaveTracer('weave-genai');
      const providerA = getWeaveTracerProvider();
      expect(providerA).toBeInstanceOf(BasicTracerProvider);

      // Re-init to a different project must NOT hand back A's cached provider,
      // or B's agent spans would export under A (the reported bleed).
      installFakeClient({}, 'ent/B');
      getWeaveTracer('weave-genai');
      const providerB = getWeaveTracerProvider();
      expect(providerB).toBeInstanceOf(BasicTracerProvider);
      expect(providerB).not.toBe(providerA);
    });

    it('shuts down the old provider when switching projects', () => {
      installFakeClient({}, 'ent/A');
      getWeaveTracer('weave-genai');
      const providerA = getWeaveTracerProvider()!;
      const shutdownSpy = jest.spyOn(providerA, 'shutdown').mockResolvedValue();

      installFakeClient({}, 'ent/B');
      getWeaveTracer('weave-genai');

      // The abandoned provider is torn down (its shutdown() force-flushes
      // A's queued spans, then disposes it) so we don't leak an exporter.
      expect(shutdownSpy).toHaveBeenCalledTimes(1);
      shutdownSpy.mockRestore();
    });

    it('routes the rebuilt provider to the new project via the project_id header', () => {
      installFakeClient({}, 'ent/A');
      getWeaveTracer('weave-genai');
      expect(exporterProjectId(getWeaveTracerProvider()!)).toBe('ent/A');

      installFakeClient({}, 'ent/B');
      getWeaveTracer('weave-genai');
      expect(exporterProjectId(getWeaveTracerProvider()!)).toBe('ent/B');
    });
  });
});
