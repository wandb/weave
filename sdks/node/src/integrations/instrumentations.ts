import {globalSingleton} from '../utils/globalSingleton';

const symCJSInstrumentations = Symbol.for('_weave_cjs_instrumentations');
export const symESMInstrumentations = Symbol.for('_weave_esm_instrumentations');
export const symESMCache = Symbol.for('_weave_esm_cached_patched');

(global as any)[symCJSInstrumentations] =
  (global as any)[symCJSInstrumentations] ||
  // key is the module name and sub path(lookup key),
  // value is an array of instrumentations pinned to an expected version range of the module
  new Map<string, Array<Pick<CJSInstrumentation, 'version' | 'hook'>>>();

export interface CacheEntry {
  originalExports: any;
  patchedExports: any;
}

(global as any)[symESMCache] =
  (global as any)[symESMCache] || new Map<string, CacheEntry>();

export default (global as any)[symCJSInstrumentations];

export type HookFn = (exports: any, name: string, baseDir: string) => any;

(global as any)[symESMInstrumentations] =
  (global as any)[symESMInstrumentations] ||
  // key is the module name (lookup key),
  // value is an array of instrumentations pinned to an expected version range of the module
  new Map<string, Array<Pick<ESMInstrumentation, 'version' | 'hook'>>>();

export interface CJSInstrumentation {
  moduleName: string;
  subPath: string;
  version: string;
  hook: HookFn;
}

export interface ESMInstrumentation {
  moduleName: string;
  version: string;
  hook: HookFn;
}

export function addCJSInstrumentation({
  moduleName,
  subPath,
  version,
  hook,
}: CJSInstrumentation) {
  const instrumentations = (global as any)[symCJSInstrumentations];

  const instrumentationLookupKey = `${moduleName}@${subPath}`;

  if (!instrumentations.has(instrumentationLookupKey)) {
    instrumentations.set(instrumentationLookupKey, []);
  }

  instrumentations.get(instrumentationLookupKey)!.push({
    version,
    hook,
  });
}

export function addESMInstrumentation({
  moduleName,
  version,
  hook,
}: ESMInstrumentation) {
  const instrumentations = (global as any)[symESMInstrumentations];

  if (!instrumentations.has(moduleName)) {
    instrumentations.set(moduleName, []);
  }
  instrumentations.get(moduleName)!.push({
    version,
    hook,
  });
}

export function getESMInstrumentedModules(): string[] {
  const instrumentations = (global as any)[symESMInstrumentations];
  return Array.from(instrumentations.keys());
}

export function getCJSInstrumentedTargets(): Array<
  Pick<CJSInstrumentation, 'moduleName' | 'subPath'>
> {
  const instrumentations = (global as any)[symCJSInstrumentations];
  return Array.from(instrumentations.keys() as Iterable<string>, key => {
    // Keys are `${moduleName}@${subPath}`. The separator is the first `@`
    // after the leading one a scoped name starts with.
    const at = key.indexOf('@', key.startsWith('@') ? 1 : 0);
    return {moduleName: key.slice(0, at), subPath: key.slice(at + 1)};
  });
}

const explicitlyRegistered = globalSingleton(
  '_weave_explicitly_registered_integrations',
  () => new Set<string>()
);

/**
 * Record that the app wired `moduleName` up itself, e.g. with `wrapOpenAI()`,
 * so it does not depend on the require hook. Implicit patching must not call
 * this.
 */
export function markRegisteredExplicitly(moduleName: string): void {
  explicitlyRegistered.add(moduleName);
}

export function isRegisteredExplicitly(moduleName: string): boolean {
  return explicitlyRegistered.has(moduleName);
}
