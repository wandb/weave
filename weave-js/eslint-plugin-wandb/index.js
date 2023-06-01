const utils = require('jsx-ast-utils');
const astUtils = require('eslint-utils');
const Path = require('path');
const fs = require('fs');

function isGlobalThisReferenceOrGlobalWindow(scope, node) {
  if (!node) {
    return false;
  }
  if (scope.type === 'global' && node.type === 'ThisExpression') {
    return true;
  }
  const rootNode = node.type === 'MemberExpression' ? node.object : node;
  if (rootNode.type !== 'Identifier') {
    return false;
  }
  if (rootNode.name === 'window' || rootNode.name === 'document') {
    return true;
  }
  if (
    rootNode.name === 'globalThis' &&
    getVariableByName(scope, 'globalThis')
  ) {
    return true;
  }
  return false;
}

function skipChainExpression(node) {
  return node && node.type === 'ChainExpression' ? node.expression : node;
}

function getProjectRoot(filename) {
  const parent = Path.dirname(filename);
  if (parent === filename) {
    return parent; // returns "/" as the basecase
  }
  const files = fs.readdirSync(parent);
  const isRoot = files.some(file => file === 'package.json');
  if (!isRoot) {
    return getProjectRoot(parent);
  }
  return parent;
}

function firstArgumentName(node) {
  if (node.arguments && node.arguments.length > 0 && node.arguments[0].callee) {
    return node.arguments[0].callee.name;
  } else if (node.type === 'CallExpression') {
    return node.callee.name;
  }
}

function urlIsLikelyOk(node) {
  if (node.type === 'Literal') {
    return node.value.match(/^(\/site|http)/);
  }
  if (
    ['login', 'logout', 'urlPrefixed', 'backendHost'].indexOf(
      firstArgumentName(node)
    ) > -1
  ) {
    return true;
  }
  if (node.arguments && node.arguments.length > 0) {
    if (node.arguments[0].type === 'Literal') {
      return node.arguments[0].value.match(/^(\/site|http)/);
    } else if (node.arguments[0].type === 'Identifier') {
      return ['uploadUrl', 'fetchedUrl'].indexOf(node.arguments[0].name) > -1;
    } else if (node.arguments[0].type === 'MemberExpression') {
      return ['directUrl', 'ref'].indexOf(node.arguments[0].property.name) > -1;
    }
  }
  return false;
}

const rules = {
  'no-a-tags': {
    meta: {
      fixable: 'code',
      type: 'problem',
      docs: {
        url: 'https://github.com/wandb/core/tree/master/frontends/app/plugins/eslint-plugin-wandb#no-a-tags',
      },
    },
    create: context => ({
      JSXOpeningElement: node => {
        const nodeType = utils.elementType(node);
        const componentOverride = utils.hasProp(node.attributes, 'component');
        if (
          componentOverride &&
          utils.getPropValue(utils.getProp(node.attributes, 'component')) ===
            'a'
        ) {
          context.report({
            node,
            message:
              "You should use the Link component from react-router-dom unless you really know what you're doing!",
          });
          return;
        }
        if (nodeType === 'a') {
          const target = utils.getPropValue(
            utils.getProp(node.attributes, 'target')
          );
          const href = utils.getPropValue(
            utils.getProp(node.attributes, 'href')
          );
          const download = utils.getPropValue(
            utils.getProp(node.attributes, 'download')
          );
          // only links with targets, download or ones that start with #, http, or mailto: are allowed
          if (
            target == null &&
            download == null &&
            href != null &&
            !(
              href.startsWith('#') ||
              href.startsWith('http') ||
              href.startsWith('mailto:')
            )
          ) {
            context.report({
              node,
              message:
                "You should use the Link component from react-router-dom unless you really know what you're doing!",
            });
          } else if (target === '_blank') {
            context.report({
              node,
              message:
                'You should use the TargetBlank component from util/links/',
            });
          }
        }
      },
    }),
  },
  'no-unprefixed-urls': {
    meta: {
      fixable: 'code',
      type: 'problem',
      docs: {
        url: 'https://github.com/wandb/core/tree/master/frontends/app/plugins/eslint-plugin-wandb#no-unprefixed-urls',
      },
    },
    create: context => ({
      CallExpression: node => {
        const callee = skipChainExpression(node.callee),
          currentScope = context.getScope();

        if (callee.type === 'Identifier') {
          // fetch("/something")
          if (callee.name === 'fetch' && !urlIsLikelyOk(node)) {
            context.report({
              node,
              message:
                'Gotta use urlPrefixed(...) or backendHost(...) when using fetch',
            });
          }
        } else if (
          callee.type === 'MemberExpression' &&
          isGlobalThisReferenceOrGlobalWindow(currentScope, callee.object)
        ) {
          // window.open("/somewhere"), window.location.assign("/somewhere"), window.location.replace("/somewhere")
          const name = astUtils.getPropertyName(callee);
          if (
            ['open', 'assign', 'replace'].indexOf(name) > -1 &&
            !urlIsLikelyOk(node)
          ) {
            context.report({
              node,
              message: `Gotta use urlPrefixed(...) when using window.${name}`,
            });
          }
        }
      },
      AssignmentExpression: node => {
        const currentScope = context.getScope();
        if (
          node.left.object &&
          isGlobalThisReferenceOrGlobalWindow(
            currentScope,
            node.left.object.object
          )
        ) {
          if (node.left.property.name === 'href') {
            // window|document.location.href = "/somewhere"
            if (!urlIsLikelyOk(node.right)) {
              context.report({
                node,
                message:
                  'Gotta use urlPrefixed(...) when setting location.href',
              });
            }
          }
        }
      },
    }),
  },
  'no-relative-imports-of-files-outside-workspace-root': {
    meta: {
      type: 'problem',
      docs: {
        description:
          'Cannot perform relative imports of files outside of the package root.',
      },
      fixable: 'code',
    },

    create(context) {
      return {
        ImportDeclaration(node) {
          if (!node) {
            return false;
          }
          const filename = context.getFilename();
          const importTarget = node.source.value;
          const rootPathInferredFromPackageJson = getProjectRoot(filename);
          const relative = Path.relative(
            rootPathInferredFromPackageJson,
            Path.join(Path.dirname(filename), importTarget)
          );
          const isInSubtreeOfProjectRoot =
            relative &&
            !relative.startsWith('..') &&
            !Path.isAbsolute(relative);
          if (!isInSubtreeOfProjectRoot) {
            context.report({
              node,
              message:
                `Cannot perform relative imports of files outside of the package root. \n` +
                `    file: ${filename}\n    imported: ${importTarget}\n` +
                `    projectRoot: ${rootPathInferredFromPackageJson}`,
            });
          }
        },
      };
    },
  },
};

module.exports = {rules};
