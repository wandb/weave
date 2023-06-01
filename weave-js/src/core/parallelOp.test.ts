import * as _ from 'lodash';

import type {ForwardOp} from './engine/forwardGraph';
import {constNumber, list, typedDict} from './model';
import {opIndex} from './ops';
import {makeOp} from './opStore';
import {testClient} from './testUtil';

const getDownstreamOpNamesThroughList = (op: ForwardOp): string[] => {
  return [...op.outputNode.inputTo.values()].flatMap((n: ForwardOp) => {
    if (n.op.name === 'index') {
      return getDownstreamOpNamesThroughList(n);
    } else {
      return [n.op.name];
    }
  });
};

// This op simulates an op that looks down the
// forward graph to generate it's results (ie like a gql root op).
// it returns a list of 2 objects, keyed by downstream names, with
// values as the index. For example:
// [
//     {
//         "id": 0,
//         "downstream-a": 0,
//         "downstream-b": 0,
//     },
//     {
//         "id": 1,
//         "downstream-a": 1,
//         "downstream-b": 1,
//     },
// ]
export const OpListOfThings = makeOp({
  hidden: true,
  name: 'OpListOfThings',
  argTypes: {},
  returnType: list(typedDict({})),
  resolver: async (inputs, forwardGraph, forwardOp, context) => {
    const dOps = getDownstreamOpNamesThroughList(forwardOp);
    const res = _.range(3).map(i => ({
      id: i,
      ..._.fromPairs(dOps.map(opName => [opName, i])),
    }));
    return res;
  },
});

export const OpChild = makeOp({
  hidden: true,
  name: 'OpChild',
  argTypes: {obj: typedDict({OpChild: 'number'})},
  returnType: 'number',
  resolver: async (inputs, forwardGraph, forwardOp, context) => {
    return inputs.obj.OpChild;
  },
});

const buildTestGraph = () => {
  const rootNode = OpListOfThings({});
  const leftNode = opIndex({arr: rootNode, index: constNumber(0)});
  const leftNodeChild = OpChild({obj: leftNode as any});
  const rightNode = opIndex({arr: rootNode, index: constNumber(1)});
  const rightNodeChild = OpChild({obj: rightNode as any});
  return {
    rootNode,
    leftNode,
    leftNodeChild,
    rightNode,
    rightNodeChild,
  };
};

describe('parallel graph', () => {
  it('base case', async () => {
    const client = await testClient();
    const graph = buildTestGraph();
    const rightNodeChildQuery = client.query(graph.rightNodeChild);
    expect(await rightNodeChildQuery).toEqual(1);
  });

  it('challenging case - operation order can result in invalid cache', async () => {
    const client = await testClient();
    const graph = buildTestGraph();

    // First, request the first-layer results
    const leftNodeQuery = client.query(graph.leftNode);
    const rightNodeQuery = client.query(graph.rightNode);
    expect(await leftNodeQuery).toEqual({id: 0});
    expect(await rightNodeQuery).toEqual({id: 1});

    // Now, request the second-layer - left child
    const leftNodeChildQuery = client.query(graph.leftNodeChild);
    expect(await leftNodeChildQuery).toEqual(0);

    // Now, request the second-layer - right child
    const rightNodeChildQuery = client.query(graph.rightNodeChild);
    expect(await rightNodeChildQuery).toEqual(1);
  });
});
