import path from 'path';

import {getCJSInstrumentedTargets} from '../integrations/instrumentations';
import state from '../state';
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
  for (const {moduleName, subPath} of getCJSInstrumentedTargets()) {
    // Match the exact file the hook patches, not the package directory: some
    // other file of the package loaded early does not stop the entry point
    // from being patched. Suffix rather than equality because pnpm keeps the
    // real files under `.pnpm/<pkg>@<ver>/node_modules/<pkg>`.
    const patched = path.join(
      path.sep,
      'node_modules',
      moduleName,
      ...subPath.split('/')
    );
    if (!loadedBeforeHook.some(file => file.endsWith(patched))) {
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
