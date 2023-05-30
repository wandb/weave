import {
  findChainedAncestor,
  list,
  Node,
  NodeOrVoidNode,
  Type,
  Weave,
} from '@wandb/weave/core';
import * as _ from 'lodash';
import {useCallback} from 'react';

import * as Table from './tableState';
import {typeShapesMatch} from './util';

export enum RowSize {
  Small = 1,
  Medium = 2,
  Large = 3,
  XLarge = 4,
}

// Modified by feature flags
export const TABLE_CONFIG_DEFAULTS = {
  rowSize: RowSize.Medium,
};

export type PanelTableConfig = {
  tableState?: Table.TableState;
  tableStateInputType?: Type;
  rowSize: RowSize;
  indexOffset: number;
  columnWidths: {[key: string]: number};
  pinnedRows: {[groupKey: string]: number[]};
  pinnedColumns: string[];
  activeRowForGrouping: {[groupKey: string]: number};
  simpleTable?: boolean;
};

const tableStateKeys = [
  'autoColumns',
  'columns',
  'preFilterFunction',
  'columnNames',
  'columnSelectFunctions',
  'order',
  'groupBy',
  'sort',
  'pageSize',
  'page',
];

const defaultObj = {};
const defaultArr: any[] = [];

export const migrateConfig = (
  config: any,
  inputNode: NodeOrVoidNode | undefined
): PanelTableConfig => {
  let mConfig = config || {};
  if (mConfig?.combinedTableConfig != null && mConfig?.table == null) {
    mConfig = {
      ..._.omit(mConfig, ['combinedTableConfig']),
      tableState: _.pick(mConfig.combinedTableConfig, tableStateKeys),
    };
  }
  if (
    mConfig != null &&
    mConfig.tableState == null &&
    mConfig.tableStateInputType == null &&
    mConfig.order != null
  ) {
    mConfig = {
      ..._.omit(mConfig, tableStateKeys),
      tableState: _.pick(mConfig, tableStateKeys),
    };
    if ((mConfig.tableState.order ?? []).length > 0) {
      let exampleSelect: Node;
      if ((mConfig.tableState.groupBy ?? []).length > 0) {
        exampleSelect =
          mConfig.tableState.columnSelectFunctions[
            mConfig.tableState.groupBy[0]
          ];
      } else {
        exampleSelect =
          mConfig.tableState.columnSelectFunctions[mConfig.tableState.order[0]];
      }
      const exampleRowNode = findChainedAncestor(
        exampleSelect,
        (inNode: Node) => {
          return inNode.nodeType === 'var' && inNode.varName === 'row';
        },
        () => true
      );
      if (exampleRowNode != null) {
        mConfig.tableStateInputType = list(exampleRowNode.type);
      }
    }
  }

  if (mConfig.rowSize == null) {
    if (mConfig === config) {
      mConfig = {
        ...mConfig,
        rowSize: TABLE_CONFIG_DEFAULTS.rowSize,
      };
    } else {
      mConfig.rowSize = TABLE_CONFIG_DEFAULTS.rowSize;
    }
  }

  if (mConfig.indexOffset == null) {
    if (mConfig === config) {
      mConfig = {
        ...mConfig,
        indexOffset: 0,
      };
    } else {
      mConfig.indexOffset = 0;
    }
  }

  if (mConfig.columnWidths == null) {
    if (mConfig === config) {
      mConfig = {
        ...mConfig,
        columnWidths: defaultObj,
      };
    } else {
      mConfig.columnWidths = defaultObj;
    }
  }

  if (mConfig.pinnedRows == null) {
    if (mConfig === config) {
      mConfig = {
        ...mConfig,
        pinnedRows: defaultObj,
      };
    } else {
      mConfig.pinnedRows = defaultObj;
    }
  }

  if (mConfig.pinnedColumns == null) {
    if (mConfig === config) {
      mConfig = {
        ...mConfig,
        pinnedColumns: defaultArr,
      };
    } else {
      mConfig.pinnedColumns = defaultArr;
    }
  }

  const safeType = typeSafeTableState(mConfig, inputNode?.type);

  if (safeType !== mConfig.tableState) {
    if (mConfig === config) {
      mConfig = {
        ...mConfig,
        tableState: safeType,
      };
    } else {
      mConfig.tableState = safeType;
    }
  }

  return mConfig;
};

const typeSafeTableState = (
  config: PanelTableConfig | undefined,
  incomingType: Type | undefined
) => {
  if (
    config?.tableStateInputType == null ||
    incomingType == null ||
    typeShapesMatch(incomingType, config.tableStateInputType)
  ) {
    return config?.tableState;
  } else {
    return undefined;
  }
};

export const useUpdateConfigRespectingTableType = (
  updateConfig: (partialConfig: Partial<PanelTableConfig>) => void,
  typedInputNode: NodeOrVoidNode<Type> | undefined
) => {
  return useCallback(
    (newConfig: Partial<PanelTableConfig>) => {
      if (newConfig.tableState != null && typedInputNode != null) {
        newConfig.tableStateInputType = typedInputNode.type;
      }
      return updateConfig(newConfig);
    },
    [typedInputNode, updateConfig]
  );
};

export const getTableConfig = (
  node: Node,
  config: any,
  weave: Weave
): PanelTableConfig => {
  const mConfig = migrateConfig(config, node);
  const configNeedsReset =
    mConfig?.tableStateInputType != null &&
    !typeShapesMatch(node.type, mConfig?.tableStateInputType);

  const currentTableState: PanelTableConfig['tableState'] = configNeedsReset
    ? undefined
    : mConfig?.tableState;

  const {table: autoTable} = Table.initTableFromTableType(node, weave);

  const colDiff = Table.tableColumnsDiff(weave, autoTable, currentTableState);
  const isDiff = colDiff.addedCols.length > 0 || colDiff.removedCols.length > 0;

  const tableState =
    currentTableState?.columnNames == null ||
    (currentTableState?.autoColumns === true && isDiff)
      ? autoTable
      : currentTableState;
  return {...mConfig, tableState};
};
