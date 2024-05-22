import * as path from 'path';
import pkg from 'lodash';
import {visit, Type} from 'ast-types';

Type.def('StaticBlock').finalize();

const {sortBy} = pkg;

const ALLOWED_CJS_MODULES = [
  'src', // allow absolute imports from weave root
  'react',
  'react-dom',
  'react-select',
  'lodash',
  '@segment',
  '@babel/runtime',
  '@wandb/ui',
  '@wandb/weave',
  '@wry/equality',
  '@apollo',
  'apollo-client',
  'classnames',
  'graphql-tag',
  'monaco-editor',
  'monaco-yaml',
  'mousetrap',
  'query-string',
  'decode-uri-component',
  'split-on-first',
  'querystring',
  'react-timeago',
  'styled-components',
  'memoize-one',
  'moment',
  'numeral',
  '@babylonjs',
  'cytoscape',
  'cytoscape-dagre',
  'react-datetime', // see src/compat/react-datetime
  'clsx',
  'prop-types',
  'shallowequal',

  '@emotion/stylis',
  '@emotion/unitless',
  '@emotion/weak-memoize',
  '@hypnosphi/create-react-context',
  '@material-ui/core/Avatar',
  '@material-ui/core/ButtonBase',
  '@material-ui/core/ButtonGroup',
  '@material-ui/core/Checkbox',
  '@material-ui/core/Chip',
  '@material-ui/core/Collapse',
  '@material-ui/core/Divider',
  '@material-ui/core/Fab',
  '@material-ui/core/FormControl',
  '@material-ui/core/FormGroup',
  '@material-ui/core/FormHelperText',
  '@material-ui/core/FormLabel',
  '@material-ui/core/Grow',
  '@material-ui/core/IconButton',
  '@material-ui/core/ListSubheader',
  '@material-ui/core/Paper',
  '@material-ui/core/Popper',
  '@material-ui/core/RadioGroup',
  '@material-ui/core/Tabs',
  '@material-ui/core/Tooltip',
  '@material-ui/core/Typography',
  '@material-ui/core/Zoom',
  '@material-ui/core/colors',
  '@material-ui/core/styles/createSpacing',
  '@material-ui/core/useMediaQuery',
  '@monaco-editor/loader',
  '@radix-ui/react-checkbox',
  '@radix-ui/react-dialog',
  '@radix-ui/react-dropdown-menu',
  '@radix-ui/react-radio-group',
  '@radix-ui/react-slider',
  '@radix-ui/react-switch',
  '@radix-ui/react-tabs',
  '@redux-saga/core',
  '@redux-saga/deferred',
  '@redux-saga/delay-p',
  '@semantic-ui-react/event-stack',
  '@sentry/react',
  '@sentry/integrations',
  '@sentry/tracing',
  'localforage',
  '@visx/shape',
  '@visx/stats',
  'ansi_up',
  'attr-accept',
  'autosuggest-highlight/parse',
  'autosuggest-highlight/match',
  'babylonjs-viewer-assets',
  'branch-safe-name/sanitized',
  'clone',
  'color',
  'color-string',
  'compare-versions',
  'compute-scroll-into-view',
  'copy-to-clipboard',
  'create-emotion',
  'd3',
  'd3-interpolate',
  'd3-scale',
  'deep-equal',
  'deepmerge',
  'direction',
  'dom-helpers/addClass',
  'dom-helpers/removeClass',
  'fast-deep-equal',
  'fast-json-stable-stringify',
  'fast-memoize',
  'fetch-jsonp',
  'graphql',
  'handlebars',
  'hoist-non-react-statics',
  'immer',
  'immutability-helper',
  'invariant',
  'is-buffer',
  'is-hotkey',
  'is-plain-obj',
  'is-plan-object',
  'isomorphic-unfetch',
  'is-url',
  'js-levenshtein',
  'json-stringify-pretty-compact',
  'jss-plugin-camel-case',
  'jss-plugin-default-unit',
  'jss-plugin-global',
  'jss-plugin-nested',
  'jss-plugin-props-sort',
  'jss-plugin-rule-value-function',
  'jss-plugin-vendor-prefixer',
  'katex',
  'keyboard-key',
  'lodash.isequalwith',
  'lru-cache',
  'mdast-util-gfm/to-markdown',
  'mdast-util-math',
  'mdast-util-to-string',
  'mdurl/encode.js',
  'mini-create-react-context',
  'ngl',
  'node-emoji',
  'object.entries',
  'object.values',
  'parse5/lib/parser/index.js',
  'path-to-regexp',
  'popper.js',
  'postmate',
  'prismjs',
  'react-base-table',
  'react-cytoscapejs',
  'react-draggable',
  'react-dropzone',
  'react-helmet',
  'react-hook-mousetrap',
  'react-is',
  'react-measure',
  'react-string-replace',
  'react-textarea-autosize',
  'react-use-measure',
  'react-virtualized-auto-sizer',
  'react-vis/dist/style.css?used',
  'rebber',
  'rebber-plugins/dist/type/math',
  'rebber/dist/escaper',
  'reduce-css-calc',
  'redux-saga',
  'redux-thunk',
  'rehype-katex',
  'rehype-parse',
  'rehype-raw',
  'rehype-sanitize',
  'rehype-stringify',
  'remark-emoji',
  'remark-math',
  'remark-parse',
  'remark-rehype',
  'remark-stringify',
  'style-to-object',
  'resolve-pathname',
  'tiny-invariant',
  'tiny-warning',
  'value-equal',
  'scroll-into-view-if-needed',
  'direction',
  'state-local',
  'substyle',
  'invariant',
  'symbol-observable',
  'unist-util-visit',
  'use-composed-ref',
  'use-isomorphic-layout-effect',
  'use-latest',
  'use-resize-observer',
  'vega',
  'vega-crossfilter',
  'vega-embed',
  'vega-encode',
  'vega-force',
  'vega-geo',
  'vega-hierarchy',
  'vega-label',
  'vega-lit',
  'vega-regression',
  'vega-schema-url-parser',
  'vega-themes',
  'vega-transforms',
  'vega-view-transforms',
  'vega-voronoi',
  'vega-wordcloud',
  'warning',
  'yaml',
  'zen-observable',
  'zen-observable-ts',
  'wavesurfer.js',
  'resize-observer-polyfill',
  'redux-saga',
  'redux-thunk',
  'reduce-css-calc',

  '@emotion/cache',
  '@emotion/hash',
  '@emotion/is-prop-valid',
  '@emotion/memoize',
  'branch-safe-name/sanitize',
  'delaunator',
  'downloadjs',
  'extend',
  'hyphenate-style-name',
  'is-dom',
  'is-in-browser',
  'is-plain-object',
  'jsep',
  'jszip',
  'react-diff-viewer',
  'react-inspector',
  'vega-lite',

  'pako',
  'plotly.js',

  // umap-js - Start
  'is-any-array',
  'ml-array-max',
  'ml-array-min',
  'ml-array-rescale',
  // umap-js - End

  'web-tree-sitter',

  'd3-scale',
  'diff',

  // markdown rendering
  // markdown: true deps
  'react-markdown',
  'remark-gfm',
  // markdown: peer deps
  'escape-string-regexp',
  'lowlight',
  'lowlight/lib/core',
  'refractor',
  'refractor/core',
  'yet-another-react-lightbox',
];

const repositoryRoot = path.dirname(path.dirname(__dirname));

const packageRoots = [__dirname];

const packageDepRoots = packageRoots.map(pth => `${pth}/node_modules`);

type ImportedPackage = {
  package: string;
  default?: true;
  star?: true;
  dynamic?: true;
};

type ImportersBySymbol = {
  [importer: string]: {
    default?: string[];
    star?: string[];
    dynamic?: string[];
  };
};

const getExternalDefaultOrStarImports = (ast: any) => {
  const imports: ImportedPackage[] = [];

  visit(ast, {
    visitImportDefaultSpecifier(p) {
      imports.push({
        package: p.parentPath.node.source?.value,
        default: true,
      });
      return false;
    },
    visitImportSpecifier(p) {
      if (p.node.imported.name === 'default') {
        imports.push({
          package: p.parentPath.node.source?.value,
          default: true,
        });
      }
      return false;
    },
    visitImportNamespaceSpecifier(p) {
      imports.push({package: p.parentPath.node.source?.value, star: true});
      return false;
    },
    visitImport(p) {
      const arg = p.parentPath.node.arguments[0];

      if (arg?.type === 'StringLiteral') {
        imports.push({package: arg.value, dynamic: true});
      }
      return false;
    },
  });

  return imports.filter(i => !i.package.startsWith('.'));
};

const isAllowedCJS = (pkg: string) => {
  for (const allowed of ALLOWED_CJS_MODULES) {
    if (
      pkg === allowed ||
      pkg.startsWith(allowed + '/') ||
      packageDepRoots.includes(pkg)
    ) {
      return true;
    }
  }

  return false;
};

const packageRegex = /\/(@.*?\/.*?|.*?)\//;
const filePathToPackageName = (filePath: string) => {
  let startsWithPrefix = null;
  if (packageDepRoots.includes(filePath)) {
    return filePath;
  }

  for (const root of packageDepRoots) {
    if (filePath.startsWith(root)) {
      startsWithPrefix = root;
      break;
    }
  }

  if (!startsWithPrefix) {
    // this doesn't look like a dependency -- if it's something in our own app,
    // we want to see the full path
    return filePath;
  }

  const trimmed = filePath.slice(`${startsWithPrefix}`.length);

  if (!trimmed.match(packageRegex)) {
    console.log('ERR', filePath, trimmed);
  }
  return trimmed.match(packageRegex)[1];
};

const cjsErrorMessage = (
  foundPackages: any
) => `Some new CommonJS dependencies were detected. Because of dev -> prod inconsistencies in Vite when handling CJS, CJS dependencies are blocked by default.

Here are the new dependencies, along with the modules importing them: ${JSON.stringify(
  foundPackages,
  undefined,
  2
)}

Please run invoker_fe_prod_preview.ini and check that each dependency works as expected, then add them to ALLOWED_CJS_MODULES in vite-plugin-block-cjs.ts.

The error that motivated this check is https://github.com/vitejs/vite/issues/4209 (so if it's fixed, consider tearing this out)
`;

const unverifiedCjsModules = new Set<string>();
const externalImportsToCheck: ImportersBySymbol = {};
const blockCjsPlugin = {
  name: 'cjs-scan',
  enforce: 'post' as const,
  moduleParsed({id, ast, meta}) {
    if (meta?.commonjs?.isCommonJS && !isAllowedCJS(id)) {
      unverifiedCjsModules.add(filePathToPackageName(id));
    } else {
      const potentiallyDangerousImports = getExternalDefaultOrStarImports(ast);

      // the following external modules were imported either:
      //
      // - as default
      // - using *
      // - dynamically
      //
      // we should check them -- if they're CommonJS we have to make sure they compiled correctly
      for (const importedModule of potentiallyDangerousImports) {
        if (
          id.endsWith('?commonjs-proxy') &&
          id.includes(importedModule.package)
        ) {
          // some commonjs modules are imported through a proxy, which counts as an import
          // reporting this would just be noise
          continue;
        }

        if (!externalImportsToCheck[importedModule.package]) {
          externalImportsToCheck[importedModule.package] = {};
        }

        const idToLog = id.startsWith(repositoryRoot)
          ? id.slice(repositoryRoot.length)
          : id;

        if (importedModule.default) {
          externalImportsToCheck[importedModule.package].default = [
            ...(externalImportsToCheck[importedModule.package].default || []),
            idToLog,
          ];
        }

        if (importedModule.star) {
          externalImportsToCheck[importedModule.package].star = [
            ...(externalImportsToCheck[importedModule.package].star || []),
            idToLog,
          ];
        }

        if (importedModule.dynamic) {
          externalImportsToCheck[importedModule.package].dynamic = [
            ...(externalImportsToCheck[importedModule.package].dynamic || []),
            idToLog,
          ];
        }
      }
    }
  },

  buildEnd() {
    // now we've got a map of all external imports that could trip up the CJS compiler,
    // along with a list of verified and unverified CJS modules

    const dangerousImportsFound: ImportersBySymbol = {};

    for (const [module, importers] of Object.entries(externalImportsToCheck)) {
      if (!isAllowedCJS(module)) {
        // we have not verified this module -- we need to make sure it's safe
        dangerousImportsFound[module] = importers;
      }
    }

    const dangerousImportsList = Object.entries(dangerousImportsFound);
    // if (dangerousImportsList.length > 0) {
    //   throw new Error(
    //     cjsErrorMessage(
    //       Object.fromEntries(
    //         sortBy(dangerousImportsList, ([module]) => {
    //           return module;
    //         })
    //       )
    //     )
    //   );
    // }
  },
};

export default blockCjsPlugin;
