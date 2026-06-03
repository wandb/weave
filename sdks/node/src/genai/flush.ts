import {getWeaveTracerProvider} from './provider';

/**
 * Force-flush any GenAI spans buffered by the active span processor.
 *
 * Resolves immediately if `weave.init()` has not been called. Otherwise
 * delegates to `BasicTracerProvider.forceFlush()`, which waits for the
 * underlying span processor to drain its queue and complete its OTLP export
 * round-trip.
 *
 * Call before process exit when using `'simple'` or any other processor that
 * may have in-flight work, or in tests that need to observe exported spans
 * synchronously.
 */
export async function flushOTel(): Promise<void> {
  const provider = getWeaveTracerProvider();
  if (!provider) {
    return;
  }
  await provider.forceFlush();
}
