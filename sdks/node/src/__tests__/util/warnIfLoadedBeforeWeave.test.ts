import fs from 'fs';
import os from 'os';
import path from 'path';

import '../../integrations/hooks';
import {
  getLoadOrderDependencyOwners,
  suppressLoadOrderWarning,
  suppressLoadOrderWarningForFile,
  suppressLoadOrderWarningWhenLoadedBy,
} from '../../integrations/instrumentations';
import state from '../../state';
import {nearestPackageName} from '../../utils/npmModuleUtils';
import {
  requirerPackagesOf,
  shouldSnapshotRequireCache,
  warnIfLoadedBeforeWeave,
} from '../../utils/warnIfLoadedBeforeWeave';

const parse: (file: string) => {name: string} | undefined =
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  require('module-details-from-path');

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
  test('loading weave declares the packages that load hooked modules themselves', () => {
    expect([...getLoadOrderDependencyOwners('@google/genai')]).toEqual([
      '@google/adk',
    ]);
    expect([...getLoadOrderDependencyOwners('openai')]).toEqual([
      '@openai/agents-openai',
    ]);
  });

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

  test('records the package of each requirer, including linked ones', () => {
    // A linked package's real path is outside node_modules; its package.json names it.
    const linkedAdk = installed(
      path.join(root, 'packages', 'adk'),
      '@google/adk',
      '1.2.0',
      'index.js'
    );
    const appFile = installed(root, 'my-app', '1.0.0', 'src/app.js');
    const target = pkg('@google/genai', '1.30.0', 'dist/node/index.cjs');
    const fromPnpm = installed(
      path.join(nodeModules, '.pnpm', 'x@1.0.0', 'node_modules', '@scope', 'x'),
      '@scope/x',
      '1.0.0',
      'lib/index.js'
    );
    const child = {filename: target} as NodeModule;
    const cache = {
      [linkedAdk]: {children: [child]},
      [appFile]: {children: [child]},
      [fromPnpm]: {children: [child]},
      [target]: {children: []},
    } as unknown as NodeJS.Dict<NodeModule>;

    expect(
      requirerPackagesOf(
        cache,
        file => parse(file)?.name ?? nearestPackageName(path.dirname(file))
      )
    ).toEqual({[target]: ['@google/adk', 'my-app', '@scope/x']});
  });

  test('skips only the copy the loader patched, not another copy', () => {
    const warn = jest.spyOn(console, 'warn').mockImplementation();
    const patchedCopy = installed(
      path.join(nodeModules, 'dep', 'node_modules', '@openai', 'agents'),
      '@openai/agents',
      '0.12.0',
      'dist/index.js'
    );
    const appCopy = pkg('@openai/agents', '0.12.0', 'dist/index.js');
    suppressLoadOrderWarningForFile(patchedCopy);
    state.requirerPackagesBeforeCjsHook = {};

    state.modulesLoadedBeforeCjsHook = [patchedCopy];
    warnIfLoadedBeforeWeave();
    expect(warn.mock.calls).toEqual([]);

    state.modulesLoadedBeforeCjsHook = [patchedCopy, appCopy];
    warnIfLoadedBeforeWeave();
    expect(warn.mock.calls).toEqual([[warning('@openai/agents')]]);
    warn.mockRestore();
  });

  test('keeps the warning when the package version cannot be read', () => {
    const warn = jest.spyOn(console, 'warn').mockImplementation();
    const noPackageJson = path.join(
      root,
      'bare',
      'node_modules',
      '@anthropic-ai',
      'claude-agent-sdk',
      'sdk.mjs'
    );
    fs.mkdirSync(path.dirname(noPackageJson), {recursive: true});
    fs.writeFileSync(noPackageJson, '');
    state.modulesLoadedBeforeCjsHook = [noPackageJson];
    state.requirerPackagesBeforeCjsHook = {};

    warnIfLoadedBeforeWeave();

    expect(warn.mock.calls).toEqual([
      [warning('@anthropic-ai/claude-agent-sdk')],
    ]);
    warn.mockRestore();
  });

  test('stays quiet without a snapshot', () => {
    const warn = jest.spyOn(console, 'warn').mockImplementation();
    for (const snapshot of [null, undefined]) {
      state.modulesLoadedBeforeCjsHook = snapshot as unknown as null;
      warnIfLoadedBeforeWeave();
    }
    expect(warn.mock.calls).toEqual([]);
    warn.mockRestore();
  });

  test('a copy snapshots only if no copy did and no weave hook is active', () => {
    const nodeRequire = {name: 'require'};
    const weaveHook = {name: 'patchedRequire'};
    expect([
      shouldSnapshotRequireCache(null, nodeRequire), // first copy
      shouldSnapshotRequireCache(undefined, nodeRequire), // older ESM copy first
      shouldSnapshotRequireCache([], weaveHook), // second copy of this version
      shouldSnapshotRequireCache(undefined, weaveHook), // older CJS copy first
      shouldSnapshotRequireCache(null, weaveHook), // SDK without shared state first
    ]).toEqual([true, true, false, false, false]);
  });
});
