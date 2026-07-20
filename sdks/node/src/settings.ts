import type {BufferConfig, SpanProcessor} from '@opentelemetry/sdk-trace-base';

/**
 * Client-wide configuration for a Weave client.
 *
 * Options:
 * - `printCallLink` (default `true`): prints links in terminal to the Weave UI
 *   for ops. Overridden by env var `WEAVE_PRINT_CALL_LINK`.
 * - `attributes`: a map of attributes applied to every trace produced by this
 *   client.
 * - `useOTelV2` (default `true`): routes OTel-capable integrations through
 *   their OTel variant. Overridden by env var `WEAVE_USE_OTEL_V2`.
 * - `useCallsComplete` (default `true`): sends finished calls to the
 *   `calls/complete` endpoint (start+end paired client-side) instead of the
 *   legacy `call/upsert_batch` path. Overridden by env var
 *   `WEAVE_USE_CALLS_COMPLETE`.
 * - `genai.spanProcessor`: how GenAI spans are exported. `'batch'` (default)
 *   uses `BatchSpanProcessor` for production/long-lived processes; `'simple'`
 *   uses `SimpleSpanProcessor` (one HTTP POST per span) for tests and
 *   short-lived CLIs; a `SpanProcessor` instance uses a caller-owned processor
 *   and bypasses the Weave OTLP exporter at `/agents/otel/v1/traces`.
 * - `genai.batchOptions`: `BatchSpanProcessor` configuration. Ignored unless
 *   `genai.spanProcessor === 'batch'`.
 *
 * @inline
 */
export type Settings = {
  /**
   * Prints links in terminal to Weave UI for ops.
   *
   * @default `true`
   */
  readonly printCallLink: boolean;

  /**
   * A map of attributes applied to every trace produced by this client.
   */
  readonly attributes: Record<string, any>;

  /**
   * Routes OTel-capable integrations through their OTel variant.
   *
   * @default `true`
   */
  useOTelV2: boolean;

  /**
   * Sends finished calls to the `calls/complete` endpoint (start+end paired
   * client-side) instead of the legacy `call/upsert_batch` path.
   *
   * @default `true`
   */
  useCallsComplete: boolean;

  readonly genai: {
    /**
     * How GenAI spans are exported.
     *
     * - `'batch'` (default): `BatchSpanProcessor`, suitable for production
     *   agents and long-lived processes.
     * - `'simple'`: `SimpleSpanProcessor`, one HTTP POST per span. Useful for
     *   tests and short-lived CLIs where deterministic flush matters more than
     *   throughput.
     * - `SpanProcessor` instance: a user-supplied processor. The caller owns
     *   its lifecycle; the Weave OTLP exporter targeting `/agents/otel/v1/traces`
     *   is not used.
     */
    spanProcessor?: 'batch' | 'simple' | SpanProcessor;

    /**
     * `BatchSpanProcessor` configuration. Ignored unless `spanProcessor === 'batch'`.
     */
    batchOptions?: BufferConfig;
  };
};

export function makeSettings(settings: Partial<Settings> = {}): Settings {
  // Env vars take precedence over provided settings.
  const printCallLink =
    parseEnvVar(process.env.WEAVE_PRINT_CALL_LINK) ??
    settings.printCallLink ??
    true;

  const useOTelV2 =
    parseEnvVar(process.env.WEAVE_USE_OTEL_V2) ?? settings.useOTelV2 ?? true;

  const useCallsComplete =
    parseEnvVar(process.env.WEAVE_USE_CALLS_COMPLETE) ??
    settings.useCallsComplete ??
    true;

  return {
    printCallLink,
    useOTelV2,
    useCallsComplete,
    attributes: settings.attributes ?? {},
    genai: settings.genai ?? {},
  };
}

export function defaultSettings(): Settings {
  return makeSettings();
}

function parseEnvVar(val: string | undefined): boolean | undefined {
  switch (val?.toLowerCase()) {
    case 'true':
      return true;

    case 'false':
      return false;

    default:
      return undefined;
  }
}
