import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { getGlobalDomain } from '../urls';

export function readApiKeyFromNetrc(host: string): string | undefined {
  const netrcPath = path.join(os.homedir(), '.netrc');
  if (!fs.existsSync(netrcPath)) {
    return undefined;
  }

  const netrcContent = fs.readFileSync(netrcPath, 'utf-8');
  const lines = netrcContent.split('\n');
  let foundMachine = false;
  for (const line of lines) {
    const trimmedLine = line.trim();
    if (trimmedLine.startsWith('machine') && trimmedLine.includes(host)) {
      foundMachine = true;
    } else if (foundMachine && trimmedLine.startsWith('password')) {
      return trimmedLine.split(' ')[1];
    }
  }
  return undefined;
}

export function getApiKey(host: string): string {
  let apiKey = process.env.WANDB_API_KEY;
  if (!apiKey) {
    apiKey = readApiKeyFromNetrc(host);
  }
  if (!apiKey) {
    const domain = getGlobalDomain();
    const apiKeyNotFoundMessage = `
    wandb API key not found.
    
    Go to https://${domain}/authorize to get your API key.
    
    You can either:
    
    1. Set the WANDB_API_KEY environment variable.
    2. Add your API key to your .netrc file, in a stanza like this:
    
        machine ${domain}
            login user
            password <your-wandb-api-key>
    `;
    throw new Error(apiKeyNotFoundMessage);
  }
  return apiKey;
}

export function parseProject(project: string): { entityName?: string; projectName: string } {
  let entityName: string | undefined;
  let projectName: string = project;

  if (project.includes('/')) {
    [entityName, projectName] = project.split('/');
  }
  return { entityName, projectName };
}
