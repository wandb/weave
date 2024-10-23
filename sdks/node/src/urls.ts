import { requireGlobalClient } from './clientApi';

export const defaultBaseUrl = 'https://api.wandb.ai';
export const defaultTraceBaseUrl = 'https://trace.wandb.ai';
export const defaultDomain = 'wandb.ai';

let globalDomain: string | undefined = undefined;

export function getGlobalDomain() {
  const client = requireGlobalClient();
  return client.urls.domain;
}

export function setGlobalDomain(domain: string) {
  globalDomain = domain;
}
