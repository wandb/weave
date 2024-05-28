/// <reference types="vitest" />
import * as path from 'path';

import {defineConfig} from 'vite';
import svgr from 'vite-plugin-svgr';
import react from '@vitejs/plugin-react';
import blockCjsPlugin from './vite-plugin-block-cjs';
import fileUrls from './vite-plugin-file-urls';
import {visualizer} from 'rollup-plugin-visualizer';
import fs from 'fs';

// https://vitejs.dev/config/
export default defineConfig(({mode, command}) => {
  /* eslint-disable node/no-process-env */

  /**
   * NOTE: the lint rule here is disabled because this file only runs inside of
   * build tooling, and it needs direct access to env variables in order to
   * configure itself. DO NOT use process.env directly in frontend code.
   *
   * If you need environment variables in the app, look at generate-env-js.bash
   * and app/src/config.ts
   */

  const host = process.env.HOST;
  const port = process.env.PORT
    ? Number.parseInt(process.env.PORT, 10)
    : undefined;

  const showVisualizer = process.env.VISUALIZER;

  let https: boolean | {key: Buffer; cert: Buffer} = false;
  if (process.env.VITE_HTTPS_KEY_PATH && process.env.VITE_HTTPS_CERT_PATH) {
    https = {
      key: fs.readFileSync(process.env.VITE_HTTPS_KEY_PATH),
      cert: fs.readFileSync(process.env.VITE_HTTPS_CERT_PATH),
    };
  }

  const hmrPort = process.env.HMR_PORT
    ? Number.parseInt(process.env.HMR_PORT, 10)
    : undefined;
  /* eslint-enable */

  const alias = [
    // Allow absolute imports inside this package
    {
      find: /^@wandb\/weave\/(.*)$/,
      replacement: `${__dirname}/src/$1`,
    },
    {
      find: /^react-datetime$/,
      replacement: 'react-datetime/dist/react-datetime.umd.js',
    },
    {
      find: 'react-virtualized',
      replacement: 'react-virtualized/dist/commonjs/',
    },
    {find: 'plotly.js', replacement: 'plotly.js-dist-min'},
    {
      find: 'react-vis/dist/style.css',
      replacement: `${__dirname}/node_modules/react-vis/dist/style.css`,
    },
    {find: /^react-vis$/, replacement: 'react-vis/dist/index.js'},
    {find: 'dagre', replacement: 'dagre/dist/dagre.min.js'},
    {
      find: 'type/value/is',
      replacement: `${__dirname}/node_modules/type/value/is`,
    },
    {
      find: 'type/value/ensure',
      replacement: `${__dirname}/node_modules/type/value/ensure`,
    },
    {
      find: 'type/plain-function/ensure',
      replacement: `${__dirname}/node_modules/type/plain-function/ensure`,
    },
    {
      find: 'type/plain-function/is',
      replacement: `${__dirname}/node_modules/type/plain-function/is`,
    },
    {find: 'type', replacement: `component-type`},
    {find: 'each', replacement: `component-each`},
    {find: 'unserialize', replacement: 'yields-unserialize'},
  ];

  const plugins: any = [svgr(), blockCjsPlugin, fileUrls];

  // enable the react plugin in dev only, for fast refresh

  // we're not using it in prod builds right now because it requires Babel,
  // which is slow. To make sure the behavior is the same in both envs, we're
  // NOT using the new JSX runtime in dev (so it should be equivalent to prod,
  // where JSX transpilation is handled by esbuild, which doesn't support the
  // new runtime yet)
  if (mode !== 'production') {
    plugins.unshift(
      react({
        jsxRuntime: 'classic',
      })
    );
  }

  if (showVisualizer) {
    plugins.push(visualizer());
  }

  return {
    plugins,
    base:
      mode === 'production' && command !== 'serve'
        ? // eslint-disable-next-line node/no-process-env
          process.env.URL_BASE ?? '/__frontend/'
        : undefined,
    resolve: {
      alias,
      dedupe: ['react', '@material-ui/styles', 'mdast-util-to-hast'],
    },
    optimizeDeps: {
      entries: './index.html',
      include: [
        'd',
        'yaml-ast-parser-custom-tags',
        'js-yaml',
        'graphlib',
        'is-buffer',
        'mdast-util-to-hast',
      ],
      esbuildOptions: {
        define: {
          global: 'globalThis',
        },
      },
    },
    server: {
      host,
      port,
      https,
      // for invoker_local we need the frontend to proxy back to the local
      // container NOTE: if you update values here, you need to update
      // onprem/local/files/etc/nginx/sites-available/*
      hmr: {clientPort: hmrPort ?? port},
      // Route requests to /__weave to Weave server on fixed port.
      // I think this fixes direct_url_as_of in file.py
      proxy: {
        '^/__weave/.*': {
          target: 'http://localhost:9994',
          secure: false,
          changeOrigin: true,
        },
        // Dynamically generated env.js
        '^.*/__frontend/env.js': {
          target: 'http://localhost:9994',
          secure: false,
          changeOrigin: true,
        },
        // General pattern matcher for static assets
        '^.*/__frontend/(.*.js|.*.ico|.*.js.map)': {
          target: 'http://localhost:9994',
          secure: false,
          changeOrigin: true,
        },
      },
    },
    preview: {
      host,
      port,
      https: false,
    },

    build: {
      target: 'es2021',
      outDir: './build',
      sourcemap: true,
    },
    envPrefix: 'REACT_APP_',
    cacheDir: path.join(__dirname, '.vite_cache'),
    assetsInclude: ['**/tree-sitter-weave.wasm', '**/tree-sitter.wasm'],
    test: {
      globals: true,
      environment: 'jsdom',
      setupFiles: ['./src/setupTests.ts'],
      alias: [
        {
          find: /.*\.wasm$/,
          replacement: `${__dirname}/mockTreeSitterForTest.js`,
        },
      ],
    },
  };
});
