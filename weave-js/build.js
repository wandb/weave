import esbuild from 'esbuild';
import svgr from 'esbuild-plugin-svgr';
import {wasmLoader} from 'esbuild-plugin-wasm';
import {lessLoader} from 'esbuild-plugin-less';
const markAssetsExternal = () => ({
  name: 'mark assets external',
  setup(build) {
    build.onResolve({filter: /\.(woff2?|ttf|eot|png)((\?|#).*)?$/}, args => {
      return {path: args.path, external: true};
    });

    // TODO: should actually resolve to the file path without the # or ?
    build.onResolve({filter: /\.svg((\?|#).*)?$$/}, args => {
      return {path: args.path, external: true};
    });
  },
});

await esbuild.build({
  entryPoints: ['src/index.ts', 'src/entrypoint.tsx'],
  outdir: 'dist',
  bundle: true,
  plugins: [svgr({}), lessLoader(), markAssetsExternal()],
  external: [
    'buffer',
    'path',
    'fs',
    'stream',
    'assert',
    'GOT.func',
    '*tree-sitter.wasm',
    '*tree-sitter-weave.wasm',
  ],
  format: 'esm',
});
