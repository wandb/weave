import type {Tracer} from '@opentelemetry/api';
import {OTLPTraceExporter} from '@opentelemetry/exporter-trace-otlp-proto';
import {Resource} from '@opentelemetry/resources';
import {
  AlwaysOffSampler,
  BasicTracerProvider,
  BatchSpanProcessor,
  SimpleSpanProcessor,
  type SpanProcessor,
} from '@opentelemetry/sdk-trace-base';

import {getGlobalClient} from '../clientApi';
import {globalSingleton} from '../utils/globalSingleton';
import {packageVersion} from '../utils/packageVersion';
import type {WeaveClient} from '../weaveClient';
import {getWandbConfigs} from '../wandb/settings';

import {WEAVE_RESOURCE_ATTR} from './weaveResource';

const SDK_LANGUAGE = 'node';
const GENAI_OTLP_PATH = '/agents/otel/v1/traces';

/** Key for the dual-package-hazard-safe singleton holder routed through
 *  `globalThis`. Exported so tests can reset the holder via `Symbol.for`. */
export const PROVIDER_HOLDER_SYMBOL_NAME = '_weave_genai_provider';

// Dual-package-hazard-safe: routed through globalThis so CJS and ESM copies
// of this module share one provider instance per process.
const _providerHolder = globalSingleton<{
  provider: BasicTracerProvider | null;
  beforeExitRegistered: boolean;
}>(PROVIDER_HOLDER_SYMBOL_NAME, () => ({
  provider: null,
  beforeExitRegistered: false,
}));

// Standalone no-op provider for the "weave.init() not called" path. The
// `AlwaysOffSampler` makes every emitted span non-recording, so all
// downstream `span.set*` / `span.end` calls become cheap no-ops and nothing
// is ever exported. Kept separate from the OTel global registry so
// user-installed providers don't redirect our spans somewhere else.
const NOOP_PROVIDER = new BasicTracerProvider({
  sampler: new AlwaysOffSampler(),
});

/**
 * Returns the singleton Tracer for Weave-emitted GenAI spans.
 *
 * If `weave.init()` has not been called, a no-op tracer is returned and all
 * downstream API calls remain safe to invoke; spans are silently dropped.
 *
 * @param name Instrumentation library name. Use a stable identifier per
 *             emitter (e.g. `'weave-genai'`).
 */
export function getWeaveTracer(name: string): Tracer {
  const client = getGlobalClient();
  if (!client) {
    return NOOP_PROVIDER.getTracer(name, packageVersion);
  }
  return getOrBuildProvider(client).getTracer(name, packageVersion);
}

/**
 * Returns the live singleton TracerProvider, or `null` if no GenAI tracer
 * has been pulled yet. Used by the `flushOTel` / `beforeExit` paths.
 */
export function getWeaveTracerProvider(): BasicTracerProvider | null {
  return _providerHolder.provider;
}

export function clearWeaveTracerProvider() {
  _providerHolder.provider = null;
}

function getOrBuildProvider(client: WeaveClient): BasicTracerProvider {
  if (_providerHolder.provider) {
    return _providerHolder.provider;
  }

  const [entity, project] = client.projectId.includes('/')
    ? client.projectId.split('/')
    : ['', client.projectId];

  const resource = new Resource({
    [WEAVE_RESOURCE_ATTR.WANDB_ENTITY]: entity,
    [WEAVE_RESOURCE_ATTR.WANDB_PROJECT]: project,
    [WEAVE_RESOURCE_ATTR.WEAVE_SDK_VERSION]: packageVersion,
    [WEAVE_RESOURCE_ATTR.WEAVE_SDK_LANGUAGE]: SDK_LANGUAGE,
  });

  _providerHolder.provider = new BasicTracerProvider({
    resource,
    spanProcessors: [buildSpanProcessor(client)],
  });
  registerBeforeExitHookOnce();
  return _providerHolder.provider;
}

// Best-effort flush on process exit. Registered the first time a real
// provider is built, so processes that never use the GenAI surface don't pay
// the hook cost.
function registerBeforeExitHookOnce(): void {
  if (_providerHolder.beforeExitRegistered) {
    return;
  }
  _providerHolder.beforeExitRegistered = true;
  process.once('beforeExit', async () => {
    if (!_providerHolder.provider) {
      return;
    }
    try {
      await _providerHolder.provider.shutdown();
    } catch {
      // If shutdown fails we have no good place to surface it — the
      // process is already on its way out.
    }
  });
}

function buildSpanProcessor(client: WeaveClient): SpanProcessor {
  const genai = client.settings.genai;
  const choice = genai.spanProcessor ?? 'batch';

  // Power-user override: the caller owns the full pipeline, including
  // exporter routing. Used by tests too (e.g. SimpleSpanProcessor wrapping
  // an InMemorySpanExporter).
  if (typeof choice !== 'string') {
    return choice;
  }

  const exporter = buildOtlpExporter(client);
  if (choice === 'simple') {
    return new SimpleSpanProcessor(exporter);
  }
  return new BatchSpanProcessor(exporter, genai.batchOptions);
}

// Private today. A user-supplied SpanProcessor (via
// settings.genai.spanProcessor) fully owns its own exporter and bypasses
// this one — fine for tests and for users who don't care about reaching
// the Weave Agents tab, but it leaves no clean path for "custom
// queue/retry logic AND spans land in Weave."
//
// If that use case shows up, expose this as `getWeaveOTLPExporter()` so
// callers can wrap-not-replace:
//
//   const exporter = weave.getWeaveOTLPExporter();
//   const processor = new MyCustomBatchProcessor(exporter, { ... });
//   await weave.init('entity/project', { genai: { spanProcessor: processor } });
//
// Not done now: nothing needs it, and widening the public API has support
// cost.
function buildOtlpExporter(client: WeaveClient): OTLPTraceExporter {
  const {apiKey} = getWandbConfigs();
  const url = `${client.traceServerApi.baseUrl}${GENAI_OTLP_PATH}`;
  const authHeader = `Basic ${Buffer.from(`api:${apiKey}`).toString('base64')}`;
  return new OTLPTraceExporter({
    url,
    headers: {Authorization: authHeader, project_id: client.projectId},
  });
}
