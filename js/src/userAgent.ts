import { readFileSync } from 'fs';
import { join } from 'path';

let packageVersion: string;

try {
    const packageJson = JSON.parse(readFileSync(join(__dirname, '..', 'package.json'), 'utf8'));
    packageVersion = packageJson.version;
} catch (error) {
    console.warn('Failed to read package.json:', error);
    packageVersion = 'unknown';
}

export function userAgent() {
    return `Weave JS Client ${packageVersion}`;
}