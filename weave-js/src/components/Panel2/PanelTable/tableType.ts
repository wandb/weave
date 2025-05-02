import {
  applyOpToOneOrMany,
  constBoolean,
  constFunction,
  isFile,
  isIncrementalTable,
  isJoinedTable,
  isListLike,
  isPartitionedTable,
  isTable,
  isUnion,
  listObjectType,
  Node,
  nullableTaggableValue,
  opConcat,
  opFileIncrementalTable,
  opFileJoinedTable,
  opFilePartitionedTable,
  opFileTable,
  opJoinedTableRows,
  opMap,
  opPartitionedTableRows,
  opTableRows,
  Type,
  union,
} from '@wandb/weave/core';
import {opIncrementalTableRows} from '@wandb/weave/core/ops/domain/incrementalTable';

export const GeneralTableType = {
  type: 'list' as const,
  objectType: 'any' as const,
};

export const DataTableType = {
  type: 'list' as const,
  objectType: {
    type: 'typedDict' as const,
    propertyTypes: {},
  },
};

// Purposely exclude the odd intermediate datatype of "[*-]table"
export const ConvertibleToDataTableType = {
  type: 'union' as const,
  members: [
    // {type: 'table' as const, columnTypes: {}},
    {
      type: 'file' as const,
      wbObjectType: {type: 'table' as const, columnTypes: {}},
    },
    {
      type: 'file' as const,
      wbObjectType: {type: 'incremental-table' as const, columnTypes: {}},
    },
    // {type: 'partitioned-table' as const, columnTypes: {}},
    {
      type: 'file' as const,
      wbObjectType: {type: 'partitioned-table' as const, columnTypes: {}},
    },
    // {type: 'joined-table' as const, columnTypes: {}},
    {
      type: 'file' as const,
      wbObjectType: {type: 'joined-table' as const, columnTypes: {}},
    },
  ],
};

export const GeneralTableLikeType = {
  type: 'union' as const,
  members: [GeneralTableType, ConvertibleToDataTableType],
};

export const DataTableLikeType = {
  type: 'union' as const,
  members: [DataTableType, ConvertibleToDataTableType],
};

export function normalizeTableLike(node: Node) {
  let type = nullableTaggableValue(node.type);
  if (isListLike(type)) {
    type = nullableTaggableValue(listObjectType(type));
  }

  if (isUnion(type)) {
    return opConcat({
      arr: opMap({
        arr: node,
        mapFn: constFunction(
          {row: union('incremental-table-file', 'table-file')},
          ({row}) => {
            return normalizeTableLike(row);
          }
        ),
      }),
    });
  }

  // wb table file
  if (isFile(type) && type.wbObjectType != null && isTable(type.wbObjectType)) {
    return opTableRows({table: opFileTable({file: node})});
  }
  // table
  if (isTable(type)) {
    return opTableRows({table: node});
  }

  // wb partitioned-table file
  if (
    isFile(type) &&
    type.wbObjectType != null &&
    isPartitionedTable(type.wbObjectType)
  ) {
    return applyOpToOneOrMany(
      opPartitionedTableRows,
      'partitionedTable',
      opFilePartitionedTable({file: node}),
      {}
    );
  }

  // partitioned-table
  if (isPartitionedTable(type)) {
    return applyOpToOneOrMany(
      opPartitionedTableRows,
      'partitionedTable',
      node,
      {}
    );
  }

  // wb joined-table file
  if (
    isFile(type) &&
    type.wbObjectType != null &&
    isJoinedTable(type.wbObjectType)
  ) {
    return applyOpToOneOrMany(
      opJoinedTableRows,
      'joinedTable',
      opFileJoinedTable({file: node}),
      {
        leftOuter: constBoolean(true),
        rightOuter: constBoolean(true),
      }
    );
  }
  // joined-table
  if (isJoinedTable(type)) {
    return applyOpToOneOrMany(opJoinedTableRows, 'joinedTable', node, {
      leftOuter: constBoolean(true),
      rightOuter: constBoolean(true),
    });
  }

  // incremental-table file
  if (
    isFile(type) &&
    type.wbObjectType != null &&
    isIncrementalTable(type.wbObjectType)
  ) {
    return opIncrementalTableRows({
      incrementalTable: opFileIncrementalTable({file: node}),
    });
  }

  if (isIncrementalTable(type)) {
    return opIncrementalTableRows({incrementalTable: node});
  }

  return node;
}

export function isTableTypeLike(type: Type) {
  type = nullableTaggableValue(type);
  // todo: might not be feasible
  if (isUnion(type)) {
    for (const member of type.members) {
      if (!isTableTypeLike(member)) {
        console.log('aint it');
        return false;
      }
    }
    return true;
  }

  // wb table file
  if (isFile(type) && type.wbObjectType != null && isTable(type.wbObjectType)) {
    return true;
  }
  // table
  if (isTable(type)) {
    return true;
  }

  // wb partitioned-table file
  if (
    isFile(type) &&
    type.wbObjectType != null &&
    isPartitionedTable(type.wbObjectType)
  ) {
    return true;
  }
  // partitioned-table
  if (isPartitionedTable(type)) {
    return true;
  }

  // wb joined-table file
  if (
    isFile(type) &&
    type.wbObjectType != null &&
    isJoinedTable(type.wbObjectType)
  ) {
    return true;
  }
  // incremental-table
  if (isIncrementalTable(type)) {
    return true;
  }

  // wb incremental-table file
  if (
    isFile(type) &&
    type.wbObjectType != null &&
    isIncrementalTable(type.wbObjectType)
  ) {
    return true;
  }

  return false;
}
