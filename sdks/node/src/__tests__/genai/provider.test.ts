import {createServer} from 'node:http';
import type {AddressInfo} from 'node:net';
import {
  BasicTracerProvider,
  InMemorySpanExporter,
  SimpleSpanProcessor,
} from '@opentelemetry/sdk-trace-base';

import {flushOTel} from '../../genai/flush';
import {
  getWeaveTracer,
  getWeaveTracerProvider,
  getWeaveTracerProviderProjectId,
  shutdownWeaveTracerProvider,
} from '../../genai/provider';
import {WEAVE_RESOURCE_ATTR} from '../../genai/weaveResource';
import {packageVersion} from '../../utils/packageVersion';
import {CallStack} from '../../weaveClient';

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

  it('exports only weave-owned resource attributes, without routing overrides', async () => {
    const exporter = new InMemorySpanExporter();
    installFakeClient({
      settings: {genai: {spanProcessor: new SimpleSpanProcessor(exporter)}},
    });
    getWeaveTracer('weave-genai').startSpan('resource-check').end();
    await flushOTel();

    const [span] = exporter.getFinishedSpans();
    const weaveOwned = Object.fromEntries(
      Object.entries(span.resource.attributes).filter(
        ([k]) => k.startsWith('weave.') || k.startsWith('wandb.')
      )
    );
    expect(weaveOwned).toEqual({
      [WEAVE_RESOURCE_ATTR.WEAVE_SDK_VERSION]: packageVersion,
      [WEAVE_RESOURCE_ATTR.WEAVE_SDK_LANGUAGE]: 'node',
    });
  });

  it('keeps eval links ahead of op links, including after a project switch', async () => {
    const originalLimit = process.env.OTEL_SPAN_ATTRIBUTE_COUNT_LIMIT;
    process.env.OTEL_SPAN_ATTRIBUTE_COUNT_LIMIT = '4';
    try {
      for (const projectId of ['ent/A', 'ent/B']) {
        const exporter = new InMemorySpanExporter();
        shutdownWeaveTracerProvider();
        const client = installFakeClient({
          projectId,
          settings: {genai: {spanProcessor: new SimpleSpanProcessor(exporter)}},
        });
        client.runWithCallStack(
          new CallStack([
            {
              callId: 'eval',
              traceId: 'trace',
              childSummary: {},
              opName: 'Evaluation.evaluate',
            },
            {
              callId: 'predict',
              traceId: 'trace',
              childSummary: {},
              opName: 'Evaluation.predictAndScore',
            },
          ]),
          () => getWeaveTracer('weave-genai').startSpan('linked-span').end()
        );
        await flushOTel();
        expect(exporter.getFinishedSpans()[0].attributes).toEqual({
          'weave.eval.run_id': 'eval',
          'weave.eval.predict_and_score_call_id': 'predict',
          'weave.eval.project_id': projectId,
          'weave.parent_call.id': 'predict',
        });
      }
    } finally {
      if (originalLimit === undefined) {
        delete process.env.OTEL_SPAN_ATTRIBUTE_COUNT_LIMIT;
      } else {
        process.env.OTEL_SPAN_ATTRIBUTE_COUNT_LIMIT = originalLimit;
      }
    }
  });

  it('honors a user-supplied SpanProcessor and routes spans through it', async () => {
    const exporter = new InMemorySpanExporter();
    const processor = new SimpleSpanProcessor(exporter);
    installFakeClient({settings: {genai: {spanProcessor: processor}}});

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
    // Simulate a re-init to `projectId`: install the client (as init() does),
    // run the same project-switch teardown init() performs, then pull a tracer
    // to (re)build the provider. Keeps these tests exercising the real reset
    // path without standing up the full network-touching init().
    function reinit(projectId: string, baseURL?: string): void {
      const client = installFakeClient({projectId});
      if (baseURL) {
        client.traceServerApi.baseURL = baseURL;
      }
      const prior = getWeaveTracerProviderProjectId();
      if (prior !== null && prior !== projectId) {
        shutdownWeaveTracerProvider();
      }
      getWeaveTracer('weave-genai');
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

    it('routes exported spans to the new project after re-init', async () => {
      const requests: {
        path: string | undefined;
        projectId: string | string[] | undefined;
      }[] = [];
      const server = createServer((request, response) => {
        requests.push({
          path: request.url,
          projectId: request.headers.project_id,
        });
        request.resume();
        response.end();
      });
      await new Promise<void>(resolve =>
        server.listen(0, '127.0.0.1', resolve)
      );
      const baseURL = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
      try {
        for (const projectId of ['ent/A', 'ent/B']) {
          reinit(projectId, baseURL);
          getWeaveTracer('weave-genai').startSpan('exported-span').end();
          await flushOTel();
        }
        expect(requests).toEqual([
          {path: '/agents/otel/v1/traces', projectId: 'ent/A'},
          {path: '/agents/otel/v1/traces', projectId: 'ent/B'},
        ]);
      } finally {
        await getWeaveTracerProvider()?.shutdown();
        await new Promise<void>(resolve => server.close(() => resolve()));
      }
    });
  });
});
