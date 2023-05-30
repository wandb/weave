import _ from 'lodash';
import moment from 'moment';

import {TableCellValue, TableMetadata} from '../types/media';

// msSaveOrOpenBlob is deprecated and no longer recommended to be used.
// This logic needs to be at the top of the file of where it is used
// so typescript doesn't complain and force us to do (window.navigator as any).
declare global {
  interface Navigator {
    msSaveOrOpenBlob: (blob: Blob | string, filename: string) => void;
  }
}

export interface Table {
  cols: string[];
  data: TableRow[];
}

export interface TableRow {
  [col: string]: any;
}

export const saveTableAsCSV = (table: Table) =>
  saveTextAsCSV(tableToCSV(table), getExportFilename());

const getExportFilename = () =>
  `wandb_export_${moment().toISOString(true)}.csv`;

const tableToCSV = ({cols, data}: Table) =>
  [
    cols.map(String).map(escape).join(','),
    ...data.map(tableRow =>
      cols.map(c => escape(String(tableRow[c]))).join(',')
    ),
  ].join('\n');

const escape = (str: string) => {
  const escaped = str.replace(/"/g, '""');
  return `"${escaped}"`;
};

export function saveTextAsCSV(text: string, filename: string) {
  let type = '';
  const splitFilename = filename.split('.');
  if (splitFilename.length > 1) {
    const extension = splitFilename[splitFilename.length - 1];
    type = `text/${extension}`;
  }
  const file = new Blob([text], {type});

  // IE10+
  // https://developer.mozilla.org/en-US/docs/Web/API/Navigator/msSaveOrOpenBlob
  if (window.navigator.msSaveOrOpenBlob) {
    window.navigator.msSaveOrOpenBlob(file, filename);
    return;
  }

  const a = document.createElement('a');
  const url = URL.createObjectURL(file);
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  });
}

export const saveMediaTableAsCSV = (mediaTable: TableMetadata) =>
  saveTableAsCSV(fromMediaTable(mediaTable));

const fromMediaTable = (mediaTable: TableMetadata): Table => {
  const cols = mediaTable.columns.map(c => c.toString());
  const data: TableRow[] = [];
  mediaTable.data?.forEach(
    (mediaRowData: TableCellValue | TableCellValue[]) => {
      if (!_.isArray(mediaRowData)) {
        return;
      }
      const rowData: TableRow = {};
      data.push(rowData);
      mediaRowData.forEach((d, i) => (rowData[cols[i]] = d));
    }
  );
  return {cols, data};
};
