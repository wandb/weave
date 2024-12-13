import React, {createContext, useContext} from 'react';

interface DatasetEditContextType {
  editedCellsMap: Map<string, any>;
  setEditedCellsMap: React.Dispatch<React.SetStateAction<Map<string, any>>>;
  editedRows: Map<string, any>;
  setEditedRows: React.Dispatch<React.SetStateAction<Map<string, any>>>;
  processRowUpdate: (newRow: any, oldRow: any) => any;
  deletedRows: number[];
  setDeletedRows: React.Dispatch<React.SetStateAction<number[]>>;
  addedRows: Map<string, any>;
  setAddedRows: React.Dispatch<React.SetStateAction<Map<string, any>>>;
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
