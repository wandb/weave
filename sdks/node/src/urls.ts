export const defaultHost = 'api.wandb.ai';
export const defaultDomain = 'wandb.ai';

export function getUrls(host?: string) {
  const resolvedHost = host ?? defaultHost;
  const isDefault = resolvedHost === defaultHost;

  let traceBaseUrl = process.env.WF_TRACE_SERVER_URL;

  if (traceBaseUrl === undefined || traceBaseUrl === null) {
    traceBaseUrl = isDefault
      ? `https://trace.wandb.ai`
      : `https://${resolvedHost}/traces`;
  }

  return {
    baseUrl: isDefault ? `https://api.wandb.ai` : `https://${resolvedHost}`,
    traceBaseUrl,
    domain: isDefault ? defaultDomain : resolvedHost,
    host: isDefault ? defaultHost : resolvedHost,
  };
}

let globalDomain: string | undefined = undefined;
export function getGlobalDomain() {
  return globalDomain;
}
export function setGlobalDomain(domain: string) {
  globalDomain = domain;
}
