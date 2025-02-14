import isEqual from 'lodash/isEqual';
import React, {createContext, useCallback, useContext, useState} from 'react';

import {flattenObjectPreservingWeaveTypes} from '../flattenObject';

export interface DatasetRow {
  [key: string]: any;
  ___weave: {
    id: string;
    index?: number;
    isNew?: boolean;
    serverValue?: any;
  };
}

interface DatasetEditContextType {
  /** Map of complete edited rows, keyed by row absolute index */
  editedRows: Map<number, DatasetRow>;
  setEditedRows: React.Dispatch<React.SetStateAction<Map<number, DatasetRow>>>;
  /** Get edited fields for a row */
  getEditedFields: (rowIndex: number) => {[fieldName: string]: unknown};
  /** Array of row indices that have been marked for deletion */
  deletedRows: number[];
  setDeletedRows: React.Dispatch<React.SetStateAction<number[]>>;
  /** Map of newly added rows, keyed by temporary row ID */
  addedRows: Map<string, DatasetRow>;
  setAddedRows: React.Dispatch<React.SetStateAction<Map<string, DatasetRow>>>;
  /** Reset the context to its initial state */
  resetEditState: () => void;
  /** Convert current edits to table update spec */
  convertEditsToTableUpdateSpec: () => Array<
    {pop: {index: number}} | {insert: {index: number; row: Record<string, any>}}
  >;
}

export const DatasetEditContext = createContext<
  DatasetEditContextType | undefined
>(undefined);

export const useDatasetEditContext = () => {
  const context = useContext(DatasetEditContext);
  if (!context) {
    throw new Error(
      'useDatasetEditContext must be used within a DatasetEditProvider'
    );
  }
  return context;
};

interface DatasetEditProviderProps {
  children: React.ReactNode;
  initialAddedRows?: Map<string, DatasetRow>;
}

export const DatasetEditProvider: React.FC<DatasetEditProviderProps> = ({
  children,
  initialAddedRows,
}) => {
  const [editedRows, setEditedRows] = useState<Map<number, DatasetRow>>(
    new Map()
  );
  const [deletedRows, setDeletedRows] = useState<number[]>([]);
  const [addedRows, setAddedRows] = useState<Map<string, DatasetRow>>(
    initialAddedRows || new Map()
  );

  const getEditedFields = useCallback(
    (rowIndex: number) => {
      const editedRow = editedRows.get(rowIndex);
      const originalRow = editedRow?.___weave?.serverValue ?? editedRow;
      if (!editedRow) {
        return {};
      }
      const flattenedOriginalRow =
        flattenObjectPreservingWeaveTypes(originalRow);
      const flattenedEditedRow = flattenObjectPreservingWeaveTypes(editedRow);
      return Object.fromEntries(
        Object.entries(flattenedEditedRow).filter(
          ([key, value]) =>
            !key.startsWith('___weave') &&
            !isEqual(value, flattenedOriginalRow[key])
        )
      );
    },
    [editedRows]
  );

  // Cleanup effect to remove rows that no longer have any edits
  // from the editedRows map.
  React.useEffect(() => {
    const rowsToRemove: number[] = [];
    editedRows.forEach((editedRow, rowIndex) => {
      const fields = getEditedFields(rowIndex);
      if (Object.keys(fields).length === 0) {
        rowsToRemove.push(rowIndex);
      }
    });

    if (rowsToRemove.length > 0) {
      setEditedRows(prev => {
        const newMap = new Map(prev);
        rowsToRemove.forEach(index => newMap.delete(index));
        return newMap;
      });
    }
  }, [editedRows, getEditedFields]);

  const reset = useCallback(() => {
    setEditedRows(new Map());
    setDeletedRows([]);
    setAddedRows(new Map());
  }, []);

  const cleanRow = useCallback((row: DatasetRow) => {
    return Object.fromEntries(
      Object.entries(row).filter(([key]) => !['___weave'].includes(key))
    );
  }, []);

  const convertEditsToTableUpdateSpec = useCallback(() => {
    const updates: Array<
      | {pop: {index: number}}
      | {insert: {index: number; row: Record<string, any>}}
    > = [];

    editedRows.forEach((editedRow, rowIndex) => {
      if (rowIndex !== undefined) {
        updates.push({pop: {index: rowIndex}});
        updates.push({
          insert: {
            index: rowIndex,
            row: cleanRow(editedRow),
          },
        });
      }
    });

    deletedRows
      .sort((a, b) => b - a)
      .forEach(rowIndex => {
        updates.push({pop: {index: rowIndex}});
      });

    Array.from(addedRows.values())
      .reverse()
      .forEach(row => {
        updates.push({
          insert: {
            index: 0,
            row: cleanRow(row),
          },
        });
      });

    return updates;
  }, [editedRows, deletedRows, addedRows, cleanRow]);

  return (
    <DatasetEditContext.Provider
      value={{
        editedRows,
        setEditedRows,
        getEditedFields,
        deletedRows,
        setDeletedRows,
        addedRows,
        setAddedRows,
        resetEditState: reset,
        convertEditsToTableUpdateSpec,
      }}>
      {children}
    </DatasetEditContext.Provider>
  );
};
