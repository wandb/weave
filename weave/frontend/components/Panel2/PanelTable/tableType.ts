import * as Op from '@wandb/cg/browser/ops';
import * as Types from '@wandb/cg/browser/model/types';

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

export function normalizeTableLike(node: Types.Node) {
  let type = Types.nullableTaggableValue(node.type);
  if (Types.isListLike(type)) {
    type = Types.nullableTaggableValue(Types.listObjectType(type));
  }

  // wb table file
  if (
    Types.isFile(type) &&
    type.wbObjectType != null &&
    Types.isTable(type.wbObjectType)
  ) {
    return Op.opTableRows({table: Op.opFileTable({file: node})});
  }
  // table
  if (Types.isTable(type)) {
    return Op.opTableRows({table: node});
  }

  // wb partitioned-table file
  if (
    Types.isFile(type) &&
    type.wbObjectType != null &&
    Types.isPartitionedTable(type.wbObjectType)
  ) {
    return Op.applyOpToOneOrMany(
      Op.opPartitionedTableRows,
      'partitionedTable',
      Op.opFilePartitionedTable({file: node}),
      {}
    );
  }
  // partitioned-table
  if (Types.isPartitionedTable(type)) {
    return Op.applyOpToOneOrMany(
      Op.opPartitionedTableRows,
      'partitionedTable',
      node,
      {}
    );
  }

  // wb joined-table file
  if (
    Types.isFile(type) &&
    type.wbObjectType != null &&
    Types.isJoinedTable(type.wbObjectType)
  ) {
    return Op.applyOpToOneOrMany(
      Op.opJoinedTableRows,
      'joinedTable',
      Op.opFileJoinedTable({file: node}),
      {
        leftOuter: Op.constBoolean(true),
        rightOuter: Op.constBoolean(true),
      }
    );
  }
  // joined-table
  if (Types.isJoinedTable(type)) {
    return Op.applyOpToOneOrMany(Op.opJoinedTableRows, 'joinedTable', node, {
      leftOuter: Op.constBoolean(true),
      rightOuter: Op.constBoolean(true),
    });
  }

  return node;
}

export function isTableTypeLike(type: Types.Type) {
  type = Types.nullableTaggableValue(type);

  // wb table file
  if (
    Types.isFile(type) &&
    type.wbObjectType != null &&
    Types.isTable(type.wbObjectType)
  ) {
    return true;
  }
  // table
  if (Types.isTable(type)) {
    return true;
  }

  // wb partitioned-table file
  if (
    Types.isFile(type) &&
    type.wbObjectType != null &&
    Types.isPartitionedTable(type.wbObjectType)
  ) {
    return true;
  }
  // partitioned-table
  if (Types.isPartitionedTable(type)) {
    return true;
  }

  // wb joined-table file
  if (
    Types.isFile(type) &&
    type.wbObjectType != null &&
    Types.isJoinedTable(type.wbObjectType)
  ) {
    return true;
  }
  // joined-table
  if (Types.isJoinedTable(type)) {
    return true;
  }

  return false;
}
