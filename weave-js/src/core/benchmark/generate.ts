// Utils for generating test data

import {constNodeUnsafe} from '../model/graph/construction';
import {NUM_UUIDS, UUIDS} from './stringConstants';

interface ColOptions {
  name: (colIndex: number) => string;
  value: (colIndex: number, rowIndex: number) => any;
}

export interface TestTableOptions {
  cols: ColOptions[];
  nRows: number;
}

export function createTestTable(opts: TestTableOptions) {
  const result = new Array(opts.nRows);
  for (let rowIndex = 0; rowIndex < opts.nRows; rowIndex++) {
    result[rowIndex] = opts.cols.map((col, colIndex) =>
      col.value(colIndex, rowIndex)
    );
  }

  return constNodeUnsafe(
    {
      type: 'table',
      columnTypes: {},
    },
    {
      type: 'table',
      columns: opts.cols.map((col, colIndex) => col.name(colIndex)),
      data: result,
    }
  );
}

export function nthTestColumn(index: number): ColOptions {
  const pool: ColOptions[] = [
    {
      name: idx => `string${idx}`,
      value: idx => UUIDS[Math.floor(Math.random() * NUM_UUIDS)],
    },
    {
      name: idx => `integer${idx}`,
      value: idx => Math.floor(Math.random() * 1000),
    },
    {
      name: idx => `float${idx}`,
      value: idx => Math.random(),
    },
    {
      name: idx => `boolean${idx}`,
      value: idx => Math.random() >= 0.5,
    },
  ];

  return pool[index % pool.length];
}
