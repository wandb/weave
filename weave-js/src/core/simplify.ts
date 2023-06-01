import type {Client} from './client';
import * as HL from './hl';
import type {Node, OpInputs, OutputNode} from './model';
import {
  constFunction,
  constNumber,
  constString,
  isAssignableTo,
  isFunction,
  isTypedDict,
} from './model';
import {
  opAnd,
  opArtifactName,
  opArtifactType,
  opArtifactTypeName,
  opArtifactVersionName,
  opGroupGroupKey,
  opIndex,
  opNumberEqual,
  opStringEqual,
} from './ops';
import {filterNodes} from './util/filter';

// Must preserve behavior exactly!
//
// Simplifications implemented:
//   - remove limit ops prior to index ops
//   - remove offset ops prior to index ops
//   - convert groupBy.**.index() to filter where ** ops
//     must be dimension preserving
//   - convert index node that produces artifact to
//     project.artifact() (if descendent of project)
//   - convert index node that produces artifactVersion to
//     project.artifactVersion() (if descendent of project)

function groupByFnToFilterPred(
  groupByFn: OutputNode,
  groupKey: any
): OutputNode | undefined {
  if (groupByFn.type === 'string') {
    return opStringEqual({
      lhs: groupByFn,
      rhs: constString(groupKey),
    });
  } else if (groupByFn.type === 'number') {
    return opNumberEqual({
      lhs: groupByFn,
      rhs: constNumber(groupKey),
    });
  }
  if (!isTypedDict(groupByFn.type)) {
    return;
  }
  const preds: OutputNode[] = [];
  for (const key of Object.keys(groupByFn.type.propertyTypes)) {
    const propertyType = groupByFn.type.propertyTypes[key];
    if (propertyType === 'string') {
      preds.push(
        opStringEqual({
          lhs: groupByFn.fromOp.inputs[key],
          rhs: constString(groupKey[key]),
        })
      );
    } else if (propertyType === 'number') {
      preds.push(
        opNumberEqual({
          lhs: groupByFn.fromOp.inputs[key],
          rhs: constNumber(groupKey[key]),
        })
      );
    } else {
      return;
    }
  }
  return preds.reduce((accumulator, currentValue) =>
    opAnd({lhs: accumulator as any, rhs: currentValue as any})
  );
}

async function simplifyNode(
  client: Client,
  node: Node
): Promise<Node | undefined> {
  if (node.nodeType !== 'output') {
    return;
  }
  const {fromOp} = node;
  if (fromOp.name === 'index') {
    const indexNode = fromOp.inputs.index;
    if (indexNode.nodeType !== 'const') {
      return;
    }
    const index = indexNode.val;
    const checkNode = fromOp.inputs.arr;
    if (checkNode.nodeType !== 'output') {
      return;
    }
    const checkFromOp = checkNode.fromOp;
    if (checkFromOp.name === 'limit') {
      const limitArr = checkFromOp.inputs.arr;
      const limitNode = checkFromOp.inputs.limit;
      if (limitNode.nodeType !== 'const') {
        return;
      }
      if (limitNode.val <= index) {
        // limit would chop the array shorter than we're trying
        // to index, which produces an error. Simplify should not
        // change behavior at all, so we don't simplify here.
        return;
      }
      return {
        ...node,
        fromOp: {
          name: 'index',
          inputs: {
            arr: limitArr,
            index: constNumber(index),
          },
        },
      };
    } else if (checkFromOp.name === 'offset') {
      const offsetArr = checkFromOp.inputs.arr;
      const offsetNode = checkFromOp.inputs.offset;
      if (offsetNode.nodeType !== 'const') {
        return;
      }
      // skip over the limit node
      return {
        ...node,
        fromOp: {
          name: 'index',
          inputs: {
            arr: offsetArr,
            index: constNumber(index + offsetNode.val),
          },
        },
      };
    }
    // an index with ancestor groupBy connected by dimension preserving
    // operations can be simplified to a filter.
    const foundGroupBy = HL.findChainedAncestor(
      checkNode,
      n => n.nodeType === 'output' && n.fromOp.name === 'groupby',
      n =>
        n.nodeType === 'output' &&
        (n.fromOp.name === 'filter' ||
          n.fromOp.name === 'sort' ||
          n.fromOp.name === 'map')
    );
    if (foundGroupBy != null) {
      if (foundGroupBy.nodeType !== 'output') {
        throw new Error(
          'simplifyNode: expected foundGroupBy.nodeType to be output, found ' +
            foundGroupBy.nodeType
        );
      }
      const groupByFromOp = foundGroupBy.fromOp;
      const groupByArr = groupByFromOp.inputs.arr;
      const groupByFn = groupByFromOp.inputs.groupByFn;
      if (!isFunction(groupByFn.type) || groupByFn.type.inputTypes == null) {
        throw new Error(
          'simplifyNode: expected groupByFn to be a parameterized function'
        );
      }
      if (groupByFn.nodeType !== 'const') {
        return;
      }
      const tagNode = opGroupGroupKey({
        obj: opIndex({arr: checkNode, index: constNumber(index)}),
      });
      const tagValue = await client.query(tagNode);
      const filterFn = groupByFnToFilterPred(groupByFn.val, tagValue);
      if (filterFn == null) {
        return;
      }
      return {
        ...node,
        fromOp: {
          name: 'filter',
          inputs: {
            arr: groupByArr,
            filterFn: constFunction(
              groupByFn.type.inputTypes,
              // ignore the named variables, we kept the same
              // input variable in groupByToFilterPred
              inputs => filterFn
            ),
          },
        },
      };
    }
    if (isAssignableTo(node.type, 'artifact')) {
      // TODO: not tested
      const projectNode = HL.findChainedAncestor(
        checkNode,
        n => n.nodeType === 'output' && n.type === 'project',
        n => true
      );
      if (projectNode == null) {
        return;
      }
      if (projectNode.nodeType !== 'output') {
        throw new Error(
          'simplifyNode: expected projectNode.nodeType to be output, found ' +
            projectNode.nodeType
        );
      }
      const artifactTypeNode = opArtifactTypeName({
        artifactType: opArtifactType({artifact: node}),
      });
      const artifactNameNode = opArtifactName({artifact: node});
      const [artifactType, artifactName] = await Promise.all([
        client.query(artifactTypeNode),
        client.query(artifactNameNode),
      ]);
      return {
        ...node,
        fromOp: {
          name: 'project-artifact',
          inputs: {
            project: projectNode,
            artifactType: constString(artifactType),
            artifactName: constString(artifactName),
          },
        },
      };
    }
    if (isAssignableTo(node.type, 'artifactVersion')) {
      // TODO: not tested
      const projectNode = HL.findChainedAncestor(
        checkNode,
        n => n.nodeType === 'output' && n.type === 'project',
        n => true
      );
      if (projectNode == null) {
        return;
      }
      if (projectNode.nodeType !== 'output') {
        throw new Error(
          'simplifyNode: expected projectNode.nodeType to be output, found ' +
            projectNode.nodeType
        );
      }
      const artifactVersionNameNode = opArtifactVersionName({
        artifactVersion: node as any,
      });
      const [artifactVersionName] = await client.query(artifactVersionNameNode);
      return {
        ...node,
        fromOp: {
          name: 'project-artifactVersion',
          inputs: {
            project: projectNode,
            artifactVersionName: constString(artifactVersionName),
          },
        },
      };
    }
  }
  return;
}

async function simplifyPass(client: Client, node: Node) {
  // simplify until we can't anymore
  let simpler: Node | undefined = node;
  while (simpler != null) {
    simpler = await simplifyNode(client, node);
    if (simpler != null) {
      node = simpler;
    }
  }
  // Simplify inputs
  if (node.nodeType !== 'output') {
    return node;
  }
  const newInputNodes = await Promise.all(
    Object.values(node.fromOp.inputs).map(inNode => simplify(client, inNode))
  );
  const newInputs: OpInputs = {};
  const argNames = Object.keys(node.fromOp.inputs);
  for (let i = 0; i < argNames.length; i++) {
    newInputs[argNames[i]] = newInputNodes[i];
  }
  return {
    ...node,
    fromOp: {
      ...node.fromOp,
      inputs: newInputs as any,
    },
  };
}

export async function simplify(client: Client, node: Node): Promise<Node> {
  // If there are any get-tag calls, don't try to simplify
  if (
    filterNodes(
      node,
      checkNode =>
        checkNode.nodeType === 'output' &&
        checkNode.fromOp.name === 'group-groupkey'
    ).length > 0
  ) {
    return node;
  }
  return simplifyPass(client, node);
}
