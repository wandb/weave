import path from 'path';
import semifies from 'semifies';

import {
  getCJSInstrumentedTargets,
  getLoadOrderDependencyOwners,
  isLoadOrderWarningSuppressed,
  isLoadOrderWarningSuppressedForFile,
} from '../integrations/instrumentations';
import state from '../state';
import {requirePackageJson} from './npmModuleUtils';
import {warnOnce} from './warnOnce';

/**
 * Warn about libraries a CommonJS app loaded before `weave`.
 *
 * Implicit CJS patching works by replacing `Module.prototype.require`, so a
 * library resolved before that hook went in handed the app its unpatched
 * exports, and the app keeps calling those.
 */
export function warnIfLoadedBeforeWeave(): void {
  // An older copy of the SDK sharing this process can own the state singleton
  // and not carry the field.
  const loadedBeforeHook = state.modulesLoadedBeforeCjsHook ?? [];
  if (loadedBeforeHook.length === 0) {
    return;
  }
  for (const {moduleName, subPath, versions} of getCJSInstrumentedTargets()) {
    if (isLoadOrderWarningSuppressed(moduleName)) {
      continue;
    }
    // Match the exact file the hook patches, not the package directory: some
    // other file of the package loaded early does not stop the entry point
    // from being patched. Suffix rather than equality because pnpm keeps the
    // real files under `.pnpm/<pkg>@<ver>/node_modules/<pkg>`.
    const entry = path.join(...subPath.split('/'));
    const patched = path.join(path.sep, 'node_modules', moduleName, entry);
    const owners = getLoadOrderDependencyOwners(moduleName);
    const unpatched = loadedBeforeHook.filter(
      file =>
        file.endsWith(patched) &&
        !isLoadOrderWarningSuppressedForFile(file) &&
        !loadedOnlyBy(file, owners) &&
        isPatchableVersion(file.slice(0, -(entry.length + 1)), versions)
    );
    if (unpatched.length === 0) {
      continue;
    }
    warnOnce(
      `weave-loaded-after-${moduleName}`,
      `Weave: '${moduleName}' was loaded before 'weave', so automatic patching did not apply to it. ` +
        `In CommonJS, require('weave') before the library. ` +
        `Ignore this if you register the integration explicitly.`
    );
  }
}

/**
 * Whether a copy of the SDK that is installing its CJS hook should take the
 * load-order snapshot: not if a copy already did, and not if another weave
 * copy's hook is the active require, because that hook saw every later load.
 * An older SDK may have created the shared state without the field.
 */
export function shouldSnapshotRequireCache(
  snapshot: string[] | null | undefined,
  activeRequire: {name: string}
): boolean {
  return snapshot == null && activeRequire.name !== 'patchedRequire';
}

/**
 * For each file in `cache`, the package of every file that had required it so
 * far. The loader stores this next to its snapshot; see
 * `state.requirerPackagesBeforeCjsHook`.
 */
export function requirerPackagesOf(
  cache: NodeJS.Dict<NodeModule>,
  packageNameOf: (file: string) => string
): Record<string, string[]> {
  const requirers: Record<string, string[]> = {};
  for (const [file, cached] of Object.entries(cache)) {
    for (const child of cached?.children ?? []) {
      (requirers[child.filename] ??= []).push(packageNameOf(file));
    }
  }
  return requirers;
}

// True when only `owners` had required `file` before the hook, i.e. another
// package loaded it for its own use and the app never imported it itself.
function loadedOnlyBy(file: string, owners: ReadonlySet<string>): boolean {
  const requirers = state.requirerPackagesBeforeCjsHook?.[file] ?? [];
  return (
    owners.size > 0 &&
    requirers.length > 0 &&
    requirers.every(requirer => owners.has(requirer))
  );
}

// The hook skips versions outside its range in any order, so advice to reorder
// would not help them. An unreadable version keeps the warning.
function isPatchableVersion(packageDir: string, versions: string[]): boolean {
  try {
    const {version} = requirePackageJson(packageDir, []);
    return versions.some(range => semifies(version, range));
  } catch {
    return true;
  }
}
