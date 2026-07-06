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
import {packageVersion} from '../utils/packageVersion';
import type {WeaveClient} from '../weaveClient';
import {getWandbConfigs} from '../wandb/settings';

import {WEAVE_RESOURCE_ATTR} from './weaveResource';
import state from '../state';

const SDK_LANGUAGE = 'node';
const GENAI_OTLP_PATH = '/agents/otel/v1/traces';

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
  return state.genAi.provider;
}

export function clearWeaveTracerProvider() {
  state.genAi.provider = null;
  state.genAi.providerProjectId = null;
}

function getOrBuildProvider(client: WeaveClient): BasicTracerProvider {
  // The provider routes agent spans to a single project: the target rides the
  // exporter's `project_id` header (see buildOtlpExporter), and server-side
  // precedence puts Resource attrs above that header. So the project must NOT
  // live on the immutable Resource, or a later `weave.init('ent/B')` can't
  // re-route — the cached provider keeps exporting B's spans under A.
  //
  // Because we own a standalone provider (not OTel's set-once global), the
  // simplest correct re-route is to rebuild when the target project changes.
  // This mirrors the Python fix (#7507) without poking the exporter's private
  // request internals.
  const cached = state.genAi.provider;
  if (cached && state.genAi.providerProjectId === client.projectId) {
    return cached;
  }
  if (cached) {
    // A re-init pointed us at a different project. Flush spans queued under the
    // old project before tearing the provider down, then rebuild for the new
    // one. shutdown() force-flushes then disposes; failures are best-effort
    // since the queued spans belong to the previous project regardless.
    void cached.shutdown().catch(() => {
      // Nothing actionable if the old provider fails to drain; we're replacing
      // it either way.
    });
  }

  const resource = new Resource({
    [WEAVE_RESOURCE_ATTR.WEAVE_SDK_VERSION]: packageVersion,
    [WEAVE_RESOURCE_ATTR.WEAVE_SDK_LANGUAGE]: SDK_LANGUAGE,
  });

  state.genAi.provider = new BasicTracerProvider({
    resource,
    spanProcessors: [buildSpanProcessor(client)],
  });
  state.genAi.providerProjectId = client.projectId;
  registerBeforeExitHookOnce();
  return state.genAi.provider;
}

// Best-effort flush on process exit. Registered the first time a real
// provider is built, so processes that never use the GenAI surface don't pay
// the hook cost.
function registerBeforeExitHookOnce(): void {
  if (state.genAi.providerRegistered) {
    return;
  }
  state.genAi.providerRegistered = true;
  process.once('beforeExit', async () => {
    if (!state.genAi.provider) {
      return;
    }
    try {
      await state.genAi.provider.shutdown();
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
