// @ts-ignore-file This file is compiled as ESM via tsconfig.instrument.json

const satisfies = require('semifies');
const {register} = require('node:module');
const {pathToFileURL} = require('node:url');

import {Hook, createAddHookMessageChannel} from 'import-in-the-middle';
require('../integrations/hooks');

import {
  getESMInstrumentedModules,
  symESMInstrumentations,
  ESMInstrumentation,
  symESMCache,
} from '../integrations/instrumentations';
import {requirePackageJson} from '../utils/npmModuleUtils';
import semifies from 'semifies';

const {registerOptions, waitForAllMessagesAcknowledged} =
  createAddHookMessageChannel();

register(
  'import-in-the-middle/hook.mjs',
  pathToFileURL(__filename),
  registerOptions
);

(async () => {
  await waitForAllMessagesAcknowledged();

  if (satisfies(process.versions.node, '>=14.13.1')) {
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
