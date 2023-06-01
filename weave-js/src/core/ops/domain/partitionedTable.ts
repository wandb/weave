import * as _ from 'lodash';

import type {Client} from '../../client';
import {EngineClient} from '../../client';
import * as HL from '../../hl';
import {MediaPartitionedTable, OpInputNodes, OutputNode} from '../../model';
import {
  constString,
  isPartitionedTable,
  list,
  mappableNullableSkipTaggable,
  mappableNullableSkipTaggableValAsync,
  mappableNullableTaggable,
  mappableNullableTaggableVal,
  maybe,
  typedDict,
  withTableRowTag,
} from '../../model';
import {makeOp} from '../../opStore';
import {docType} from '../../util/docs';
import {opConcat} from '../primitives/list';
import {opArray} from '../primitives/literals';
import {opArtifactVersionFile} from './artifactVersion';
import {opFileArtifactVersion, opFileDir, opFileTable} from './file';
import {makeResolveOutputTypeFromOp} from './refineOp';
import {opTableRows} from './table';

const opPartitionedTableInputTypes = {
  partitionedTable: maybe({
    type: 'partitioned-table' as const,
    columnTypes: {},
  }),
};

const partitionedTableExpansionInputTypes = {
  partitionedTable: {type: 'partitioned-table' as const, columnTypes: {}},
};

const partitionedTableExpansion = async (
  client: Client,
  partitionedTable: MediaPartitionedTable,
  inputs: OpInputNodes<typeof partitionedTableExpansionInputTypes>
): Promise<OutputNode> => {
  const inputFileNode = opPartitionedTableFile({
    partitionedTable: inputs.partitionedTable,
  });
  const upstreamArtifactVersionNode = opFileArtifactVersion({
    file: inputFileNode,
  });
  const partsPath = partitionedTable.parts_path;
  const fileDirNode = opFileDir({
    file: opArtifactVersionFile({
      artifactVersion: upstreamArtifactVersionNode,
      path: constString(partsPath),
    }) as any,
  });
  // Augh, TODO: implement this as op! A dir should be an array of file
  // probably.
  const fileDir = await client.query(fileDirNode);
  const partTables = fileDir.files;
  const tableNodes = Object.keys(partTables)
    .filter(key => key.endsWith('table.json'))
    .map(key => {
      return opFileTable({
        file: opArtifactVersionFile({
          artifactVersion: upstreamArtifactVersionNode,
          // Weave1 does not send over an object with fullPath... need to figure out why
          // path: constString(partTables[key].fullPath),
          path: constString(partsPath + '/' + key),
        }) as any,
      });
    });

  // TODO: Assert homogenous column types
  const tableRowNodes = tableNodes.map(node => {
    return opTableRows({table: node as any});
  });
  const tableRowArrayNode = opArray(
    // Weave1 does not like non-string keys
    _.fromPairs(tableRowNodes.map((node, ndx) => ['' + ndx, node])) as any
  );
  return opConcat({
    arr: tableRowArrayNode as any,
  });
};

export const opPartitionedTableRowsType = makeOp({
  hidden: true,
  name: 'partitionedtable-rowsType',
  argTypes: opPartitionedTableInputTypes,
  returnType: 'type',
  resolver: async (
    {partitionedTable},
    forwardGraph,
    forwardOp,
    context,
    engine
  ) => {
    if (partitionedTable == null) {
      return 'none';
    }
    const client = new EngineClient(engine());
    const inputPartitionedTableNode = forwardOp.op.inputs.partitionedTable;
    if (inputPartitionedTableNode.nodeType !== 'output') {
      throw new Error('opPartitionedTableRows: expected output node');
    }
    const pt = await client.query(inputPartitionedTableNode);

    if (pt == null) {
      return 'none';
    }
    const joined2 = await partitionedTableExpansion(
      client,
      pt.partitionedTable,
      forwardOp.op.inputs as any // TODO(np): as any
    );
    const joinedRefined = await HL.refineNode(client, joined2, []);
    return joinedRefined.type;
  },
});

export const opPartitionedTableRows = makeOp({
  name: 'partitionedtable-rows',
  argTypes: opPartitionedTableInputTypes,
  description: `Returns the rows of a ${docType('partitioned-table')}`,
  argDescriptions: {
    partitionedTable: `The ${docType('partitioned-table')} to get rows from`,
  },
  returnValueDescription: `Rows of the ${docType('partitioned-table')}`,
  returnType: inputs => {
    return mappableNullableSkipTaggable(inputs.partitionedTable.type, t => {
      if (!isPartitionedTable(t)) {
        throw new Error('opPartitionedTableRows: expected partitioned table');
      }
      return list(withTableRowTag(typedDict({}), inputs.partitionedTable.type));
    });
  },
  resolver: async (inputs, forwardGraph, forwardOp, context, engine) => {
    const localEngine = engine();
    return mappableNullableSkipTaggableValAsync(
      inputs.partitionedTable,
      async (pt, ptWithTags) => {
        const joined2 = await partitionedTableExpansion(
          new EngineClient(localEngine),
          pt.partitionedTable,
          forwardOp.outputNode.node.fromOp.inputs as any // TODO(np): as any
        );

        // TODO: get rid of await
        return (await localEngine.executeNodes([joined2], false))[0];
      }
    );
  },
  resolveOutputType: makeResolveOutputTypeFromOp(opPartitionedTableRowsType, [
    'partitionedTable',
  ]),
});

export const opPartitionedTableFile = makeOp({
  name: 'partitionedtable-file',
  argTypes: opPartitionedTableInputTypes,
  description: `Returns the ${docType('file')} of a ${docType(
    'partitioned-table'
  )}`,
  argDescriptions: {
    partitionedTable: `The ${docType('partitioned-table')}`,
  },
  returnValueDescription: `${docType('file')} of the ${docType(
    'partitioned-table'
  )}`,
  returnType: inputs =>
    mappableNullableTaggable(inputs.partitionedTable.type, t => {
      return {type: 'file'};
    }),
  resolver: async inputs => {
    return await mappableNullableTaggableVal(
      inputs.partitionedTable,
      partitionedTable => {
        return partitionedTable;
      }
    );
  },
});
