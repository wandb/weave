import type {BufferConfig, SpanProcessor} from '@opentelemetry/sdk-trace-base';

export type Settings = {
  /**
   * Prints links in terminal to Weave UI for ops.
   *
   * @default `true`
   */
  readonly printCallLink: boolean;

  /** @deprecated Use `printCallLink` instead. */
  readonly shouldPrintCallLink: boolean;

  /**
   * A map of attributes applied to every trace produced by this client.
   */
  globalAttributes: Record<string, any>;

  /** @deprecated Use `globalAttributes` instead. */
  readonly attributes: Record<string, any>;

  genai: {
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

    /** `BatchSpanProcessor` configuration. Ignored unless `spanProcessor === 'batch'`. */
    batchOptions?: BufferConfig;
  };
};

export function makeSettings(settings: Partial<Settings> = {}): Settings {
  // Env vars take precedence over provided settings.
  const printCallLink =
    parseEnvVar(process.env.WEAVE_PRINT_CALL_LINK) ??
    settings.printCallLink ??
    true;

  const globalAttributes = settings.globalAttributes ?? {};

  return {
    printCallLink,
    globalAttributes,
    genai: settings.genai ?? {},

    /** @deprecated Use `printCallLink` instead. */
    shouldPrintCallLink: printCallLink,

    /** @deprecated Use `globalAttributes` instead. */
    attributes: globalAttributes,
  };
}

export function shouldUseOtelV2(): boolean {
  return parseEnvVar(process.env.WEAVE_USE_OTEL_V2) ?? false;
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
