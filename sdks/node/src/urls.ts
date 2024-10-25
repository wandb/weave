import { requireGlobalClient } from './clientApi';

export const defaultHost = 'wandb.ai';

export function getUrls(host?: string) {
  const resolvedHost = host ?? defaultHost;
  const isDefault = resolvedHost === defaultHost;

  return {
    baseUrl: isDefault ? `https://api.${resolvedHost}` : `https://${resolvedHost}`,
    traceBaseUrl: isDefault ? `https://trace.${resolvedHost}` : `https://${resolvedHost}`,
    domain: isDefault ? defaultHost : resolvedHost,
  };
}

let globalDomain: string | undefined = undefined;

export function getGlobalDomain() {
  const client = requireGlobalClient();
  const domain = client.urls.domain;

  // wandb login saves the .netrc as api.wandb.ai
  if (domain === 'api.wandb.ai') {
    return 'wandb.ai';
  }
  return domain;
}

export function setGlobalDomain(domain: string) {
  globalDomain = domain;
}
