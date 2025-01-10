import {existsSync, readFileSync} from 'fs';
import {join} from 'path';

export let packageVersion: string;

const twoLevelsUp = join(__dirname, '..', '..', 'package.json');
const oneLevelUp = join(__dirname, '..', 'package.json');

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
