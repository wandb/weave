#!/usr/bin/env node
// Drives the dual CJS/ESM build by calling tsc-multi's public `build()`
// function twice — once per target — with a different tsconfig per call.
//
// This pattern gives us per-target file selection (each tsconfig has its
// own `exclude` list) plus tsc-multi's AST transformer that rewrites
// relative-import specifiers to the right extension per format. Both
// without reaching into tsc-multi internals.
//
// See `weave-sdk-dual-build-report.md` §5 for background; the rationale
// for this specific layout vs. alternatives is captured in the conversation
// log under PR 2.

import {build} from 'tsc-multi';
import {fileURLToPath} from 'node:url';
import {dirname, resolve} from 'node:path';

const cwd = resolve(dirname(fileURLToPath(import.meta.url)), '..');

await build({
  cwd,
  projects: ['tsconfig.cjs.json'],
  targets: [{extname: '.js', module: 'commonjs', moduleResolution: 'node'}],
});

await build({
  cwd,
  projects: ['tsconfig.esm.json'],
  targets: [{extname: '.mjs', module: 'esnext'}],
});
