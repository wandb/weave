export const defaultHost = 'api.wandb.ai';
export const defaultDomain = 'wandb.ai';

function hasUrlScheme(value: string) {
  return /^[a-zA-Z][a-zA-Z\d+\-.]*:\/\//.test(value);
}

function parseUrl(value: string) {
  try {
    return new URL(value);
  } catch {
    throw new Error(
      `Invalid W&B host or URL: "${value}". Please check your WANDB_BASE_URL setting or provided host value, and report this case if you believe the input should be supported.`
    );
  }
}

export function getUrls(hostOrUrl?: string) {
  const resolvedInput = hostOrUrl ?? defaultHost;
  const parsedUrl = hasUrlScheme(resolvedInput)
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
