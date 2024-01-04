import * as _ from 'lodash';
import memoize from 'memoize-one';

import {callOpVeryUnsafe, dereferenceAllVars, mapNodes} from './callers';
import type {Client} from './client';
import {
  availableOpsForChain,
  couldBeReplacedByType,
  getPlaceholderArg,
  isEditingNode,
  isEditingOp,
  maybeReplaceNode,
  pickSuggestions,
  refineEditingNode,
  rootOps,
  supportedEngineForNode,
  validReplacementOps,
} from './hl';
import {nodeToString} from './language/js/print';
import {
  constFunction,
  constNone,
  constNumber,
  constString,
  functionType,
  isAssignableTo,
  isConstNode,
  isFunctionType,
  isListLike,
  isNullable,
  list,
  listObjectType,
  maybe,
  toFrame,
  unwrapTaggedValues,
  varNode,
  voidNode,
} from './model';
import type {
  EditingNode,
  EditingOp,
  EditingOpInputs,
} from './model/graph/editing/types';
import type {Stack} from './model/graph/types';
import {
  applyOpToOneOrMany,
  opArtifactName,
  opArtifactTypeName,
  opArtifactVersionFiles,
  opArtifactVersionName,
  opArtifactVersions,
  opArtifactVersionVersionId,
  opEntityName,
  opEntityProjects,
  opFilePath,
  opFlatten,
  opMap,
  opProjectArtifact,
  opProjectArtifacts,
  opProjectArtifactTypes,
  opProjectName,
  opRootEntity,
  opRootViewer,
  opRunLoggedArtifactVersions,
  opUserEntities,
} from './ops';
import type {OpStore} from './opStore/types';
import {findConsumingOp, isBinaryOp, opDisplayName} from './opStore/util';
import {getStackAtNodeOrOp} from './refineHelpers';
import {notEmpty} from './util/obj';
import {trimStartChar} from './util/string';

export interface AutosuggestResult<
  Replacement extends EditingNode | EditingOp
> {
  newNodeOrOp: Replacement;
  suggestionString: string;
  category: string;
}

const MAX_SUGGESTIONS = 500;

type SuggestedNode = {
  node: EditingNode;
  category: string;
};

// Attach a category string (like "Ops") to a suggestion.
const addCategory = (node: EditingNode, category: string): SuggestedNode => {
  return {
    node,
    category,
  };
};

// For a given node, return a list of suggested new
// nodes to swap it with.
async function autosuggestNodes(
  client: Client,
  node: EditingNode,
  graph: EditingNode,
  stack: Stack
): Promise<{
  refinedNode: EditingNode;
  suggestions: SuggestedNode[];
}> {
  let result: SuggestedNode[] = [];
  const consumer = findConsumingOp(node, graph);
  const consumingOp = consumer?.outputNode.fromOp;
  const supportedEngines =
    consumer?.outputNode == null
      ? new Set()
      : supportedEngineForNode(consumer.outputNode as any, client.opStore);
  if (node.nodeType === 'const' || node.nodeType === 'void') {
    if (consumingOp != null) {
      const consumingOpDef = client.opStore.getOpDef(consumingOp.name);
      const consumingOpInputTypes = Object.values(consumingOpDef.inputTypes);
      if (
        consumer &&
        isFunctionType(consumingOpDef.inputTypes[consumer.argName])
      ) {
        result = [
          addCategory(
            {
              nodeType: 'const',
              type: consumingOpDef.inputTypes[consumer.argName],
              val: voidNode(),
            },
            'Other'
          ),
        ];
      } else if (consumingOp.name === 'pick') {
        const pickObj = consumingOp.inputs.obj;
        const pickKeys = pickSuggestions(pickObj.type);
        result = pickKeys.map(key => addCategory(constString(key), 'Other'));
        // TODO: the following branches have `supportedEngines.has('ts')`. This
        // means that suggestions will only work for these ops so long as we
        // have a typescript engine. For now this is fine, but we can remove
        // this check once we get op parity.
      } else if (
        consumingOp.name === 'root-project' &&
        supportedEngines.has('ts')
      ) {
        let keys: string[] = [];
        let category = '';
        if (consumer?.argName === 'entityName') {
          category = 'Entities';
          const entityNamesNode = opEntityName({
            entity: opUserEntities({
              user: opRootViewer({}),
            }),
          });
          keys = await client.query(entityNamesNode as any);
        } else if (consumer?.argName === 'projectName') {
          category = 'Projects';
          const entityNamesNode = opProjectName({
            project: opEntityProjects({
              entity: opRootEntity({
                entityName: consumingOp.inputs.entityName as any,
              }),
            }),
          });
          keys = await client.query(entityNamesNode as any);
        }
        result = keys.map(key => {
          return addCategory(constString(key), category);
        });
      } else if (
        consumingOp.name === 'root-user' &&
        supportedEngines.has('ts')
      ) {
        let keys: string[] = [];
        if (consumer?.argName === 'userName') {
          keys = ['shawn', 'stacey', 'l2k2'];
        }
        result = keys.map(key => {
          return addCategory(constString(key), 'Users');
        });
      } else if (
        consumingOp.name === 'project-artifact' &&
        supportedEngines.has('ts')
      ) {
        let keys: string[] = [];
        // need to dereference project node since it has a var input node for runs
        const projectNode = dereferenceAllVars(
          consumingOp.inputs.project,
          stack
        ).node as EditingNode;
        if (projectNode.nodeType === 'void') {
          throw new Error(
            'autosuggestNodes: project-artifactVersion input projectNode.nodeType is void'
          );
        }
        const runLoggedArtifactNamesNode = opArtifactName({
          artifact: opProjectArtifacts({
            project: projectNode as any,
          }) as any,
        });
        const possibleValues = await client.query(
          runLoggedArtifactNamesNode as any
        );
        keys = _.uniq(_.flatten(possibleValues));
        result = keys.map(key => {
          return addCategory(constString(key), 'Artifacts');
        });
      } else if (
        consumingOp.name === 'project-artifactType' &&
        supportedEngines.has('ts')
      ) {
        let keys: string[] = [];
        // need to dereference project node since it has a var input node for runs
        const projectNode = dereferenceAllVars(
          consumingOp.inputs.project,
          stack
        ).node as EditingNode;
        if (projectNode.nodeType === 'void') {
          throw new Error(
            'autosuggestNodes: project-artifactType input projectNode.nodeType is void'
          );
        }
        if (consumer?.argName === 'artifactType') {
          const projectArtifactTypeNamesNode = opArtifactTypeName({
            artifactType: opProjectArtifactTypes({
              project: projectNode as any,
            }) as any,
          });
          const possibleValues = await client.query(
            projectArtifactTypeNamesNode as any
          );
          // Calling flatten here as we may have nested
          // lists due to mappable input.
          keys = _.uniq(_.flatten(possibleValues));
        }
        result = keys.map(key => {
          return addCategory(constString(key), 'Artifact types');
        });
      } else if (
        consumingOp.name === 'project-artifactVersion' &&
        supportedEngines.has('ts')
      ) {
        let keys: string[] = [];
        // need to dereference project node since it has a var input node for runs
        const projectNode = dereferenceAllVars(
          consumingOp.inputs.project,
          stack
        ).node as EditingNode;
        if (projectNode.nodeType === 'void') {
          throw new Error(
            'autosuggestNodes: project-artifactVersion input projectNode.nodeType is void'
          );
        }
        if (consumer?.argName === 'artifactName') {
          const runLoggedArtifactNamesNode = opArtifactName({
            artifact: opProjectArtifacts({
              project: projectNode as any,
            }) as any,
          });
          const possibleValues = await client.query(
            runLoggedArtifactNamesNode as any
          );
          // Calling flatten here as we may have nested
          // lists due to mappable input.
          keys = _.uniq(_.flatten(possibleValues));
        } else if (consumer?.argName === 'artifactVersionAlias') {
          if (consumingOp.inputs.artifactName.nodeType === 'void') {
            return {refinedNode: node, suggestions: []};
          }
          const artifactVersionNamesNode = opArtifactVersionVersionId({
            artifactVersion: opArtifactVersions({
              artifact: opProjectArtifact({
                project: projectNode as any,
                artifactName: consumingOp.inputs.artifactName as any,
              }) as any,
            }),
          });
          const possibleValues = await client.query(
            artifactVersionNamesNode as any
          );
          // Calling flatten here as we may have nested
          // lists due to mappable input.
          keys = _.uniq(_.flatten(possibleValues));
        }
        result = keys.map(key => {
          return addCategory(
            constString(Number.isInteger(key) ? `v${key}` : `${key}`),
            'Aliases'
          );
        });
      } else if (
        consumingOp.name === 'run-loggedArtifactVersion' &&
        supportedEngines.has('ts')
      ) {
        let keys: string[] = [];
        if (consumer?.argName === 'artifactVersionName') {
          const runNode = consumingOp.inputs.run;
          if (runNode.nodeType === 'void') {
            throw new Error(
              'autosuggestNodes: run-loggedArtifactVersion input runNode.nodeType is void'
            );
          }
          let called = dereferenceAllVars(runNode, stack).node;

          // Just get the first run for now
          if (
            called.nodeType === 'output' &&
            called.fromOp.name === 'index' &&
            called.fromOp.inputs.index.nodeType === 'var'
          ) {
            called = {
              ...called,
              fromOp: {
                ...called.fromOp,
                inputs: {
                  ...called.fromOp.inputs,
                  index: constNumber(0),
                },
              },
            };
          }

          const runLoggedArtifactIdsNode = opMap({
            arr: opRunLoggedArtifactVersions({
              run: called as any,
            }) as any,
            mapFn: constFunction({row: 'artifactVersion'}, ({row}) =>
              opArtifactVersionName({
                artifactVersion: row,
              })
            ) as any,
          });
          const possibleValues = await client.query(
            runLoggedArtifactIdsNode as any
          );
          // Calling flatten here as we may have nested
          // lists due to mappable input.
          keys = _.uniq(_.flatten(possibleValues));
        }
        result = keys.map(key => {
          return addCategory(constString(key), 'Artifact versions');
        });
      } else if (
        consumingOp.name === 'artifactVersion-file' &&
        supportedEngines.has('ts')
      ) {
        let keys: string[] = [];
        if (consumer?.argName === 'path') {
          const artifactNode = consumingOp.inputs.artifactVersion;
          if (artifactNode.nodeType === 'void') {
            throw new Error(
              'autosuggestNodes: artifactVersion-file input artifactNode.nodeType is void'
            );
          }
          const called = dereferenceAllVars(artifactNode, stack).node;

          // one or many as we could be in a double list
          const runLoggedArtifactFileNames = applyOpToOneOrMany(
            opFilePath,
            'file',
            opArtifactVersionFiles({
              artifactVersion: called as any,
            }),
            {}
          );
          const possibleValues = await client.query(
            runLoggedArtifactFileNames as any
          );

          // Calling flatten here as we may have nested
          // lists due to mappable input.
          keys = _.uniq(_.flatten(possibleValues));
        }
        result = keys.map(key => {
          return addCategory(constString(key), 'Artifact files');
        });
      } else if (
        consumingOp.name === 'string-equal' ||
        consumingOp.name === 'string-notEqual'
      ) {
        // Assume this is rhs for now.
        if (consumer?.argName !== 'rhs') {
          throw new Error(
            'autosuggestNodes: string-equal/notEqual argName is not rhs'
          );
        }
        const lhsNode = consumingOp.inputs.lhs;
        if (lhsNode.nodeType === 'void') {
          throw new Error(
            'autosuggestNodes: string-equal/notEqual input lhsNode.nodeType is void'
          );
        }
        const called = dereferenceAllVars(lhsNode, stack).node;
        const generalizedNode = mapNodes(called, curNode => {
          if (curNode.nodeType !== 'output') {
            return curNode;
          }
          const fromOp = curNode.fromOp;
          if (
            fromOp.name === 'filter' ||
            // If we find an index with a variable, remove it.
            (fromOp.name === 'index' && fromOp.inputs.index.nodeType === 'var')
          ) {
            return opFlatten({arr: fromOp.inputs.arr as any});
          }
          return curNode;
        });

        const improvedNode = await refineEditingNode(
          client,
          generalizedNode,
          stack
        );

        if (
          improvedNode.nodeType === 'void' ||
          !isAssignableTo(improvedNode.type, maybe(list(maybe('string'))))
        ) {
          console.error(
            'Could not generalize node for suggest, you probably need to make ops in this chain project. ' +
              nodeToString(improvedNode, client.opStore)
          );
          result = [];
        } else {
          const possibleValues = (await client.query(
            improvedNode as any
          )) as Array<string | null> | null;

          let matchesFirst = (a: string, b: string) => 0;

          if (
            isConstNode(node) &&
            typeof node.val === 'string' &&
            node.val.length > 0
          ) {
            const searchString = node.val.toLocaleLowerCase();
            matchesFirst = (a: string, b: string) => {
              const aMatches = a.toLocaleLowerCase().includes(searchString);
              const bMatches = b.toLocaleLowerCase().includes(searchString);
              if (aMatches && !bMatches) {
                return -1;
              } else if (bMatches && !aMatches) {
                return 1;
              }
              return 0;
            };
          }

          // filter null, we'll suggest it as none below
          const keys =
            possibleValues == null
              ? []
              : _.uniq(possibleValues).filter(notEmpty).sort(matchesFirst);
          result = keys.map(key => addCategory(constString(key), 'Other'));
        }
        // do stuff
      } else if (consumingOp.name === 'contains') {
        const arrNode = consumingOp.inputs.arr;
        if (arrNode.nodeType === 'void') {
          throw new Error(
            'autosuggestNodes: contains input arrNode.nodeType is void'
          );
        }
        const called = dereferenceAllVars(arrNode, stack).node;
        const generalizedNode = opFlatten({
          arr: mapNodes(called, curNode => {
            if (curNode.nodeType !== 'output') {
              return curNode;
            }
            const fromOp = curNode.fromOp;
            if (
              fromOp.name === 'filter' ||
              // If we find an index with a variable, remove it.
              (fromOp.name === 'index' &&
                fromOp.inputs.index.nodeType === 'var')
            ) {
              return opFlatten({arr: fromOp.inputs.arr as any});
            }
            return curNode;
          }) as any,
        });

        const improvedNode = await refineEditingNode(
          client,
          generalizedNode,
          stack
        );

        if (
          improvedNode.nodeType === 'void' ||
          !isAssignableTo(improvedNode.type, maybe(list(maybe('string'))))
        ) {
          console.error(
            'Could not generalize node for suggest, you probably need to make ops in this chain project. ' +
              nodeToString(improvedNode, client.opStore)
          );
          result = [];
        } else {
          const possibleValues = (await client.query(
            improvedNode as any
          )) as Array<string | null> | null;
          // filter null, we'll suggest it as none below
          const keys =
            possibleValues == null
              ? []
              : _.uniq(possibleValues).filter(notEmpty);
          result = keys.map(key => addCategory(constString(key), 'Other'));
        }
      } else if (
        isBinaryOp(consumingOp, client.opStore) &&
        isAssignableTo('number', consumingOpInputTypes[1])
      ) {
        result.push(addCategory(constNumber(3.14159), 'Numeric constants'));
      }

      // Suggest none for equality comparison ops (which are all nullable),
      // if the left hand side might have a null in it based on its input
      // type.
      if (
        (consumingOp.name.endsWith('-equal') ||
          consumingOp.name.endsWith('-notEqual')) &&
        (isNullable(consumingOp.inputs.lhs.type) ||
          (isListLike(consumingOp.inputs.lhs.type) &&
            isNullable(listObjectType(consumingOp.inputs.lhs.type))))
      ) {
        result.push(addCategory(constNone(), 'Other'));
      }
    }

    if (node.nodeType === 'void') {
      const frame = toFrame(stack);
      const variableNames = Object.keys(frame);
      if (variableNames.length > 0) {
        for (const varName of variableNames) {
          // Recursively suggest results for each variable
          const vNode = varNode(frame[varName].type, varName);
          // const newGraph = maybeReplaceNode(graph, node, vNode);
          // const results = await autosuggestNodes(
          //   client,
          //   vNode,
          //   newGraph,
          //   stack
          // );
          // vNode = results.refinedNode as any;
          result.push(addCategory(vNode, 'Variables'));
          // result = result.concat(results.suggestions);
        }
      }
      if (graph.nodeType === 'void') {
        // Suggest root ops
        result = result.concat(
          rootOps(client.opStore).map(opDef => {
            const rootOpInputs = _.mapValues(
              opDef.inputTypes,
              (v, key) => getPlaceholderArg(opDef, key) ?? voidNode()
            );
            return addCategory(
              callOpVeryUnsafe(opDef.name, rootOpInputs),
              'Root Ops'
            );
          })
        );
      }
    } else {
      const availOps = availableOpsForChain(node, client.opStore).filter(
        opDef => !opDef.name.startsWith('objectConstructor-_new_')
      );
      result = result.concat(
        availOps.flatMap(opDef => {
          return addCategory(
            callOpVeryUnsafe(opDef.name, {
              lhs: node,
              rhs: getPlaceholderArg(opDef, 'rhs') ?? voidNode(),
            }),
            'Ops'
          );
        })
      );
    }
  } else if (node.nodeType === 'var' || node.nodeType === 'output') {
    if (node.type === 'any') {
      node = await refineEditingNode(client, node, stack);
    }
    const availOps = availableOpsForChain(node as any, client.opStore);
    result = availOps.flatMap(opDef => {
      if (opDef.name === 'pick') {
        const pickKeys = pickSuggestions(node.type);
        return [
          ...pickKeys.map(key =>
            addCategory(
              callOpVeryUnsafe('pick', {
                obj: node,
                key: constString(key),
              }),
              'Pick'
            )
          ),
          addCategory(
            callOpVeryUnsafe('pick', {obj: node, key: voidNode()}),
            'Pick'
          ),
        ];
      } else {
        const argNames = Object.keys(opDef.inputTypes);

        const opInputs: EditingOpInputs = {
          [argNames[0]]: node,
        };
        for (const argName of argNames.slice(1)) {
          if (
            isAssignableTo(
              opDef.inputTypes[argName],
              functionType({row: 'any'}, 'any')
            )
          ) {
            // Create a variable called row with type any?
            // TODO: We'll fix this up when we enable user-created anonymous
            // functions.
            opInputs[argName] = constFunction(
              {row: 'any', ...(opDef.name === 'map' ? {index: 'any'} : {})},
              () => varNode('any', 'row')
            );
          } else {
            opInputs[argName] = getPlaceholderArg(opDef, argName) ?? voidNode();
          }
        }
        return addCategory(callOpVeryUnsafe(opDef.name, opInputs), 'Ops');
      }
    });

    if ((node.type as any)._is_object) {
      // node is an Object with properties.  Suggest each property as a __getattr__ call
      const getAttrCalls = Object.keys(node.type as any)
        .filter(attrName => !attrName.startsWith('_'))
        .map(attrName => {
          return addCategory(
            callOpVeryUnsafe('Object-__getattr__', {
              self: node,
              name: constString(attrName),
            }),
            'Other'
          );
        });

      result = [...result, ...getAttrCalls];
    }
  }

  if (result.length > MAX_SUGGESTIONS) {
    console.warn(
      `Too many suggestions (${result.length}) for node ${nodeToString(
        node,
        client.opStore
      )}`
    );
    result = result.slice(0, MAX_SUGGESTIONS);
  }

  return {refinedNode: node, suggestions: result};
}

async function _autosuggestOps(
  op: EditingOp,
  opStore: OpStore
): Promise<EditingOp[]> {
  return validReplacementOps(op, opStore)
    .filter(opDef => !opDef.hidden)
    .map(opDef => ({
      name: opDef.name,
      inputs: op.inputs,
    }));
}
const autosuggestOps = memoize(_autosuggestOps);

function isTagGetterNodeOrOp(
  nodeOrOp: EditingNode | EditingOp,
  opStore: OpStore
) {
  if (isEditingNode(nodeOrOp) && nodeOrOp.nodeType === 'output') {
    const aOp = opStore.getOpDef(nodeOrOp.fromOp.name);
    if (aOp.name?.startsWith('tag-')) {
      return true;
    }
  }
  return false;
}

function isBinaryNodeOrOp(nodeOrOp: EditingNode | EditingOp, opStore: OpStore) {
  if (isEditingNode(nodeOrOp) && nodeOrOp.nodeType === 'output') {
    return isBinaryOp(nodeOrOp.fromOp, opStore);
  }
  return false;
}

function isVarNodeOrOp(nodeOrOp: EditingNode | EditingOp) {
  if (isEditingNode(nodeOrOp) && nodeOrOp.nodeType === 'var') {
    return true;
  }
  return false;
}

export async function autosuggest(
  client: Client,
  nodeOrOp: EditingNode | EditingOp,
  graph: EditingNode,
  stack: Stack,
  query?: string
): Promise<
  Array<AutosuggestResult<EditingNode>> | Array<AutosuggestResult<EditingOp>>
> {
  const stackAtNodeOrOp =
    getStackAtNodeOrOp(graph, nodeOrOp, stack, client.opStore) || stack;

  // NOTE: this function returns all valid nodes/ops for the given position in the graph,
  // but does not filter them according to the currently entered text -- that happens
  // later, in WBSuggester.tsx
  let result: Array<AutosuggestResult<any>> = [];
  if (isEditingOp(nodeOrOp)) {
    const ops = await autosuggestOps(nodeOrOp, client.opStore);

    result = ops.map(newOp => ({
      newNodeOrOp: newOp,
      suggestionString: opDisplayName(newOp, client.opStore),
      category: 'Other',
    }));
  } else {
    const results = await autosuggestNodes(
      client,
      nodeOrOp,
      graph,
      stackAtNodeOrOp
    );

    result = results.suggestions.map(suggestion => ({
      newNodeOrOp: suggestion.node,
      suggestionString: nodeToString(
        maybeReplaceNode(
          suggestion.node,
          results.refinedNode,
          varNode('any', '')
        ),
        client.opStore,
        null
      ),
      category: suggestion.category,
    }));
  }

  result.sort((a, b) => {
    // Constants first
    const aIsConst = a.newNodeOrOp.nodeType === 'const';
    const bIsConst = b.newNodeOrOp.nodeType === 'const';

    if (aIsConst && !bIsConst) {
      return -1;
    } else if (!aIsConst && bIsConst) {
      return 1;
    }

    // Picks second
    const aIsPick =
      a.newNodeOrOp.nodeType === 'output' &&
      a.newNodeOrOp.fromOp.name === 'pick';
    const bIsPick =
      b.newNodeOrOp.nodeType === 'output' &&
      b.newNodeOrOp.fromOp.name === 'pick';

    if (aIsPick && !bIsPick) {
      return -1;
    } else if (!aIsPick && bIsPick) {
      return 1;
    }

    const aIsTagGetter = isTagGetterNodeOrOp(a.newNodeOrOp, client.opStore);
    const bIsTagGetter = isTagGetterNodeOrOp(b.newNodeOrOp, client.opStore);

    if (aIsTagGetter && !bIsTagGetter) {
      return 1;
    } else if (!aIsTagGetter && bIsTagGetter) {
      return -1;
    }

    const aIsVarNode = isVarNodeOrOp(a.newNodeOrOp);
    const bIsVarNode = isVarNodeOrOp(b.newNodeOrOp);
    if (aIsVarNode && !bIsVarNode) {
      return -1;
    } else if (!aIsVarNode && bIsVarNode) {
      return 1;
    }

    const aIsBinaryOp = isBinaryNodeOrOp(a.newNodeOrOp, client.opStore);
    const bIsBinaryOp = isBinaryNodeOrOp(b.newNodeOrOp, client.opStore);

    if (aIsBinaryOp && !bIsBinaryOp) {
      return -1;
    } else if (!aIsBinaryOp && bIsBinaryOp) {
      return 1;
    }

    return a.suggestionString < b.suggestionString ? -1 : 1;
  });

  const nodeIsCurrentlyString =
    isEditingNode(nodeOrOp) &&
    nodeOrOp.nodeType === 'const' &&
    unwrapTaggedValues(nodeOrOp.type) === 'string';

  const nodeCouldBeReplacedByString =
    isEditingNode(nodeOrOp) &&
    couldBeReplacedByType(nodeOrOp, graph, 'string', client.opStore);

  // an "exact match" for a string node is the buffer wrapped in quotes
  const stringIsExactMatch = (test: string) =>
    test === query || (nodeIsCurrentlyString && test === `"${query}"`);

  // it's important to do this check before the block below, where we
  // will insert this suggestion if it doesn't already exist
  const containsExactMatch = result.some(item =>
    stringIsExactMatch(item.suggestionString)
  );

  if (query == null && isConstNode(nodeOrOp) && nodeOrOp.type === 'string') {
    query = nodeOrOp.val;
  }

  if (query) {
    if (nodeCouldBeReplacedByString) {
      // if the node you're currently editing could be replaced by a string,
      // offer the literal query value as the first suggestion
      result = _.uniqBy(
        [
          {
            newNodeOrOp: constString(query),
            suggestionString: `"${query}"`,
            category: 'Replace with',
          },
          ...result,
        ],
        item => item.suggestionString
      );
    }

    // usually, we want to filter the results by the query to give typeahead
    // behavior -- but there's a special case when the user returns to a completed
    // node or op:
    //
    // because the node/op is completed, the buffer/query will already contain the exact text
    // of the matching suggestion. The user's intent in returning, presumably, is to *change*
    // this node/op, so we show them *all* possible results except the one they've already selected.
    // If they start typing, the results will be filtered by the existing buffer, so this may turn
    // out to be awkward (suggestions will suddenly disappear), but at least the user can select
    // a replacement from the dropdown immediately if they want to.
    //
    // note that this does not conflict with the automatic accepting of suggestions when
    // the user enters the full text of the suggestion: that behavior happens onKeyDown,
    // BEFORE the new suggestions will be calculated. The order's important.
    // see onBufferChange in AutoSuggestor in ExpressionEditor.tsx
    if (containsExactMatch) {
      result = result.filter(
        item => !stringIsExactMatch(item.suggestionString)
      );
    } else {
      // result = result.filter(item => item.suggestionString.includes(query));
      const lowerQuery = trimStartChar(query, '.').toLocaleLowerCase();
      result = result.sort((a, b) => {
        return (
          (b.suggestionString.startsWith('"') ||
          b.suggestionString.toLocaleLowerCase().includes(lowerQuery)
            ? 1
            : -1) -
          (a.suggestionString.startsWith('"') ||
          a.suggestionString.toLocaleLowerCase().includes(lowerQuery)
            ? 1
            : -1)
        );
      });
    }
  }

  return result;
}
