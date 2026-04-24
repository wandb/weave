import {globalSingleton} from './globalSingleton.js';

// Deduped across CJS/ESM module copies so a dual-loaded SDK does not emit the
// same warning twice.
const warnedKeys = globalSingleton(
  '_weave_warned_keys',
  () => new Set<string>()
);

export function warnOnce(key: string, message: string): void {
  if (!warnedKeys.has(key)) {
    console.warn(message);
    warnedKeys.add(key);
  }
}
