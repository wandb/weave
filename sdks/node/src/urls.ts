export const defaultHost = 'api.wandb.ai';
export const defaultDomain = 'wandb.ai';

/**
 * Checks whether a value starts with an HTTP or HTTPS scheme.
 *
 * @param value String to inspect.
 * @returns Whether the value starts with `http://` or `https://`.
 */
function hasHttpScheme(value: string) {
  return /^https?:\/\//i.test(value);
}

/**
 * Parses an HTTP(S) URL string and throws a user-friendly error when it is
 * malformed.
 *
 * @param value HTTP(S) URL string to parse.
 * @returns The parsed URL instance.
 * @throws {Error} When the provided value is not a valid URL.
 */
function parseUrl(value: string) {
  try {
    return new URL(value);
  } catch {
    throw new Error(
      `Invalid W&B host or URL: "${value}". Please check your WANDB_BASE_URL setting or provided host value, and report this case if you believe the input should be supported.`
    );
  }
}

/**
 * Resolves the W&B API and trace server URLs from either a bare host name
 * (for example `custom.wandb.ai`) or a full HTTP(S) base URL
 * (for example `http://custom.wandb.ai`).
 *
 * Bare hosts default to HTTPS. Full HTTP(S) URLs preserve their original
 * scheme. Malformed URL inputs throw a user-friendly error.
 *
 * @param hostOrUrl Optional bare host or full HTTP(S) base URL.
 * @returns The resolved W&B API base URL, trace base URL, domain, and host.
 */
export function getUrls(hostOrUrl?: string) {
  const resolvedInput = hostOrUrl ?? defaultHost;
  const parsedUrl = hasHttpScheme(resolvedInput)
    ? parseUrl(resolvedInput)
    : undefined;
  const resolvedHost = parsedUrl?.host ?? resolvedInput;
  const baseUrl = parsedUrl?.origin ?? `https://${resolvedHost}`;
  const isDefaultBaseUrl = baseUrl === `https://${defaultHost}`;

  let traceBaseUrl = process.env.WF_TRACE_SERVER_URL;

  if (traceBaseUrl === undefined || traceBaseUrl === null) {
    traceBaseUrl = isDefaultBaseUrl
      ? `https://trace.wandb.ai`
      : `${baseUrl}/traces`;
  }

  return {
    baseUrl,
    traceBaseUrl,
    domain: isDefaultBaseUrl ? defaultDomain : resolvedHost,
    host: isDefaultBaseUrl ? defaultHost : resolvedHost,
  };
}

let globalDomain: string | undefined = undefined;
export function getGlobalDomain() {
  return globalDomain;
}
export function setGlobalDomain(domain: string) {
  globalDomain = domain;
}
