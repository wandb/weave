import {GridColumnVisibilityModel} from '@mui/x-data-grid-pro';
import stringify from 'json-stable-stringify';
import _ from 'lodash';

import {isRef} from '../Browse3/pages/common/util';

type ValueType =
  | 'undefined'
  | 'null'
  | 'boolean'
  | 'string'
  | 'number'
  | 'other';

const determineType = (value: any): ValueType => {
  if (value === null) {
    return 'null';
  }
  if (value === undefined) {
    return 'undefined';
  }
  if (typeof value === 'boolean') {
    return 'boolean';
  }
  if (typeof value === 'string') {
    return 'string';
  }
  if (typeof value === 'number') {
    return 'number';
  }
  return 'other';
};

type ColumnStats = {
  valueCount: number;
  // TODO: Would make code more complex but could only store counts for types seen
  typeCounts: Record<ValueType, number>;
  refCounts: Record<string, number>;
  valueCounts: Record<any, number>;
};
export type TableStats = {
  rowCount: number;
  column: Record<string, ColumnStats>;
};

export const computeTableStats = (table: Array<Record<string, any>>) => {
  const stats: TableStats = {
    rowCount: 0,
    column: {},
  };

  // Determine set of possible columns and value types
  const colPatterns: RegExp[] = [
    /^userId$/,
    /^opCategory$/,
    /^inputs\..*$/,
    /^output\..*$/,
  ];
  for (const row of table) {
    stats.rowCount++;
    for (const colName of Object.keys(row)) {
      for (const colPattern of colPatterns) {
        if (colPattern.test(colName)) {
          if (!(colName in stats.column)) {
            stats.column[colName] = {
              valueCount: 0,
              typeCounts: {
                undefined: 0,
                null: 0,
                boolean: 0,
                string: 0,
                number: 0,
                other: 0,
              },
              refCounts: {},
              valueCounts: {},
            };
          }
          const colStats = stats.column[colName];
          colStats.valueCount += 1;
          const value = row[colName];
          const valueType = determineType(value);
          colStats.typeCounts[valueType] += 1;
          // Keep track of unique refs seen in column
          if (isRef(value)) {
            if (!(value in colStats.refCounts)) {
              colStats.refCounts[value] = 0;
            }
            colStats.refCounts[value] += 1;
          }
          let valueStr = null;
          if (Array.isArray(value) || _.isPlainObject(value)) {
            try {
              valueStr = stringify(value);
            } catch (e) {
              valueStr = `${value}`;
            }
          } else {
            valueStr = `${value}`;
          }
          if (!(valueStr in colStats.valueCounts)) {
            colStats.valueCounts[valueStr] = 0;
          }
          colStats.valueCounts[valueStr] += 1;
        }
      }
    }
  }

  // TODO: Now that we have an understanding of column value types,
  //       we might compute type-specific stats like min/max.

  return stats;
};

export const useColumnVisibility = (
  tableStats: TableStats,
  isSingleOpVersion: boolean
) => {
  const boringColumns = getBoringColumns(tableStats);

  const model: GridColumnVisibilityModel = {};
  for (const colName in tableStats.column) {
    if (boringColumns.includes(colName)) {
      model[colName] = false;
    } else if (isSingleOpVersion) {
      model[colName] = true;
    } else {
      const colStats = tableStats.column[colName];
      if (colStats.typeCounts.null === tableStats.rowCount) {
        model[colName] = false;
      } else {
        const haveValueFraction = colStats.valueCount / tableStats.rowCount;
        model[colName] = haveValueFraction > 0.2;
      }
    }
  }
  // TODO: Should we also put a limit on the number of trues in model?
  const allShown = Object.values(model).every(v => v);
  return {
    allShown,
    columnVisibilityModel: model,
  };
};

export const getInputColumns = (tableStats: TableStats): string[] => {
  return Object.keys(tableStats.column)
    .filter(colName => colName.startsWith('inputs.'))
    .map(colName => colName.substring(7));
};

// Get a list of "boring" columns.
// Boring columns are those that have the same value for every row.
export const getBoringColumns = (tableStats: TableStats): string[] => {
  const columns = Object.keys(tableStats.column);
  const boring: string[] = [];
  if (tableStats.rowCount < 2) {
    // Would be confusing to have "common" values when there is only one row.
    return [];
  }
  const allNull = new Set<string>();
  for (const col of columns) {
    if (col.startsWith('output.') || col === 'output') {
      // For now, output is always interesting
      continue;
    }
    const {typeCounts, valueCounts} = tableStats.column[col];
    const values = Object.values(valueCounts);
    if (values.length === 1 && values[0] === tableStats.rowCount) {
      boring.push(col);
      if (typeCounts.null === tableStats.rowCount) {
        allNull.add(col);
      }
    }
  }

  return boring;
};

// Return the unique ref values in the column.
export const columnRefs = (
  tableStats: TableStats,
  colName: string
): string[] => {
  const colStats = tableStats.column[colName];
  if (!colStats) {
    return [];
  }
  return Object.keys(colStats.refCounts);
};

// Return true if there are any ref values in the column.
export const columnHasRefs = (
  tableStats: TableStats,
  colName: string
): boolean => {
  const refs = columnRefs(tableStats, colName);
  return refs.length > 0;
};
