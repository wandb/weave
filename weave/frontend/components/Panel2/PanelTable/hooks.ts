import {useCallback} from 'react';
import * as Table from './tableState';
import {makeEventRecorder} from '../panellib/libanalytics';

const recordEvent = makeEventRecorder('Table');

export function useUpdatePanelConfig(
  updateTableState: (newTableState: Table.TableState) => void,
  tableState: Table.TableState,
  colId: string
) {
  return useCallback(
    (newPanelConfig: any) => {
      recordEvent('UPDATE_PANEL_CONFIG');
      return updateTableState(
        Table.updateColumnPanelConfig(tableState, colId, newPanelConfig)
      );
    },
    [colId, tableState, updateTableState]
  );
}
