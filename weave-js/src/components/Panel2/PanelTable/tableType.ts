import {
  applyOpToOneOrMany,
  constBoolean,
  isFile,
  isJoinedTable,
  isListLike,
  isPartitionedTable,
  isTable,
  listObjectType,
  Node,
  nullableTaggableValue,
  opFileJoinedTable,
  opFilePartitionedTable,
  opFileTable,
  opJoinedTableRows,
  opPartitionedTableRows,
  opTableRows,
  Stack,
  Type,
} from '@wandb/weave/core';

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

export function normalizeTableLike(node: Node, stack: Stack = []) {
  let type = nullableTaggableValue(node.type);

  if (isListLike(type)) {
    type = nullableTaggableValue(listObjectType(type));
  }

  // wb table file
  if (isFile(type) && type.wbObjectType != null && isTable(type.wbObjectType)) {
    // todo(dom): Disabling this for now
    // if (isSingleRunWorkspace(stack) && !hasRunHistoryOp(node)) {
    //   // The only time incremental table should be loaded is in a
    //   // single run workspace and not via run history.
    //   // We want to display the increment at that history when using
    //   // the stepper.
    //   return opTableRows({table: opFileTableWithIncrements({file: node})});
    // }
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

  return node;
}

export function isTableTypeLike(type: Type) {
  type = nullableTaggableValue(type);

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
  // joined-table
  if (isJoinedTable(type)) {
    return true;
  }

  return false;
}

// todo(dom): restore these when we're ready for incremental tables
// const isSingleRunWorkspace = (stack: Stack) => {
//   const singleRunWorkspaceVar = stack.find(
//     stackVar => stackVar.name === 'singleRunWorkspace'
//   );

//   if (
//     singleRunWorkspaceVar == null ||
//     !isConstNode(singleRunWorkspaceVar.value)
//   ) {
//     return false;
//   }

//   return singleRunWorkspaceVar.value.val;
// };

// const hasRunHistoryOp = (node: Node): boolean => {
//   const hasRunHistoryOpPattern = (currentNode: any): boolean => {
//     if (!currentNode?.fromOp) {
//       return false;
//     }

//     const opName = currentNode.fromOp.name;

//     if (opName === 'run-history') {
//       return true;
//     }

//     const inputs = currentNode.fromOp.inputs;
//     if (inputs) {
//       return Object.values(inputs).some(
//         input =>
//           input != null && isOutputNode(input) && hasRunHistoryOpPattern(input)
//       );
//     }

//     return false;
//   };

//   return node.nodeType === 'output' && hasRunHistoryOpPattern(node);
// };
