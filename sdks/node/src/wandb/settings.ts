import {defaultHost, getUrls} from '../urls';
import {Netrc} from '../utils/netrc';
import * as fs from 'node:fs';
import * as path from 'node:path';
import * as os from 'node:os';
import * as ini from 'ini';

function getBaseUrlFromConfig(): string | undefined {
  // Check environment first
  const envBaseUrl = process.env.WANDB_BASE_URL;
  if (envBaseUrl) {
    return envBaseUrl;
  }

  // Try to read from config file
  try {
    const configPath = path.join(os.homedir(), '.config', 'wandb', 'settings');
    if (fs.existsSync(configPath)) {
      const config = ini.parse(fs.readFileSync(configPath, 'utf-8'));
      if (config.default?.wandb_base_url) {
        return config.default.wandb_base_url;
      }
    }
  } catch (error) {
    // Silently fail if we can't read the config file
    // This could happen in restricted environments like Deno
  }

  return undefined;
}

function getApiKeyFromNetrc(host: string): string | undefined {
  try {
    const netrc = new Netrc();
    return netrc.entries.get(host)?.password;
  } catch (error) {
    // Silently fail if we can't read the netrc file
    // This could happen in restricted environments like Deno
    return undefined;
  }
}

export function getApiKey(host: string): string {
  // 1. Check environment variable first
  const envApiKey = process.env.WANDB_API_KEY;
  if (envApiKey) {
    return envApiKey;
  }

  // 2. Try netrc file
  const netrcApiKey = getApiKeyFromNetrc(host);
  if (netrcApiKey) {
    return netrcApiKey;
  }

  // No API key found, throw informative error
  const domain = defaultHost;
  const apiKeyNotFoundMessage = `
    wandb API key not found.
    
    Go to https://${domain}/authorize to get your API key.
    
    You can either:
    
    1. Set the WANDB_API_KEY environment variable
    2. Log in using weave.login()
    `;
  throw new Error(apiKeyNotFoundMessage);
}

export function getWandbConfigs() {
  // Get base URL from environment or config
  const configBaseUrl = getBaseUrlFromConfig();
  const host = configBaseUrl ? new URL(configBaseUrl).host : defaultHost;

  const apiKey = getApiKey(host);
  const {baseUrl, traceBaseUrl, domain, host: resolvedHost} = getUrls(host);
  return {apiKey, baseUrl, traceBaseUrl, domain, resolvedHost};
}
