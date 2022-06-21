import * as _ from 'lodash';
import * as HL from '@wandb/cg/browser/hl';
import * as Types from '@wandb/cg/browser/model/types';

import {useCallback} from 'react';

import * as Table from './tableState';
import {typeShapesMatch} from './util';

export enum RowSize {
  Small = 1,
  Medium = 2,
  Large = 3,
  XLarge = 4,
}

export type PanelTableConfig = {
  tableState?: Table.TableState;
  tableStateInputType?: Types.Type;
  rowSize: RowSize;
  indexOffset: number;
  columnWidths: {[key: string]: number};
  pinnedRows: {[groupKey: string]: number[]};
  pinnedColumns: string[];
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
  inputNode: Types.NodeOrVoidNode | undefined
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
      let exampleSelect: Types.Node;
      if ((mConfig.tableState.groupBy ?? []).length > 0) {
        exampleSelect =
          mConfig.tableState.columnSelectFunctions[
            mConfig.tableState.groupBy[0]
          ];
      } else {
        exampleSelect =
          mConfig.tableState.columnSelectFunctions[mConfig.tableState.order[0]];
      }
      const exampleRowNode = HL.findChainedAncestor(
        exampleSelect,
        (inNode: Types.Node) => {
          return inNode.nodeType === 'var' && inNode.varName === 'row';
        },
        () => true
      );
      if (exampleRowNode != null) {
        mConfig.tableStateInputType = Types.list(exampleRowNode.type);
      }
    }
  }

  if (mConfig.rowSize == null) {
    if (mConfig === config) {
      mConfig = {
        ...mConfig,
        rowSize: RowSize.Medium,
      };
    } else {
      mConfig.rowSize = RowSize.Medium;
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
  incomingType: Types.Type | undefined
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
  typedInputNode: Types.NodeOrVoidNode<Types.Type> | undefined
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
