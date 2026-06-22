import type {BufferConfig, SpanProcessor} from '@opentelemetry/sdk-trace-base';

/**
 * Client-level settings that may be provided to `weave.init`.
 *
 * When possible, settings from the [Weave Python SDK](https://docs.wandb.ai/weave/reference/python-sdk)
 * are supported here with the same semantics. Some are planned but not yet
 * implemented; others are Python-specific and don't apply to the TypeScript
 * SDK.
 *
 * If your project would benefit from an unsupported setting, check the
 * [issues](https://github.com/wandb/weave/issues) to see if one has already
 * been filed — and if not, [open one](https://github.com/wandb/weave/issues/new/choose).
 *
 * Some settings can also be configured via environment variables using the prefix
 * `WEAVE_`; these take precedence over settings passed to `weave.init`.
 *
 * | Status    | TS                    | Environment variable      | Python                          |
 * | --------- | --------------------- | ------------------------- | ------------------------------- |
 * | supported | `attributes`          | —                         | —                               |
 * | supported | `genai.spanProcessor` | —                         | —                               |
 * | supported | `genai.batchOptions`  | —                         | —                               |
 * | supported | `printCallLink`       | `WEAVE_PRINT_CALL_LINK`   | `print_call_link`               |
 * | supported | `useOTelV2`           | `WEAVE_USE_OTEL_V2`       | `use_otel_v2`                   |
 * | planned   | —                     | —                         | `disabled`                      |
 * | —         | —                     | —                         | `log_level`                     |
 * | —         | —                     | —                         | `capture_code`                  |
 * | —         | —                     | —                         | `http_timeout`                  |
 * | —         | —                     | —                         | `retry_max_interval`            |
 * | —         | —                     | —                         | `retry_max_attempts`            |
 * | —         | —                     | —                         | `max_calls_queue_size`          |
 * | —         | —                     | —                         | `use_calls_complete`            |
 * | —         | —                     | —                         | `redact_pii`                    |
 * | —         | —                     | —                         | `redact_pii_fields`             |
 * | —         | —                     | —                         | `redact_pii_exclude_fields`     |
 * | —         | —                     | —                         | `capture_client_info`           |
 * | —         | —                     | —                         | `implicitly_patch_integrations` |
 * | —         | —                     | —                         | `client_parallelism`            |
 * | —         | —                     | —                         | `display_viewer`                |
 * | —         | —                     | —                         | `capture_system_info`           |
 * | —         | —                     | —                         | `scorers_dir`                   |
 * | —         | —                     | —                         | `use_server_cache`              |
 * | —         | —                     | —                         | `server_cache_size_limit`       |
 * | —         | —                     | —                         | `server_cache_dir`              |
 * | —         | —                     | —                         | `enable_disk_fallback`          |
 * | —         | —                     | —                         | `use_parallel_table_upload`     |
 * | —         | —                     | —                         | `use_stainless_server`          |
 *
 */
export type Settings = {
  /**
   * Prints links in terminal to Weave UI for ops.
   *
   * @default true
   */
  readonly printCallLink: boolean;

  /**
   * A map of attributes applied to every trace produced by this client.
   */
  readonly attributes: Record<string, any>;

  /**
   * Routes OTel-capable integrations through their OTel variant.
   *
   * @default true
   */
  useOTelV2: boolean;

  /**
   * GenAI-span pipeline settings.
   */
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

  return {
    printCallLink,
    useOTelV2,
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
