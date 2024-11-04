import {defaultDomain, defaultHost, getUrls} from '../urls';
import {Netrc} from '../utils/netrc';

export function getApiKey(host: string): string {
  let apiKey = process.env.WANDB_API_KEY;
  if (!apiKey) {
    const netrc = new Netrc();
    apiKey = netrc.entries.get(host)?.password;
  }
  if (!apiKey) {
    // const domain = getGlobalDomain();
    const domain = defaultHost;
    const apiKeyNotFoundMessage = `
    wandb API key not found.
    
    Go to https://${domain}/authorize to get your API key.
    
    You can either:
    
    1. Set the WANDB_API_KEY environment variable.
    2. Log in using weave.login()
    3. Add your API key to your .netrc file, in a stanza like this:
        machine ${domain}
            login user
            password <your-wandb-api-key>
    `;
    throw new Error(apiKeyNotFoundMessage);
  }
  return apiKey;
}

export function getWandbConfigs() {
  let host;
  try {
    host = new Netrc().getLastEntry()!.machine;
  } catch (error) {
    throw new Error(
      `Could not find entry in netrc file.
      Visit https://${defaultDomain}/authorize to get an API key and run
      \`weave.login({apiKey: $YOUR_API_KEY})\` or \`wandb login\` if you have that installed.`
    );
  }
  const apiKey = getApiKey(host);
  const {baseUrl, traceBaseUrl, domain, host: resolvedHost} = getUrls(host);
  return {apiKey, baseUrl, traceBaseUrl, domain, resolvedHost};
}
