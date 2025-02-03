import _ from 'lodash';

import {ObjectPath, traverse, ValueType} from '../pages/CallPage/traverse';
import {isExpandableRef} from '../pages/wfReactInterface/tsDataModelHooksCallRefExpansion';
import {RESOLVED_REF_KEY} from './refUtil';
import {ComparableObject} from './types';

// Row change types
export const UNCHANGED = 'UNCHANGED';
export const DELETED = 'DELETED';
export const ADDED = 'ADDED';
export const CHANGED = 'CHANGED';
export type RowChangeType =
  | typeof UNCHANGED
  | typeof DELETED
  | typeof ADDED
  | typeof CHANGED;

export const MISSING = '__WEAVE_MISSING__';
export const CODE = 'code';
export type ColumnType = ValueType | typeof MISSING | typeof CODE;
export type ColumnId = string;

export type RowData = {
  // Row id is the string representation of path
  id: string;
  path: ObjectPath;
  values: Record<ColumnId, any>;
  types: Record<ColumnId, any>; // ColumnType
  isCode?: boolean;
};

export type RowDataWithDiff = RowData & {
  // Overall row change type, used for filtering rows and coloring grouping column
  changeType: RowChangeType;
  changeTypes: Record<ColumnId, RowChangeType>;
  expandableRefs: string[];
};

type PathString = string;
type PathInfo = {
  path: ObjectPath;
  values: Record<ColumnId, any>;
  types: Record<ColumnId, ColumnType>;
  isCode?: boolean;
};

export const mergeObjects = (
  columnIds: string[],
  objects: ComparableObject[]
): RowData[] => {
  const values: Record<PathString, PathInfo> = {};

  for (let i = 0; i < columnIds.length; i++) {
    const columnId = columnIds[i];
    const object = objects[i];
    traverse(object, context => {
      // Ops should be migrated to the generic CustomWeaveType pattern, but for
      // now they are custom handled.
      const isOpPayload = context.value?.weave_type?.type === 'Op';

      if (context.path.tail() === RESOLVED_REF_KEY) {
        return 'skip';
      }
      const key = context.path.toString();
      if (!(key in values)) {
        values[key] = {
          path: context.path,
          values: {},
          types: {},
        };
      }
      values[key].values[columnId] = context.value;
      values[key].types[columnId] = context.valueType;

      if (isOpPayload) {
        const codeKey = key + '.code';
        if (!(codeKey in values)) {
          values[codeKey] = {
            isCode: true,
            path: context.path.plus('code'),
            values: {},
            types: {},
          };
        }
        values[codeKey].values[columnId] = context.value._ref;
        values[codeKey].types[columnId] = 'code';
      }
      return isOpPayload ? 'skip' : true;
    });
  }

  const rows: RowData[] = [];
  for (const d of Object.values(values)) {
    rows.push({
      id: d.path.toString(),
      isCode: d.isCode,
      path: d.path,
      values: d.values,
      types: d.types,
    });
  }

  return rows;
};

export const computeDiff = (
  columnIds: ColumnId[],
  rows: RowData[],
  againstBaseline: boolean
): RowDataWithDiff[] => {
  const nCols = columnIds.length;
  const diffRows: RowDataWithDiff[] = [];
  for (const row of rows) {
    let rowChangeType: RowChangeType = UNCHANGED;
    const changeTypes: Record<ColumnId, RowChangeType> = {};
    changeTypes[columnIds[0]] = UNCHANGED;
    for (let i = 1; i < nCols; i++) {
      const leftIdx = againstBaseline ? 0 : i - 1;
      const rightName = columnIds[i];
      const left = row.values[columnIds[leftIdx]];
      const right = row.values[rightName];
      let changeType: RowChangeType = UNCHANGED;
      // TODO: Handle added/deleted and missing
      if (!_.isEqual(left, right)) {
        changeType = CHANGED;
        rowChangeType = CHANGED;
      }
      changeTypes[rightName] = changeType;
    }
    const rowWithDiff: RowDataWithDiff = {
      ...row,
      changeType: rowChangeType,
      changeTypes,
      expandableRefs: _.uniq(Object.values(row.values).filter(isExpandableRef)),
    };
    diffRows.push(rowWithDiff);
  }
  return diffRows;
};
