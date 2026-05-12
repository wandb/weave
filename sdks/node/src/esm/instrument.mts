// Preload entry for Weave ESM host support.
//
// Invoked via `node --import=weave/instrument <entry>`. The `.mts` extension
// marks this file as ESM-only — TypeScript always emits it as `.mjs`. The
// CJS target's tsconfig also excludes `src/esm/**` so it is never even
// considered by the CJS build pass. The `package.json` `"./instrument"`
// exports map only routes the `import` condition, so consumers always get
// the ESM build.
//
// Its job is to register an `import-in-the-middle` loader hook so the host's
// ESM graph can be patched as modules are resolved.

import {register} from 'node:module';
import {Hook, createAddHookMessageChannel} from 'import-in-the-middle';
import {
  getESMInstrumentedModules,
  symESMInstrumentations,
  ESMInstrumentation,
  symESMCache,
} from '../integrations/instrumentations';
import {requirePackageJson} from '../utils/npmModuleUtils';
import semifies from 'semifies';

// Side-effect import — populates the instrumentation registry that
// `instrumentations.ts` exposes on `globalThis`. Must evaluate before the
// loader hook below starts consulting that registry for matching modules.
import '../integrations/hooks';

const {registerOptions, waitForAllMessagesAcknowledged} =
  createAddHookMessageChannel();

// Pass `import.meta.url` as `register()`'s `parentURL` so it can resolve the
// bare `'import-in-the-middle/hook.mjs'` specifier through `node_modules`
// (omitting parentURL defaults to `data:/`, which can't).
register('import-in-the-middle/hook.mjs', import.meta.url, registerOptions);

(async () => {
  await waitForAllMessagesAcknowledged();

  if (semifies(process.versions.node, '>=14.13.1')) {
    const modules = getESMInstrumentedModules();

    for (const module of modules) {
      new Hook([module], (exported, name, baseDir) => {
        const cachedModule = (global as any)[symESMCache].get(module);

        if (cachedModule) {
          return cachedModule.patchedExports;
        }

        const instrumentations = (global as any)[symESMInstrumentations];
        const instrumentationsForModule = instrumentations.get(module);

        let instrumentation: Pick<
          ESMInstrumentation,
          'version' | 'hook'
        > | null = null;
        let packageJson: any;

        try {
          packageJson = requirePackageJson(baseDir!, []);
        } catch (e) {
          console.warn(
            `Cannot find package.json for ${name}, ${baseDir}. Not patching`
          );
          return exported;
        }

        if (instrumentationsForModule) {
          for (const instrumentationCandidate of instrumentationsForModule) {
            if (
              semifies(packageJson.version, instrumentationCandidate.version)
            ) {
              instrumentation = instrumentationCandidate;
              break;
            }
          }

          if (!instrumentation) {
            return exported;
          }
          const patchedExports = instrumentation.hook(exported, name, baseDir!);
          (global as any)[symESMCache].set(module, {
            originalExports: exported,
            patchedExports,
          });
          return patchedExports;
        }
      });
    }
  } else {
    console.warn(
      'ESM is not fully supported by this version of Node.js, ' +
        'so Weave will not intercept ESM loading.'
    );
  }
})();
