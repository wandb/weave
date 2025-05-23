'use strict';
import path from 'path';
import instrumentations, {
  Instrumentation,
} from '../integrations/instrumentations';

const parse: (filePath: string) => {
  name: string;
  baseDir: string;
  path: string;
} = require('module-details-from-path');

export let reset = () => {};

interface CacheEntry {
  originalExports: any;
  patchedExports: any;
}

let patching = Object.create(null);

const cachedModules = new Map<string, CacheEntry>();
const passThroughModules = new Set<string>();

if (typeof module !== 'undefined' && module.exports) {
  // CommonJS environment
  const Module = require('module');
  const originalRequire = Module.prototype.require;

  function patchedRequire(this: any, request: any) {
    let filename;
    try {
      filename = Module._resolveFilename(request, this);
    } catch (resolveErr) {
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
    const {name, baseDir, path: subPath} = parsed;

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
        | Pick<Instrumentation, 'version' | 'hook'>
        | undefined;

      for (const instrumentationCandiate of instrumentations.get(
        instrumentationLookupKey
      ) || []) {
        // TODO check if the version is compatible with the current version of the module
        // if (semver.satisfies(version, instrumentationCandiate.version)) {
        instrumentation = instrumentationCandiate;
        break;
        // }
      }

      if (!instrumentation) {
        // Non of the instrumentations matched (maybe the version is not compatible), so we pass through the module
        passThroughModules.add(filename);
        return originalExports;
      }

      const hook = instrumentation.hook;

      const cacheEntry: CacheEntry = {
        originalExports,
        patchedExports: hook(originalExports, name, baseDir),
      };

      cachedModules.set(filename, cacheEntry);
      delete patching[filename];
    }
    return cachedModules.get(filename)!.patchedExports;
  }

  reset = () => {
    Module.prototype.require = originalRequire;
  };

  Module.prototype.require = patchedRequire as any;
} else {
  // ESM mode, do nothing
}
