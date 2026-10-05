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
  /**
   * The hook patches prototypes, so it also reaches references the app took
   * from this copy of the module before it ran. The loader then stops the
   * load-order warning for the file it patched.
   */
  reachesEarlierReferences?: boolean;
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
  reachesEarlierReferences,
}: CJSInstrumentation) {
  const instrumentations = (global as any)[symCJSInstrumentations];

  const instrumentationLookupKey = `${moduleName}@${subPath}`;

  if (!instrumentations.has(instrumentationLookupKey)) {
    instrumentations.set(instrumentationLookupKey, []);
  }

  instrumentations.get(instrumentationLookupKey)!.push({
    version,
    hook,
    reachesEarlierReferences,
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
  Pick<CJSInstrumentation, 'moduleName' | 'subPath'> & {versions: string[]}
> {
  const instrumentations: Map<
    string,
    Array<Pick<CJSInstrumentation, 'version'>>
  > = (global as any)[symCJSInstrumentations];
  return Array.from(instrumentations, ([key, candidates]) => {
    // Keys are `${moduleName}@${subPath}`. The separator is the first `@`
    // after the leading one a scoped name starts with.
    const at = key.indexOf('@', key.startsWith('@') ? 1 : 0);
    return {
      moduleName: key.slice(0, at),
      subPath: key.slice(at + 1),
      versions: candidates.map(candidate => candidate.version),
    };
  });
}

const loadOrderWarningSuppressed = globalSingleton(
  '_weave_load_order_warning_suppressed',
  () => new Set<string>()
);

/**
 * Stop `init()` from warning that these modules were loaded before `weave`.
 *
 * Call it when tracing no longer depends on require order: the app registered
 * the integration itself (`wrapOpenAI()`), or a registration reaches every copy
 * of the module (the global agents trace processor). A hook that only swaps
 * exports must not call it, because a reference taken before the swap stays
 * unpatched. A prototype patch reaches one copy only; its registration sets
 * `reachesEarlierReferences` instead.
 */
export function suppressLoadOrderWarning(...moduleNames: string[]): void {
  for (const moduleName of moduleNames) {
    loadOrderWarningSuppressed.add(moduleName);
  }
}

export function isLoadOrderWarningSuppressed(moduleName: string): boolean {
  return loadOrderWarningSuppressed.has(moduleName);
}

const patchedEarlyFiles = globalSingleton(
  '_weave_load_order_patched_files',
  () => new Set<string>()
);

/**
 * Stop the warning for one copy of a module: the loader patched this exact
 * file, and a compatible registration for it sets `reachesEarlierReferences`.
 * Other copies of the same package, such as one nested under another
 * dependency, still warn.
 */
export function suppressLoadOrderWarningForFile(file: string): void {
  patchedEarlyFiles.add(file);
}

export function isLoadOrderWarningSuppressedForFile(file: string): boolean {
  return patchedEarlyFiles.has(file);
}

const dependencyOwners = globalSingleton(
  '_weave_load_order_dependency_owners',
  () => new Map<string, Set<string>>()
);

/**
 * Like `suppressLoadOrderWarning()`, but only while nothing except
 * `ownerPackages` had required the module before `weave`. For an integration
 * that loads other hooked modules for its own use, such as ADK loading
 * `@google/genai`. If the app required the module itself, the warning stays.
 */
export function suppressLoadOrderWarningWhenLoadedBy(
  ownerPackages: string[],
  moduleNames: string[]
): void {
  for (const moduleName of moduleNames) {
    const owners = dependencyOwners.get(moduleName) ?? new Set<string>();
    for (const ownerPackage of ownerPackages) {
      owners.add(ownerPackage);
    }
    dependencyOwners.set(moduleName, owners);
  }
}

export function getLoadOrderDependencyOwners(
  moduleName: string
): ReadonlySet<string> {
  return dependencyOwners.get(moduleName) ?? new Set<string>();
}
