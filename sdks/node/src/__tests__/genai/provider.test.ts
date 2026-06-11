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
    await flushOTel();

    const finished = exporter.getFinishedSpans();
    expect(finished).toHaveLength(1);
    expect(finished[0].name).toBe('user-supplied-processor-span');
    // Resource attributes propagate from the provider to the exported span.
    expect(
      finished[0].resource.attributes[WEAVE_RESOURCE_ATTR.WANDB_ENTITY]
    ).toBe('test-entity');
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
});
