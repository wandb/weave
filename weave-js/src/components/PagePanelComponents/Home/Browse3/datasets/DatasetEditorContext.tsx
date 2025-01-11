import React, {createContext, useCallback, useContext, useState} from 'react';

interface DatasetRow {
  // id: string | number;
  [key: string]: any;
  ___weave: {
    id: string;
    // The index must be set for rows of an existing dataset.
    index?: number;
    isNew?: boolean;
  };
}

interface EditedCell {
  [fieldName: string]: unknown;
}

interface DatasetEditContextType {
  /** Map of edited cells, keyed by row absolute index */
  editedCellsMap: Map<number, EditedCell>;
  setEditedCellsMap: React.Dispatch<
    React.SetStateAction<Map<number, EditedCell>>
  >;
  /** Map of complete edited rows, keyed by row absolute index */
  editedRows: Map<number, DatasetRow>;
  setEditedRows: React.Dispatch<React.SetStateAction<Map<number, DatasetRow>>>;
  /** Callback to process row updates from the data grid */
  processRowUpdate: (newRow: DatasetRow, oldRow: DatasetRow) => DatasetRow;
  /** Array of row indices that have been marked for deletion */
  deletedRows: number[];
  setDeletedRows: React.Dispatch<React.SetStateAction<number[]>>;
  /** Map of newly added rows, keyed by temporary row ID */
  addedRows: Map<string, DatasetRow>;
  setAddedRows: React.Dispatch<React.SetStateAction<Map<string, DatasetRow>>>;
  /** Reset the context to its initial state */
  reset: () => void;
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
}

export const DatasetEditProvider: React.FC<DatasetEditProviderProps> = ({
  children,
}) => {
  const [editedCellsMap, setEditedCellsMap] = useState<Map<number, EditedCell>>(
    new Map()
  );
  const [editedRows, setEditedRows] = useState<Map<number, DatasetRow>>(
    new Map()
  );
  const [deletedRows, setDeletedRows] = useState<number[]>([]);
  const [addedRows, setAddedRows] = useState<Map<string, DatasetRow>>(
    new Map()
  );

  const processRowUpdate = useCallback(
    (newRow: DatasetRow, oldRow: DatasetRow): DatasetRow => {
      const changedField = Object.keys(newRow).find(
        key => newRow[key] !== oldRow[key] && key !== 'id'
      );

      if (changedField) {
        const rowKey = String(oldRow.___weave.id);
        const rowIndex = oldRow.___weave.index;
        if (oldRow.___weave.isNew) {
          setAddedRows(prev => {
            const updatedMap = new Map(prev);
            updatedMap.set(rowKey, newRow);
            return updatedMap;
          });
        } else {
          setEditedCellsMap(prev => {
            const existingEdits = prev.get(rowIndex!) || {};
            const updatedMap = new Map(prev);
            updatedMap.set(rowIndex!, {
              ...existingEdits,
              [changedField]: newRow[changedField],
            });
            return updatedMap;
          });
          setEditedRows(prev => {
            const updatedMap = new Map(prev);
            updatedMap.set(rowIndex!, newRow);
            return updatedMap;
          });
        }
      }
      return newRow;
    },
    []
  );

  const reset = useCallback(() => {
    setEditedCellsMap(new Map());
    setEditedRows(new Map());
    setDeletedRows([]);
    setAddedRows(new Map());
  }, []);

  return (
    <DatasetEditContext.Provider
      value={{
        editedCellsMap,
        setEditedCellsMap,
        editedRows,
        setEditedRows,
        processRowUpdate,
        deletedRows,
        setDeletedRows,
        addedRows,
        setAddedRows,
        reset,
      }}>
      {children}
    </DatasetEditContext.Provider>
  );
};
