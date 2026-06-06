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
 * Render the metadata as flattened OpenTelemetry span attributes. OTel
 * attributes must be scalars, so the nested shape is flattened to dotted keys
 * (`integration.name`, `integration.version`, `integration.meta.<key>`). Used
 * by the agent OTel integrations that emit spans instead of Weave calls. The
 * trace server reconstructs the nested `integration` dict on ingest.
 */
export function asOtelAttributes(
  metadata: IntegrationMetadata
): Record<string, string | number | boolean> {
  const attributes: Record<string, string | number | boolean> = {
    [`${INTEGRATION_ATTRIBUTE_KEY}.name`]: metadata.name,
    [`${INTEGRATION_ATTRIBUTE_KEY}.version`]: metadata.version,
  };
  for (const [key, value] of Object.entries(metadata.meta)) {
    const scalar =
      typeof value === 'string' ||
      typeof value === 'number' ||
      typeof value === 'boolean';
    attributes[`${INTEGRATION_ATTRIBUTE_KEY}.meta.${key}`] = scalar
      ? value
      : String(value);
  }
  return attributes;
}
