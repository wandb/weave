import * as esbuild from 'esbuild';
import {polyfillNode} from 'esbuild-plugin-polyfill-node';

const baseConfig = {
  entryPoints: ['src/index.ts'],
  bundle: true,
  platform: 'browser',
  target: ['es2020'],
  plugins: [
    polyfillNode({
      polyfills: {
        fs: true,
        crypto: true
      }
    })
  ],
  format: 'esm',
  sourcemap: true,
  minify: true,
  metafile: true,
  define: {
    'process.env.NODE_ENV': '"production"'
  },
  external: [
    'openai',
    'cli-progress',
  ],
  alias: {
    'cli-progress': './src/browser.ts'
  },
  bundle: true,
  mainFields: ['browser', 'module', 'main'],
  resolveExtensions: ['.ts', '.js']
};

// Build for production (minified)
await esbuild.build({
  ...baseConfig,
  outfile: 'dist/weave.min.js'
});

// Build for development (unminified)
await esbuild.build({
  ...baseConfig,
  minify: false,
  outfile: 'dist/weave.js'
});