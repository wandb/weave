import fs from 'fs';
import os from 'os';
import path from 'path';

import '../../integrations/hooks';
import {
  suppressLoadOrderWarning,
  suppressLoadOrderWarningWhenLoadedBy,
} from '../../integrations/instrumentations';
import state from '../../state';
import {warnIfLoadedBeforeWeave} from '../../utils/warnIfLoadedBeforeWeave';

const root = fs.mkdtempSync(path.join(os.tmpdir(), 'weave-load-order-'));
const nodeModules = path.join(root, 'node_modules');
// Requirers are recorded by package; '' is a file outside node_modules.
const APP = '';

// Writes <packageDir>/package.json and the file, and returns the file's path.
function installed(
  packageDir: string,
  name: string,
  version: string,
  file: string
): string {
  const filePath = path.join(packageDir, ...file.split('/'));
  fs.mkdirSync(path.dirname(filePath), {recursive: true});
  fs.writeFileSync(
    path.join(packageDir, 'package.json'),
    JSON.stringify({name, version})
  );
  fs.writeFileSync(filePath, '');
  return filePath;
}

function pkg(name: string, version: string, file: string): string {
  return installed(
    path.join(nodeModules, ...name.split('/')),
    name,
    version,
    file
  );
}

function warning(moduleName: string): string {
  return (
    `Weave: '${moduleName}' was loaded before 'weave', so automatic patching did not apply to it. ` +
    `In CommonJS, require('weave') before the library. ` +
    `Ignore this if you register the integration explicitly.`
  );
}

afterAll(() => fs.rmSync(root, {recursive: true, force: true}));

describe('warnIfLoadedBeforeWeave', () => {
  test('warns once for each library the app loaded before the hook', () => {
    const warn = jest.spyOn(console, 'warn').mockImplementation();
    const openai = pkg('openai', '5.0.0', 'index.js');
    // pnpm keeps the real files under .pnpm/<pkg>@<version>/node_modules/<pkg>.
    const genai = installed(
      path.join(
        nodeModules,
        '.pnpm',
        '@google+genai@1.30.0',
        'node_modules',
        '@google',
        'genai'
      ),
      '@google/genai',
      '1.30.0',
      'dist/node/index.cjs'
    );
    state.modulesLoadedBeforeCjsHook = [
      openai,
      pkg('openai', '5.0.0', 'version.js'),
      genai,
      // Another file of a package does not stop its entry point from being patched.
      pkg('@anthropic-ai/sdk', '0.60.0', 'version.js'),
    ];
    // The agents packages load openai too, but so did the app.
    suppressLoadOrderWarningWhenLoadedBy(['@openai/agents-openai'], ['openai']);
    state.requirerPackagesBeforeCjsHook = {
      [openai]: [APP, '@openai/agents-openai'],
      [genai]: [APP],
    };

    warnIfLoadedBeforeWeave();

    expect(warn.mock.calls).toEqual([
      [warning('openai')],
      [warning('@google/genai')],
    ]);
    warn.mockRestore();
  });

  test('skips libraries whose tracing does not depend on the load order', () => {
    const warn = jest.spyOn(console, 'warn').mockImplementation();
    const realtime = pkg('@openai/agents-realtime', '0.11.0', 'dist/index.js');
    const anthropic = pkg('@anthropic-ai/sdk', '0.60.0', 'index.js');
    state.modulesLoadedBeforeCjsHook = [
      // Registered explicitly.
      pkg('@google/adk', '1.2.0', 'dist/cjs/index.js'),
      // Loaded only by the agents package, for its own use.
      realtime,
      // Below the hook's version range, so reordering would not patch it.
      pkg('@anthropic-ai/claude-agent-sdk', '0.1.0', 'sdk.mjs'),
      anthropic,
    ];
    suppressLoadOrderWarning('@google/adk');
    suppressLoadOrderWarningWhenLoadedBy(
      ['@openai/agents'],
      ['@openai/agents-realtime']
    );
    state.requirerPackagesBeforeCjsHook = {
      [realtime]: ['@openai/agents'],
      [anthropic]: [APP],
    };

    warnIfLoadedBeforeWeave();

    expect(warn.mock.calls).toEqual([[warning('@anthropic-ai/sdk')]]);
    warn.mockRestore();
  });
});
