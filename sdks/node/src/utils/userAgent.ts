import {existsSync, readFileSync} from 'fs';
import {dirname, join} from 'path';
import {fileURLToPath} from 'url';

export let packageVersion: string;

// Get current directory, handling both CommonJS and ESM
let currentDir: string;
try {
  // CommonJS
  currentDir = __dirname;
} catch {
  // ESM fallback
  currentDir = dirname(fileURLToPath(import.meta.url));
}

const twoLevelsUp = join(currentDir, '..', '..', 'package.json');
const oneLevelUp = join(currentDir, '..', 'package.json');

if (existsSync(twoLevelsUp)) {
  // This is the case in the built npm package
  const packageJson = JSON.parse(readFileSync(twoLevelsUp, 'utf8'));
  packageVersion = packageJson.version;
} else if (existsSync(oneLevelUp)) {
  // This is the case in dev
  const packageJson = JSON.parse(readFileSync(oneLevelUp, 'utf8'));
  packageVersion = packageJson.version;
} else {
  console.warn('Failed to find package.json');
  packageVersion = 'unknown';
}

export function userAgent() {
  return `Weave JS Client ${packageVersion}`;
}
