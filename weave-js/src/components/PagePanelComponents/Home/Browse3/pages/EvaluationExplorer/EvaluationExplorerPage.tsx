import React, { useState, useEffect } from 'react';
import { GridRowsProp, GridRowModesModel, GridRowModes, GridRowId } from '@mui/x-data-grid-pro';
import { v4 as uuidv4 } from 'uuid';
import { SimplePageLayoutWithHeader } from '../common/SimplePageLayout';
import { ConfigurationBar } from './ConfigurationBar';
import { EvaluationDataGrid } from './components';
import { EvaluationExplorerPageProps, EvaluationRow } from './types';
import { calculateRowDigest, deepCloneRow, createEmptyRow } from './utils';

export const EvaluationExplorerPage = (props: EvaluationExplorerPageProps) => {
  return (
    <SimplePageLayoutWithHeader
      title="EvaluationExplorer"
      hideTabsIfSingle
      headerContent={null}
      tabs={[
        {
          label: 'main',
          content: <EvaluationExplorerPageInner {...props} />
        },
      ]}
      headerExtra={null}
    />
  );
};

const DEFAULT_DATASET_COLUMNS = ['columnA', 'columnB'];

const createInitialRow = (): EvaluationRow => ({
  id: "1",
  dataset: {
    columnA: "Value A1",
    columnB: "Value B1",
  },
  output: {
    modelA: [{"key": "val"}],
    modelB: [{"key": "val"}]
  },
  scores: {
    scorerA: {
      modelA: { score: "1", reason: "A" },
      modelB: { score: "1", reason: "A" }
    }
  }
});

export const EvaluationExplorerPageInner: React.FC<EvaluationExplorerPageProps> = ({ entity, project }) => {
  const [selectedDatasetId, setSelectedDatasetId] = useState<string>('dataset-1');
  const [isDatasetEdited, setIsDatasetEdited] = useState(false);
  const [selectedModelIds, setSelectedModelIds] = useState<string[]>([]);
  
  const initialRow = createInitialRow();
  const [originalRows, setOriginalRows] = useState<GridRowsProp>([initialRow]);
  const [rows, setRows] = useState<GridRowsProp>([initialRow]);
  const [datasetColumns, setDatasetColumns] = useState<string[]>(DEFAULT_DATASET_COLUMNS);
  const [rowModesModel, setRowModesModel] = useState<GridRowModesModel>({});

  // Check if dataset has been edited
  useEffect(() => {
    const hasBeenEdited = JSON.stringify(rows) !== JSON.stringify(originalRows);
    setIsDatasetEdited(hasBeenEdited);
  }, [rows, originalRows]);

  // Update row digests whenever rows change
  useEffect(() => {
    setRows(prevRows => 
      prevRows.map(row => ({
        ...row,
        dataset: {
          ...row.dataset,
          rowDigest: calculateRowDigest(row)
        }
      }))
    );
  }, [rows.length]); // Only recalculate when rows are added/removed

  const handleDeleteRow = (id: GridRowId) => {
    setRows(prevRows => prevRows.filter((row) => row.id !== id));
  };

  const handleDuplicateRow = (id: GridRowId) => {
    const rowToDuplicate = rows.find(row => row.id === id);
    if (rowToDuplicate) {
      const newRow = {
        ...deepCloneRow(rowToDuplicate as EvaluationRow),
        id: uuidv4()
      };
      setRows(prevRows => [...prevRows, newRow]);
    }
  };

  const handleAddRow = () => {
    const newId = uuidv4();
    setDatasetColumns(currentColumns => {
      const newRow = createEmptyRow(newId, currentColumns);
      
      setRows(prevRows => [...prevRows, newRow]);
      setRowModesModel(prevModel => ({
        ...prevModel,
        [newId]: { mode: GridRowModes.Edit },
      }));
      
      return currentColumns;
    });
  };

  const handleAddColumn = () => {
    setDatasetColumns(prevColumns => {
      const columnName = `column${prevColumns.length + 1}`;
      
      // Add the new column to all existing rows
      setRows(prevRows => prevRows.map(row => ({
        ...row,
        dataset: {
          ...row.dataset,
          [columnName]: ''
        }
      })));
      
      return [...prevColumns, columnName];
    });
  };

  const handleDeleteColumn = (columnName: string) => {
    setDatasetColumns(prevColumns => prevColumns.filter(col => col !== columnName));
    
    // Remove the column from all rows
    setRows(prevRows => prevRows.map(row => {
      const newDataset = { ...row.dataset };
      delete newDataset[columnName];
      return {
        ...row,
        dataset: newDataset
      };
    }));
  };

  const handleDatasetChange = (datasetId: string) => {
    if (datasetId === 'create-new') {
      // Clear all data for new dataset
      setSelectedDatasetId('new-dataset');
      setRows([]);
      setOriginalRows([]);
      setIsDatasetEdited(false);
      // Reset columns to default
      setDatasetColumns(DEFAULT_DATASET_COLUMNS);
    } else {
      setSelectedDatasetId(datasetId);
      // TODO: Load dataset data
      // For now, just reset to example data
      const newRows = [{
        id: "1",
        dataset: {
          columnA: `Data from ${datasetId}`,
          columnB: "New Value",
        },
        output: {
          modelA: [],
          modelB: []
        },
        scores: {}
      }];
      setRows(newRows);
      setOriginalRows(newRows);
      setIsDatasetEdited(false);
    }
  };

  const handleModelsChange = (modelIds: string[]) => {
    setSelectedModelIds(modelIds);
    // TODO: Update output columns based on selected models
    console.log('Selected models:', modelIds);
  };

  return (
    <Container>
      <DataContainer>
        <EvaluationDataGrid
          rows={rows}
          datasetColumns={datasetColumns}
          rowModesModel={rowModesModel}
          onRowsChange={setRows}
          onRowModesModelChange={setRowModesModel}
          onAddRow={handleAddRow}
          onAddColumn={handleAddColumn}
          onDeleteColumn={handleDeleteColumn}
          onDeleteRow={handleDeleteRow}
          onDuplicateRow={handleDuplicateRow}
        />
      </DataContainer>
      <ConfigurationBar
        selectedDatasetId={selectedDatasetId}
        isDatasetEdited={isDatasetEdited}
        onDatasetChange={handleDatasetChange}
        selectedModelIds={selectedModelIds}
        onModelsChange={handleModelsChange}
      />
    </Container>
  );
};

// Styled components
const Container: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div style={{
    width: '100%',
    height: '100%',
    position: 'relative',
    overflow: 'hidden'
  }}>
    {children}
  </div>
);

const DataContainer: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div style={{
    display: 'flex',
    flexDirection: 'column',
    width: '100%',
    height: '100%',
    paddingRight: '48px',
    position: 'relative',
    overflow: 'hidden'
  }}>
    {children}
  </div>
);