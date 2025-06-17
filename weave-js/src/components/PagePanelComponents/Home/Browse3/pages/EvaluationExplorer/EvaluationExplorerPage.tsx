import React, { useState, useEffect } from 'react';
import { GridRowsProp, GridRowModesModel, GridRowModes, GridRowId } from '@mui/x-data-grid-pro';
import { v4 as uuidv4 } from 'uuid';
import { SimplePageLayoutWithHeader } from '../common/SimplePageLayout';
import { ConfigurationBar } from './ConfigurationBar';
import { EvaluationDataGrid } from './components';
import { EvaluationExplorerPageProps, EvaluationRow } from './types';
import { calculateRowDigest, deepCloneRow, createEmptyRow } from './utils';
import SettingsIcon from '@mui/icons-material/Settings';
import IconButton from '@mui/material/IconButton';

export const EvaluationExplorerPage = (props: EvaluationExplorerPageProps) => {
  const [configDrawerOpen, setConfigDrawerOpen] = useState(false);

  const handleOpenConfigDrawer = () => setConfigDrawerOpen(true);
  const handleCloseConfigDrawer = () => setConfigDrawerOpen(false);

  return (
    <SimplePageLayoutWithHeader
      title="EvaluationExplorer"
      hideTabsIfSingle
      headerContent={null}
      tabs={[
        {
          label: 'main',
          content: <EvaluationExplorerPageInner {...props} configDrawerOpen={configDrawerOpen} onOpenConfigDrawer={handleOpenConfigDrawer} onCloseConfigDrawer={handleCloseConfigDrawer} />
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
  output: {},
  scores: {}
});

export const EvaluationExplorerPageInner: React.FC<EvaluationExplorerPageProps & {
  configDrawerOpen: boolean;
  onOpenConfigDrawer: () => void;
  onCloseConfigDrawer: () => void;
}> = ({ entity, project, configDrawerOpen, onOpenConfigDrawer, onCloseConfigDrawer }) => {
  const [selectedDatasetId, setSelectedDatasetId] = useState<string>('dataset-1');
  const [isDatasetEdited, setIsDatasetEdited] = useState(false);
  const [selectedModelIds, setSelectedModelIds] = useState<string[]>([]);
  
  const initialRow = createInitialRow();
  const [originalRows, setOriginalRows] = useState<GridRowsProp>([initialRow]);
  const [rows, setRows] = useState<GridRowsProp>([initialRow]);
  const [datasetColumns, setDatasetColumns] = useState<string[]>(DEFAULT_DATASET_COLUMNS);
  const [rowModesModel, setRowModesModel] = useState<GridRowModesModel>({});

  useEffect(() => {
    const hasBeenEdited = JSON.stringify(rows) !== JSON.stringify(originalRows);
    setIsDatasetEdited(hasBeenEdited);
  }, [rows, originalRows]);

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
  }, [rows.length]);

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
      setSelectedDatasetId('new-dataset');
      setRows([]);
      setOriginalRows([]);
      setIsDatasetEdited(false);
      setDatasetColumns(DEFAULT_DATASET_COLUMNS);
    } else {
      setSelectedDatasetId(datasetId);
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
    
    setRows(prevRows => prevRows.map(row => {
      const newOutput = { ...row.output };
      
      modelIds.forEach(modelId => {
        if (!newOutput[modelId]) {
          newOutput[modelId] = null;
        }
      });
      
      Object.keys(newOutput).forEach(modelId => {
        if (!modelIds.includes(modelId)) {
          delete newOutput[modelId];
        }
      });
      
      return { ...row, output: newOutput };
    }));
  };

  const handleRunModel = (rowId: string, modelId: string) => {
    console.log(`Running model ${modelId} for row ${rowId}`);
    
    setTimeout(() => {
      setRows(prevRows => prevRows.map(row => {
        if (row.id === rowId) {
          return {
            ...row,
            output: {
              ...row.output,
              [modelId]: [{ result: `Generated output for ${modelId}` }]
            }
          };
        }
        return row;
      }));
    }, 1000);
  };

  const availableModels = [
    { id: 'gpt-4', name: 'GPT-4', description: 'OpenAI GPT-4' },
    { id: 'claude-2', name: 'Claude 2', description: 'Anthropic Claude 2' },
    { id: 'llama-2', name: 'Llama 2', description: 'Meta Llama 2' },
  ];

  return (
    <Container>
      <DataContainer>
        <EvaluationDataGrid 
          rows={rows}
          datasetColumns={datasetColumns}
          selectedModelIds={selectedModelIds}
          models={availableModels}
          rowModesModel={rowModesModel}
          onRowsChange={setRows}
          onRowModesModelChange={setRowModesModel}
          onAddRow={handleAddRow}
          onAddColumn={handleAddColumn}
          onDeleteColumn={handleDeleteColumn}
          onDeleteRow={handleDeleteRow}
          onDuplicateRow={handleDuplicateRow}
          onRunModel={handleRunModel}
          onOpenConfig={onOpenConfigDrawer}
        />
      </DataContainer>
      <ConfigurationBar
        selectedDatasetId={selectedDatasetId}
        isDatasetEdited={isDatasetEdited}
        onDatasetChange={handleDatasetChange}
        selectedModelIds={selectedModelIds}
        onModelsChange={handleModelsChange}
        availableModels={availableModels}
        forceOpen={configDrawerOpen}
        onForceClose={onCloseConfigDrawer}
      />
    </Container>
  );
};

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
    position: 'relative',
    overflow: 'hidden'
  }}>
    {children}
  </div>
);