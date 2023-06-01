/**
 * Loads and configure the Monaco editor.
 *
 * Figured this out with a lot of experimentation -- leaving some notes here
 * for the next person who has to work on it:
 *
 * getWorker is called when Monaco needs a web worker for a language service.
 * The default implementation tries to load some external files and create
 * the workers itself. That's why we needed a plugin in Webpack: to make sure
 * those external files got generated and served.
 *
 * Vite can create workers natively, using the ?worker syntax. So we can
 * override getWorker with our own implementation and supply the workers --
 * no need for a plugin. The approach comes from: https://twitter.com/youyuxi/status/1355316139144970240
 *
 * The workers account for about half of the size of Monaco in the bundle,
 * and optional features for about a quarter. So while it's possible to strip optional
 * features out (by manually importing things that get imported in editor.main.js,
 * then importing editor.api.js instead of the entire editor.main) it just doesn't help
 * that much. I still haven't figured out how the Webpack build got Monaco down to
 * (seemingly) ~150K. I'm suspicious I may not have measured it right.
 */

import './set-window-monaco';
import 'monaco-yaml/lib/esm/monaco.contribution';
import 'monaco-editor/esm/vs/language/json/monaco.contribution';

import stringify from 'json-stringify-pretty-compact';
import type monaco from 'monaco-editor';
import * as monacoEditor from 'monaco-editor/esm/vs/editor/editor.main';
import editorWorker from 'monaco-editor/esm/vs/editor/editor.worker.js?worker&inline';
import jsonWorker from 'monaco-editor/esm/vs/language/json/json.worker.js?worker&inline';
import yamlWorker from 'monaco-yaml/lib/esm/yaml.worker.js?worker&inline';
import * as vegaSchema from 'vega/build/vega-schema.json';
import * as vegaLiteSchema from 'vega-lite/build/vega-lite-schema.json';

import sweepConfigSchema from './schemas/sweep-config-schema.json';

const jsonSchemas = [
  {
    // NOTE: the spread syntax is necessary to convert the imported JSON from a module into
    // a plain JS object -- which is required because it gets serialized to send to the worker
    // as a message
    schema: {...vegaSchema},
    uri: 'https://vega.github.io/schema/vega/v5.json',
  },
  {
    schema: {...vegaLiteSchema},
    uri: 'https://vega.github.io/schema/vega-lite/v4.json',
  },
];

const yamlSchemas = [
  {
    uri: 'http://dev.wandb.com/schema/config.json',
    schema: {...sweepConfigSchema},
    fileMatch: ['*'],
  },
];

(window as any).MonacoEnvironment = {
  globalAPI: true,
  getWorker(_: any, label: any) {
    if (label === 'json') {
      return new jsonWorker();
    }

    if (label === 'yaml') {
      return new yamlWorker();
    }

    return new editorWorker();
  },
};

monacoEditor.languages.json.jsonDefaults.setDiagnosticsOptions({
  allowComments: false,
  enableSchemaRequest: true,
  schemas: jsonSchemas,
  validate: true,
});

monacoEditor.languages.registerDocumentFormattingEditProvider('json', {
  provideDocumentFormattingEdits(
    model: monaco.editor.ITextModel,
    options: monaco.languages.FormattingOptions,
    token: monaco.CancellationToken
  ): monaco.languages.TextEdit[] {
    return [
      {
        range: model.getFullModelRange(),
        text: stringify(JSON.parse(model.getValue())),
      },
    ];
  },
});

(monacoEditor.languages as any).yaml.yamlDefaults.setDiagnosticsOptions({
  validate: true,
  schemas: yamlSchemas,
  enableSchemaRequest: true,
  format: true,
  hover: true,
  completion: true,
});
