import { readFileSync, writeFileSync } from 'fs';
import { homedir } from 'os';
import { join } from 'path';

interface NetrcEntry {
  login: string;
  password: string;
  account?: string;
}

export class Netrc {
  private path: string;
  public entries: Map<string, NetrcEntry>;

  constructor(path?: string) {
    this.path = path || join(homedir(), '.netrc');
    this.entries = new Map();
    this.load();
  }

  private load(): void {
    try {
      const content = readFileSync(this.path, 'utf8');
      const lines = content.split('\n');
      let currentMachine: string | null = null;
      let currentEntry: Partial<NetrcEntry> = {};

      for (const line of lines) {
        const [key, value] = line.trim().split(/\s+/);
        switch (key) {
          case 'machine':
            if (currentMachine && Object.keys(currentEntry).length) {
              this.entries.set(currentMachine, currentEntry as NetrcEntry);
            }
            currentMachine = value;
            currentEntry = {};
            break;
          case 'login':
          case 'password':
          case 'account':
            if (currentMachine) {
              currentEntry[key] = value;
            }
            break;
        }
      }

      if (currentMachine && Object.keys(currentEntry).length) {
        this.entries.set(currentMachine, currentEntry as NetrcEntry);
      }
    } catch (error) {
      // File doesn't exist or can't be read, starting with empty entries
    }
  }

  save(): void {
    const content = Array.from(this.entries.entries())
      .map(([machine, entry]) => {
        let str = `machine ${machine}\n`;
        if (entry.login) str += `  login ${entry.login}\n`;
        if (entry.password) str += `  password ${entry.password}\n`;
        if (entry.account) str += `  account ${entry.account}\n`;
        return str;
      })
      .join('\n');

    writeFileSync(this.path, content, { mode: 0o600 });
  }

  getMachine(machine: string): NetrcEntry | undefined {
    return this.entries.get(machine);
  }

  setMachine(machine: string, entry: NetrcEntry): void {
    this.entries.set(machine, entry);
  }
}
