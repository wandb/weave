import {readFileSync, writeFileSync} from 'fs';
import {homedir} from 'os';
import {join} from 'path';

interface NetrcEntry {
  machine: string;
  login: string;
  password: string;
}

export class Netrc {
  private path: string;
  public entries: Map<string, NetrcEntry>;

  constructor(path: string = join(homedir(), '.netrc')) {
    this.path = path;
    this.entries = new Map();
    this.load();
  }

  private load(): void {
    try {
      const content = readFileSync(this.path, 'utf8');
      let currentEntry: Partial<NetrcEntry> = {};

      const lines = content.split('\n');
      for (const line of lines) {
        const [key, value] = line.trim().split(/\s+/);
        if (key === 'machine') {
          if (currentEntry.machine && currentEntry.login) {
            this.entries.set(currentEntry.machine, currentEntry as NetrcEntry);
          }
          currentEntry = {machine: value};
        } else if (key === 'login' || key === 'password') {
          currentEntry[key] = value;
        }
      }

      if (currentEntry.machine && currentEntry.login) {
        this.entries.set(currentEntry.machine, currentEntry as NetrcEntry);
      }
    } catch (error) {
      console.error('Error parsing netrc file', error);
    }
  }

  save(): void {
    const content = Array.from(this.entries.entries())
      .map(([machine, entry]) => {
        let str = `machine ${machine}\n`;
        if (entry.login) str += `  login ${entry.login}\n`;
        if (entry.password) str += `  password ${entry.password}\n`;
        return str;
      })
      .join('\n');

    writeFileSync(this.path, content, {mode: 0o600});
  }

  getEntry(machine: string): NetrcEntry | undefined {
    return this.entries.get(machine);
  }

  setEntry({machine, ...entryProps}: NetrcEntry): void {
    if (!machine) {
      throw new Error('Machine is required');
    }
    const existing = this.entries.get(machine) ?? {machine};
    const updated = {...existing, ...entryProps, machine};
    this.entries.set(machine, updated);
  }

  getLastEntry(): NetrcEntry | undefined {
    const entries = Array.from(this.entries.values());
    return entries[entries.length - 1];
  }
}
