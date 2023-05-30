import {EngineClient} from '../../client';
import * as HL from '../../hl';
import type {MediaJoinedTable, OpInputNodes, OutputNode} from '../../model';
import {
  constFunction,
  constString,
  isJoinedTable,
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
import {opJoin} from '../primitives/list';
import {opPick} from '../primitives/typedDict';
import {opArtifactVersionFile} from './artifactVersion';
import {
  opFileArtifactVersion,
  opFilePartitionedTable,
  opFileTable,
} from './file';
import {opPartitionedTableRows} from './partitionedTable';
import {makeResolveOutputTypeFromOp} from './refineOp';
import {opTableRows} from './table';

const opJoinedTableInputsTypes = {
  joinedTable: maybe({
    type: 'joined-table' as const,
    columnTypes: {},
  }),
  leftOuter: 'boolean' as const,
  rightOuter: 'boolean' as const,
};

const joinedTableExpansionInputsTypes = {
  joinedTable: {type: 'joined-table' as const, columnTypes: {}},
  leftOuter: 'boolean' as const,
  rightOuter: 'boolean' as const,
};

// We'll want to do these expansions as a compiler pass in the future.
// We should first expand all nodes that have expansions, then do an optimization
// pass, then execute. For example, we may be able to optimize out this join,
// if we're not fetching downstream columns from both joined tables.
const joinedTableExpansion = async (
  joinedTable: MediaJoinedTable,
  inputs: OpInputNodes<typeof joinedTableExpansionInputsTypes>
): Promise<OutputNode> => {
  const inputFileNode = opJoinedTableFile({
    joinedTable: inputs.joinedTable,
  });
  const upstreamArtifactVersionNode = opFileArtifactVersion({
    file: inputFileNode,
  });

  const table1Path = joinedTable.table1;
  const table2Path = joinedTable.table2;
  const joinKey1 = joinedTable.join_key;
  const joinKey2 = joinedTable.join_key;

  const file1 = opArtifactVersionFile({
    artifactVersion: upstreamArtifactVersionNode,
    path: constString(table1Path),
  });
  // We don't have polymorphism yet, so hack it in here to support
  // join tables that contain partitioned tables. Its a really hacky
  // to look at the file name instead of the type, but it works.
  // To look at the type we'd need to refine file1 first
  const table1Rows = table1Path.endsWith('.partitioned-table.json')
    ? opPartitionedTableRows({
        partitionedTable: opFilePartitionedTable({file: file1 as any}) as any,
      })
    : opTableRows({
        table: opFileTable({file: file1 as any}) as any,
      });

  const file2 = opArtifactVersionFile({
    artifactVersion: upstreamArtifactVersionNode,
    path: constString(table2Path),
  });
  const table2Rows = table2Path.endsWith('.partitioned-table.json')
    ? opPartitionedTableRows({
        partitionedTable: opFilePartitionedTable({file: file2 as any}) as any,
      })
    : opTableRows({
        table: opFileTable({file: file2 as any}) as any,
      });
  return opJoin({
    arr1: table1Rows as any,
    arr2: table2Rows as any,
    join1Fn: constFunction({row: typedDict({[joinKey1]: 'any'})}, ({row}) =>
      opPick({obj: row, key: constString(joinKey1)})
    ) as any,
    join2Fn: constFunction({row: typedDict({[joinKey1]: 'any'})}, ({row}) =>
      opPick({obj: row, key: constString(joinKey2)})
    ) as any,
    alias1: constString('0'),
    alias2: constString('1'),
    leftOuter: inputs.leftOuter,
    rightOuter: inputs.rightOuter,
  });
};

export const opJoinedTableRowsType = makeOp({
  hidden: true,
  name: 'joinedtable-rowsType',
  argTypes: opJoinedTableInputsTypes,
  returnType: 'type',
  resolver: async ({joinedTable}, forwardGraph, forwardOp, context, engine) => {
    if (joinedTable == null) {
      return 'none';
    }
    const client = new EngineClient(engine());
    const inputJoinedTableNode = forwardOp.op.inputs.joinedTable;
    if (inputJoinedTableNode.nodeType !== 'output') {
      throw new Error('opJoinedTableRows: expected output node');
    }
    const jt = await client.query(inputJoinedTableNode);

    if (jt == null) {
      return 'none';
    }
    const joined2 = await joinedTableExpansion(
      jt.joinedTable,
      forwardOp.op.inputs as any // TODO(np): as any
    );
    const joinedRefined = await HL.refineNode(client, joined2, []);
    return joinedRefined.type;
  },
});

export const opJoinedTableRows = makeOp({
  name: 'joinedtable-rows',
  argTypes: opJoinedTableInputsTypes,
  description: `Returns the rows of a ${docType('joined-table')}`,
  argDescriptions: {
    joinedTable: `The ${docType('joined-table')}`,
    leftOuter:
      'Whether to include rows from the left table that do not have a matching row in the right table',
    rightOuter:
      'Whether to include rows from the right table that do not have a matching row in the left table',
  },
  returnValueDescription: `The rows of the ${docType('joined-table')}`,
  returnType: inputs => {
    return mappableNullableSkipTaggable(inputs.joinedTable.type, t => {
      if (!isJoinedTable(t)) {
        throw new Error('opJoinedTableRows: input must be a joined table');
      }
      return list(withTableRowTag(typedDict({}), inputs.joinedTable.type));
    });
  },
  resolver: async (inputs, forwardGraph, forwardOp, context, engine) => {
    return mappableNullableSkipTaggableValAsync(
      inputs.joinedTable,
      async (jt, jtWithTags) => {
        const joined = await joinedTableExpansion(
          jt.joinedTable,
          forwardOp.outputNode.node.fromOp.inputs as any
        );

        // TODO: get rid of await
        return (await engine().executeNodes([joined], false))[0];
      }
    );
  },
  resolveOutputType: makeResolveOutputTypeFromOp(opJoinedTableRowsType, [
    'joinedTable',
  ]),
});

export const opJoinedTableFile = makeOp({
  name: 'joinedtable-file',
  argTypes: {
    joinedTable: maybe({
      type: 'joined-table' as const,
      columnTypes: {},
    }),
  },
  description: `Returns the ${docType('file')} of a ${docType('joined-table')}`,
  argDescriptions: {
    joinedTable: `The ${docType('joined-table')}`,
  },
  returnValueDescription: `The  ${docType('file')} of a ${docType(
    'joined-table'
  )}`,
  returnType: inputs =>
    mappableNullableTaggable(inputs.joinedTable.type, t => {
      return {type: 'file'};
    }),
  resolver: async inputs => {
    return await mappableNullableTaggableVal(
      inputs.joinedTable,
      joinedTable => {
        return joinedTable;
      }
    );
  },
});
