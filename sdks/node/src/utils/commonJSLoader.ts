'use strict';
import path from 'path';
import semifies from 'semifies';

import instrumentations, {
  type CacheEntry,
  type CJSInstrumentation,
  suppressLoadOrderWarningForFile,
} from '../integrations/instrumentations';
import state from '../state';
import {nearestPackageName, requirePackageJson} from './npmModuleUtils';
import {
  requirerPackagesOf,
  shouldSnapshotRequireCache,
} from './warnIfLoadedBeforeWeave';

const parse: (filePath: string) => {
  name: string;
  basedir: string;
  path: string;
  // eslint-disable-next-line @typescript-eslint/no-require-imports
} = require('module-details-from-path');

export let reset = () => {};

// The package a file belongs to: from its `node_modules` path, or from the
// nearest package.json for a linked package or the app's own code.
function packageNameOf(file: string): string {
  return parse(file)?.name ?? nearestPackageName(path.dirname(file));
}

/**
 * Whether the hook for this file also reached references the app took before
 * it ran. Any compatible entry counts: an older weave copy may have registered
 * the same target first, without the flag, and its hook patches the same
 * prototypes.
 */
export function reachesEarlierReferences(
  candidates:
    | ReadonlyArray<
        Pick<CJSInstrumentation, 'version' | 'reachesEarlierReferences'>
      >
    | undefined,
  version: string
): boolean {
  return (candidates ?? []).some(
    candidate =>
      candidate.reachesEarlierReferences === true &&
      semifies(version, candidate.version)
  );
}

/**
 * Record what the app had loaded before this copy's hook, and which packages
 * had required each of those files, for `warnIfLoadedBeforeWeave()`.
 */
export function snapshotRequireCache(
  cache: NodeJS.Dict<NodeModule>,
  ownLoader: string
): void {
  const files = Object.keys(cache);
  if (
    !shouldSnapshotRequireCache(
      state.modulesLoadedBeforeCjsHook,
      files,
      ownLoader,
      packageNameOf
    )
  ) {
    return;
  }
  state.modulesLoadedBeforeCjsHook = files;
  state.requirerPackagesBeforeCjsHook = requirerPackagesOf(
    cache,
    packageNameOf
  );
}

const patching = Object.create(null);

const cachedModules = new Map<string, CacheEntry>();
const passThroughModules = new Set<string>();

if (typeof module !== 'undefined' && module.exports) {
  // CommonJS environment
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const Module = require('module');
  const originalRequire = Module.prototype.require;

  function patchedRequire(this: any, request: any) {
    let filename;
    try {
      filename = Module._resolveFilename(request, this);
    } catch (_resolveErr) {
      return originalRequire.apply(this, arguments as any);
    }

    const isCoreModule =
      filename.indexOf(path.sep) === -1 || filename.startsWith('node:');

    if (isCoreModule) {
      // There is no business need to patch a core module yet, directly return with the original require
      return originalRequire.apply(this, arguments as any);
    }

    const parsed = parse(filename);
    if (parsed === undefined) {
      return originalRequire.apply(this, arguments as any);
    }
    const {name, basedir, path: subPath} = parsed;

    const instrumentationLookupKey = `${name}@${subPath}`;

    // if no hook is registered for this module, use the original require
    if (!instrumentations.has(instrumentationLookupKey)) {
      return originalRequire.apply(this, arguments as any);
    }

    // if the module was already seen and no applicable hook was found, pass through the module
    if (passThroughModules.has(filename)) {
      return originalRequire.apply(this, arguments as any);
    }

    if (!cachedModules.has(filename)) {
      const isPatching = patching[filename];
      if (isPatching) {
        // If it's already patched, just return it as-is. It might be a circular call-chain coming from the call on line 72.
        return originalRequire.apply(this, arguments as any);
      } else {
        patching[filename] = true;
      }
      const originalExports = originalRequire.apply(this, arguments as any);

      let instrumentation:
        | Pick<CJSInstrumentation, 'version' | 'hook'>
        | undefined;

      let packageJson: any;
      try {
        packageJson = requirePackageJson(basedir, module.paths);
      } catch (_e) {
        console.log('Cannot find package.json for', name, basedir);
        return originalExports;
      }

      const version = packageJson.version;

      for (const instrumentationCandidate of instrumentations.get(
        instrumentationLookupKey
      ) || []) {
        // check if the version is compatible with the current version of the module
        if (semifies(version, instrumentationCandidate.version)) {
          instrumentation = instrumentationCandidate;
          break;
        }
      }

      if (!instrumentation) {
        // Non of the instrumentations matched (maybe the version is not compatible), so we pass through the module
        passThroughModules.add(filename);
        return originalExports;
      }

      const hook = instrumentation.hook;

      const cacheEntry: CacheEntry = {
        originalExports,
        patchedExports: hook(originalExports, name, basedir),
      };

      cachedModules.set(filename, cacheEntry);
      delete patching[filename];
      if (
        reachesEarlierReferences(
          instrumentations.get(instrumentationLookupKey),
          version
        )
      ) {
        suppressLoadOrderWarningForFile(filename);
      }
    }
    return cachedModules.get(filename)!.patchedExports;
  }

  reset = () => {
    Module.prototype.require = originalRequire;
  };

  // Snapshot before the swap, unfiltered: the instrumentation registry is
  // still empty here, because `index.ts` runs `./integrations/hooks`, which
  // fills it, after this module. `warnIfLoadedBeforeWeave()` filters the
  // snapshot at init() time instead.
  snapshotRequireCache(require.cache, __filename);

  Module.prototype.require = patchedRequire as any;
} else {
  // ESM mode, do nothing
}
