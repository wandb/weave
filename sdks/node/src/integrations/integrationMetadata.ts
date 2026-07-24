/**
 * Formalized integration-tracking metadata for Weave calls (TypeScript).
 *
 * Mirrors the Python `weave/integrations/integration_metadata.py`. Every call
 * produced by an integration carries provenance under
 * `attributes[INTEGRATION_ATTRIBUTE_KEY]`:
 *
 *   attributes: {
 *     integration: {
 *       name: string;              // integration id, e.g. "openai"
 *       version: string;           // version of the integrating code (Weave SDK)
 *       meta: Record<string, any>; // integration-specific, e.g. library version
 *     }
 *   }
 */
import {
  WEAVE_INTEGRATION_NAME,
  WEAVE_INTEGRATION_VERSION,
} from '../genai/semconv';
import {packageVersion as weavePackageVersion} from '../utils/packageVersion';

/** Top-level attribute key under which integration provenance is stored. */
const INTEGRATION_ATTRIBUTE_KEY = 'integration';

/** Typed integration-tracking metadata for a call's `attributes.integration`. */
export type IntegrationMetadata = {
  /** Integration identifier, e.g. `"openai"`. */
  readonly name: string;
  /**
   * Version of the integrating code. Defaults to the Weave TS SDK version;
   * an external integration would pass its own version.
   */
  readonly version: string;
  /**
   * Integration-specific detail. For library integrations this carries the
   * patched library's package name (and version, when known).
   */
  readonly meta: Record<string, any>;
};

/**
 * The attribute fragment an integration merges into a call's attributes — the
 * TS analog of the Python `IntegrationAttributes` TypedDict. The single
 * `integration` key mirrors `INTEGRATION_ATTRIBUTE_KEY`.
 */
export type IntegrationAttributes = {
  integration: IntegrationMetadata;
};

/**
 * Build `IntegrationMetadata` for a patched third-party library.
 *
 * `version` is the Weave SDK version; the library's package name (and version,
 * when supplied) are recorded under `meta`.
 */
export function libraryIntegration(
  name: string,
  opts: {
    packageName?: string;
    packageVersion?: string;
    meta?: Record<string, any>;
  } = {}
): IntegrationMetadata {
  const packageName = opts.packageName ?? name;
  const meta: Record<string, any> = {
    package_name: packageName,
    ...(opts.packageVersion != null
      ? {package_version: opts.packageVersion}
      : {}),
    ...(opts.meta ?? {}),
  };
  return {name, version: weavePackageVersion, meta};
}

/**
 * Render the attribute fragment to merge into a call's attributes. Returns a
 * fresh object each call so callers can mutate or merge it freely.
 */
export function asAttributes(
  metadata: IntegrationMetadata
): IntegrationAttributes {
  return {
    [INTEGRATION_ATTRIBUTE_KEY]: {
      name: metadata.name,
      version: metadata.version,
      meta: {...metadata.meta},
    },
  };
}

/**
 * Render the canonical Weave integration identity for OpenTelemetry spans.
 * Integration-specific metadata remains available to call-based integrations
 * through `asAttributes()` until it has a canonical OTel attribute namespace.
 */
export function asOtelAttributes(
  metadata: IntegrationMetadata
): Record<string, string | number | boolean> {
  return {
    [WEAVE_INTEGRATION_NAME]: metadata.name,
    [WEAVE_INTEGRATION_VERSION]: metadata.version,
  };
}
