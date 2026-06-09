import type {BufferConfig, SpanProcessor} from '@opentelemetry/sdk-trace-base';

export interface GenAISettingsInit {
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
}

export interface SettingsInit {
  printCallLink?: boolean;
  globalAttributes?: Record<string, any>;
  genai?: GenAISettingsInit;
}

export class Settings {
  constructor(
    private printCallLink: boolean = true,
    private globalAttributes: Record<string, any> = {},
    public readonly genai: GenAISettingsInit = {}
  ) {}

  get shouldPrintCallLink(): boolean {
    return parseEnvVar(process.env.WEAVE_PRINT_CALL_LINK) ?? this.printCallLink;
  }

  get attributes(): Record<string, any> {
    return this.globalAttributes;
  }
}

export function makeSettings(settings?: SettingsInit): Settings {
  if (!settings) {
    return new Settings();
  }
  return new Settings(
    settings.printCallLink ?? true,
    settings.globalAttributes ?? {},
    settings.genai ?? {}
  );
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
