import fs from 'fs';
import os from 'os';
import path from 'path';

import state from '../../state';
import {
  reachesEarlierReferences,
  reset,
  snapshotRequireCache,
} from '../../utils/commonJSLoader';

const root = fs.mkdtempSync(path.join(os.tmpdir(), 'weave-cjs-loader-'));
const nodeModules = path.join(root, 'node_modules');

// Writes <packageDir>/package.json and the file, and returns the file's path.
function installed(packageDir: string, name: string, file: string): string {
  const filePath = path.join(packageDir, ...file.split('/'));
  fs.mkdirSync(path.dirname(filePath), {recursive: true});
  fs.writeFileSync(
    path.join(packageDir, 'package.json'),
    JSON.stringify({name, version: '1.0.0'})
  );
  fs.writeFileSync(filePath, '');
  return filePath;
}

function pkg(name: string, file: string): string {
  return installed(path.join(nodeModules, ...name.split('/')), name, file);
}

// A require.cache with an entry for each file and the files it required.
function cacheOf(required: Record<string, string[]>): NodeJS.Dict<NodeModule> {
  return Object.fromEntries(
    Object.entries(required).map(([file, children]) => [
      file,
      {children: children.map(filename => ({filename}))},
    ])
  ) as unknown as NodeJS.Dict<NodeModule>;
}

const ownLoader = installed(
  path.join(root, 'this-weave'),
  'weave',
  'dist/utils/commonJSLoader.js'
);

beforeEach(() => {
  state.modulesLoadedBeforeCjsHook = null;
  state.requirerPackagesBeforeCjsHook = null;
});

afterAll(() => {
  reset();
  fs.rmSync(root, {recursive: true, force: true});
});

describe('snapshotRequireCache', () => {
  test('records what was loaded and the package of each requirer', () => {
    const genai = pkg('@google/genai', 'dist/node/index.cjs');
    // A linked package's real path is outside node_modules; its package.json names it.
    const linkedAdk = installed(
      path.join(root, 'packages', 'adk'),
      '@google/adk',
      'index.js'
    );
    const appFile = installed(path.join(root, 'app'), 'my-app', 'src/app.js');
    const fromPnpm = installed(
      path.join(nodeModules, '.pnpm', 'x@1.0.0', 'node_modules', '@scope', 'x'),
      '@scope/x',
      'lib/index.js'
    );

    snapshotRequireCache(
      cacheOf({
        [linkedAdk]: [genai],
        [appFile]: [genai],
        [fromPnpm]: [genai],
        [genai]: [],
      }),
      ownLoader
    );

    expect(state.modulesLoadedBeforeCjsHook).toEqual([
      linkedAdk,
      appFile,
      fromPnpm,
      genai,
    ]);
    expect(state.requirerPackagesBeforeCjsHook).toEqual({
      [genai]: ['@google/adk', 'my-app', '@scope/x'],
    });
  });

  test('keeps the snapshot an earlier copy took', () => {
    state.modulesLoadedBeforeCjsHook = ['taken earlier'];
    snapshotRequireCache(cacheOf({[pkg('openai', 'index.js')]: []}), ownLoader);
    expect(state.modulesLoadedBeforeCjsHook).toEqual(['taken earlier']);
  });

  test('takes none after another weave copy installed its hook, linked or not', () => {
    const openai = pkg('openai', 'index.js');
    const installedCopy = pkg('weave', 'dist/utils/commonJSLoader.js');
    const linkedCopy = installed(
      path.join(root, 'weave-checkout'),
      'weave',
      'dist/utils/commonJSLoader.js'
    );
    for (const otherLoader of [installedCopy, linkedCopy]) {
      snapshotRequireCache(
        cacheOf({[otherLoader]: [], [openai]: []}),
        ownLoader
      );
      expect(state.modulesLoadedBeforeCjsHook).toBeNull();
    }
  });

  test('ignores its own loader and a look-alike file of another package', () => {
    const lookAlike = pkg('other-sdk', 'dist/utils/commonJSLoader.js');
    const openai = pkg('openai', 'index.js');
    snapshotRequireCache(
      cacheOf({[ownLoader]: [], [lookAlike]: [], [openai]: []}),
      ownLoader
    );
    expect(state.modulesLoadedBeforeCjsHook).toEqual([
      ownLoader,
      lookAlike,
      openai,
    ]);
  });
});

test('a compatible entry marks the patch as reaching earlier references', () => {
  // An older weave copy registered the same target first, without the flag.
  const older = {version: '>= 0.52.0'};
  const current = {version: '>= 0.52.0', reachesEarlierReferences: true};
  expect([
    reachesEarlierReferences([older, current], '0.60.0'),
    reachesEarlierReferences([older, current], '0.40.0'),
    reachesEarlierReferences([older], '0.60.0'),
    reachesEarlierReferences(undefined, '0.60.0'),
  ]).toEqual([true, false, false, false]);
});
