import React, {createContext, useCallback, useContext, useState} from 'react';

export interface DatasetRow {
  [key: string]: any;
  ___weave: {
    id: string;
    index?: number;
    isNew?: boolean;
    serverValue?: any;
    editedFields?: Set<string>; // Set of field paths that have been edited
  };
}

interface DatasetEditContextType {
  /** Map of complete edited rows, keyed by row absolute index */
  editedRows: Map<number, DatasetRow>;
  setEditedRows: React.Dispatch<React.SetStateAction<Map<number, DatasetRow>>>;
  /** Check if a specific field in a row has been edited */
  isFieldEdited: (rowIndex: number, fieldName: string) => boolean;
  /** Mark a field as edited or not edited within the row object */
  setFieldEdited: (
    rowIndex: number,
    fieldName: string,
    isEdited: boolean
  ) => void;
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
  /** Get rows without any mui datagrid or weave metadata */
  getRowsNoMeta: () => Array<Record<string, any>>;
  /** Update cell value and track edit state */
  updateCellValue: (
    row: DatasetRow,
    field: string,
    newValue: any,
    serverValue: any,
    preserveFieldOrder?: (row: DatasetRow) => DatasetRow
  ) => void;
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

  const isFieldEdited = useCallback(
    (rowIndex: number, fieldName: string): boolean => {
      const editedRow = editedRows.get(rowIndex);
      if (!editedRow) {
        return false;
      }

      return editedRow.___weave?.editedFields?.has(fieldName) ?? false;
    },
    [editedRows]
  );

  const setFieldEdited = useCallback(
    (rowIndex: number, fieldName: string, isEdited: boolean) => {
      setEditedRows(prev => {
        const newMap = new Map(prev);
        const row = newMap.get(rowIndex);

        if (!row) {
          return newMap;
        }

        if (!row.___weave.editedFields) {
          row.___weave.editedFields = new Set<string>();
        }

        if (isEdited) {
          row.___weave.editedFields.add(fieldName);
        } else {
          row.___weave.editedFields.delete(fieldName);
        }

        if (row.___weave.editedFields.size === 0 && !row.___weave.isNew) {
          newMap.delete(rowIndex);
        } else {
          newMap.set(rowIndex, row);
        }

        return newMap;
      });
    },
    [setEditedRows]
  );

  const updateCellValue = useCallback(
    (
      row: DatasetRow,
      field: string,
      newValue: any,
      serverValue: any,
      preserveFieldOrder?: (row: DatasetRow) => DatasetRow
    ) => {
      const existingRow = {...row};
      const updatedRow = {...existingRow};
      updatedRow[field] = newValue;

      const finalRow = preserveFieldOrder
        ? preserveFieldOrder(updatedRow)
        : updatedRow;

      const isValueChanged = newValue !== serverValue;

      if (existingRow.___weave?.isNew) {
        // For newly added rows
        setAddedRows(prev => {
          const newMap = new Map(prev);
          if (existingRow.___weave?.id) {
            newMap.set(existingRow.___weave.id, finalRow);
          }
          return newMap;
        });
      } else {
        // For existing rows
        if (!finalRow.___weave) {
          // If ___weave object is missing completely, recreate it with required properties
          const rowId = existingRow.___weave?.id || `generated-${Date.now()}`;
          finalRow.___weave = {
            id: rowId,
            index: existingRow.___weave?.index,
            editedFields: new Set<string>(),
          };
        } else if (!finalRow.___weave.editedFields) {
          finalRow.___weave.editedFields = new Set<string>();
        }

        // Ensure editedFields exists before using it
        if (!finalRow.___weave.editedFields) {
          finalRow.___weave.editedFields = new Set<string>();
        }

        if (isValueChanged) {
          finalRow.___weave.editedFields.add(field);
        } else {
          finalRow.___weave.editedFields.delete(field);
        }

        // Only process if we have a valid row index
        const rowIndex = existingRow.___weave?.index;
        if (rowIndex !== undefined) {
          setEditedRows(prev => {
            const newMap = new Map(prev);

            // We can now safely access editedFields since we ensured it exists above
            // Use non-null assertion operator to tell TypeScript we guarantee editedFields exists
            if (finalRow.___weave.editedFields!.size === 0) {
              newMap.delete(rowIndex);
            } else {
              newMap.set(rowIndex, finalRow);
            }

            return newMap;
          });

          setFieldEdited(rowIndex, field, isValueChanged);
        }
      }
    },
    [setAddedRows, setEditedRows, setFieldEdited]
  );

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

  const getRowsNoMeta = useCallback(() => {
    const allRows = [
      ...Array.from(addedRows.values()),
      ...Array.from(editedRows.values()),
    ]
      .filter((_, index) => !deletedRows.includes(index))
      .map(row => cleanRow(row));
    return allRows;
  }, [addedRows, cleanRow, deletedRows, editedRows]);

  return (
    <DatasetEditContext.Provider
      value={{
        editedRows,
        setEditedRows,
        isFieldEdited,
        setFieldEdited,
        deletedRows,
        setDeletedRows,
        addedRows,
        setAddedRows,
        resetEditState: reset,
        convertEditsToTableUpdateSpec,
        getRowsNoMeta,
        updateCellValue,
      }}>
      {children}
    </DatasetEditContext.Provider>
  );
};
