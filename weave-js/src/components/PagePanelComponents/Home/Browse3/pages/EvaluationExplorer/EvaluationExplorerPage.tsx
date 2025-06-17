import { 
  GridColDef, 
  GridColumnGroupingModel, 
  GridRowsProp, 
  GridRowModesModel, 
  GridRowModel, 
  GridEventListener, 
  GridRowId, 
  GridRowModes, 
  GridActionsCellItem, 
  GridRowParams, 
  GridToolbarContainer
} from '@mui/x-data-grid-pro';
import React from 'react';
import IconButton from '@mui/material/IconButton';
import Button from '@mui/material/Button';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';

import { v4 as uuidv4 } from 'uuid';

import { StyledDataGrid } from '../../StyledDataGrid';
import {SimplePageLayoutWithHeader} from '../common/SimplePageLayout';
import { ConfigurationBar } from './ConfigurationBar';

export type EvaluationExplorerPageProps = {
  entity: string;
  project: string;
};

export const EvaluationExplorerPage = (props: EvaluationExplorerPageProps) => {
  return (
    <SimplePageLayoutWithHeader
      title="EvaluationExplorer"
      hideTabsIfSingle
      headerContent={null}
      tabs={[
        {
          label: 'main',
          content: (
              <EvaluationExplorerPageInner {...props} />

          ),
        },
      ]}
      headerExtra={null}
    />
  );
};



// Helper function to calculate row digest
const calculateRowDigest = (row: any): string => {
  // Create a simple hash from dataset values
  const datasetValues = Object.entries(row.dataset || {})
    .filter(([key]) => key !== 'rowDigest')
    .map(([key, value]) => `${key}:${value}`)
    .join('|');
  
  // Simple hash function for browser
  let hash = 0;
  for (let i = 0; i < datasetValues.length; i++) {
    const char = datasetValues.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32bit integer
  }
  return Math.abs(hash).toString(16).padStart(8, '0');
};

// Custom toolbar component
const EditToolbar = (props: any) => {
  const { onAddRow, onAddColumn } = props;
  return (
    <GridToolbarContainer>
      <Button color="primary" startIcon={<AddIcon />} onClick={onAddRow}>
        Add Row
      </Button>
      <Button color="primary" startIcon={<AddIcon />} onClick={onAddColumn}>
        Add Column
      </Button>
    </GridToolbarContainer>
  );
};

export const EvaluationExplorerPageInner: React.FC<
  EvaluationExplorerPageProps
> = ({entity, project}) => {
  const [selectedDatasetId, setSelectedDatasetId] = React.useState<string>('dataset-1');
  const [isDatasetEdited, setIsDatasetEdited] = React.useState(false);
  const [selectedModelIds, setSelectedModelIds] = React.useState<string[]>([]);
  const [originalRows, setOriginalRows] = React.useState<GridRowsProp>([
    {
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
    }
  ]);
  const [rows, setRows] = React.useState<GridRowsProp>([
    {
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
    }
  ]);

  const [datasetColumns, setDatasetColumns] = React.useState<string[]>(['columnA', 'columnB']);
  const [rowModesModel, setRowModesModel] = React.useState<GridRowModesModel>({});

  // Check if dataset has been edited
  React.useEffect(() => {
    const hasBeenEdited = JSON.stringify(rows) !== JSON.stringify(originalRows);
    setIsDatasetEdited(hasBeenEdited);
  }, [rows, originalRows]);

  // Update row digests whenever rows change
  React.useEffect(() => {
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

  const handleRowEditStop: GridEventListener<'rowEditStop'> = (params, event) => {
    if (params.reason === 'rowFocusOut') {
      event.defaultMuiPrevented = true;
    }
  };



  const handleDeleteRow = (id: GridRowId) => () => {
    setRows(prevRows => prevRows.filter((row) => row.id !== id));
  };

  const handleDuplicateRow = (id: GridRowId) => () => {
    const rowToDuplicate = rows.find(row => row.id === id);
    if (rowToDuplicate) {
      const newRow = {
        ...rowToDuplicate,
        id: uuidv4(),
        dataset: { ...rowToDuplicate.dataset },
        output: { 
          ...rowToDuplicate.output,
          modelA: Array.isArray(rowToDuplicate.output?.modelA) ? [...rowToDuplicate.output.modelA] : [],
          modelB: Array.isArray(rowToDuplicate.output?.modelB) ? [...rowToDuplicate.output.modelB] : []
        },
        scores: JSON.parse(JSON.stringify(rowToDuplicate.scores || {}))
      };
      setRows(prevRows => [...prevRows, newRow]);
    }
  };



  const processRowUpdate = (newRow: GridRowModel) => {
    const updatedRow = { 
      ...newRow, 
      dataset: {
        ...newRow.dataset,
        rowDigest: calculateRowDigest(newRow)
      }
    };
    setRows(prevRows => prevRows.map((row) => (row.id === newRow.id ? updatedRow : row)));
    return updatedRow;
  };

  const handleAddRow = () => {
    const newId = uuidv4();
    
    setDatasetColumns(currentColumns => {
      const newDataset: any = {};
      currentColumns.forEach(col => {
        newDataset[col] = '';
      });
      
      const newRow = {
        id: newId,
        dataset: newDataset,
        output: {
          modelA: [],
          modelB: []
        },
        scores: {}
      };
      
      setRows(prevRows => [...prevRows, newRow]);
      setRowModesModel(prevModel => ({
        ...prevModel,
        [newId]: { mode: GridRowModes.Edit },
      }));
      
      return currentColumns; // Return unchanged columns
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
      setDatasetColumns(['columnA', 'columnB']);
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

  // Generate columns dynamically
  const columns: GridColDef[] = React.useMemo(() => {
    const cols: GridColDef[] = [];

    // Hidden row digest column
    cols.push({
      field: 'dataset.rowDigest',
      headerName: 'Row Digest',
      width: 0,
      hideable: false,
      filterable: false,
      sortable: false,
      resizable: false,
      editable: false,
      valueGetter: (value, row) => row.dataset?.rowDigest || '',
    });

    // Dynamic dataset columns
    datasetColumns.forEach(colName => {
      cols.push({
        field: `dataset.${colName}`,
        headerName: colName.charAt(0).toUpperCase() + colName.slice(1),
        width: 150,
        editable: true,
        valueGetter: (value, row) => row.dataset?.[colName] || '',
        valueSetter: (params) => {
          if (!params.row || !params.row.dataset) {
            console.warn('Row or dataset is undefined in valueSetter', params);
            return params.row || {};
          }
          const newDataset = { ...params.row.dataset, [colName]: params.value };
          return { ...params.row, dataset: newDataset };
        },
        renderHeader: (params) => (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
            <span>{params.colDef.headerName}</span>
            <IconButton
              size="small"
              onClick={(e) => {
                e.stopPropagation();
                handleDeleteColumn(colName);
              }}
            >
              <DeleteIcon fontSize="small" />
            </IconButton>
          </div>
        ),
      });
    });

    // Output columns
    cols.push({
      field: 'output.modelA',
      headerName: 'Model A',
      width: 150,
      valueGetter: (value, row) => JSON.stringify(row.output?.modelA || []),
    });

    cols.push({
      field: 'output.modelB',
      headerName: 'Model B',
      width: 150,
      valueGetter: (value, row) => JSON.stringify(row.output?.modelB || []),
    });

    // Actions column
    cols.push({
      field: 'actions',
      type: 'actions',
      headerName: 'Actions',
      width: 100,
      cellClassName: 'actions',
      getActions: ({ id }) => {
        return [
          <GridActionsCellItem
            icon={<ContentCopyIcon />}
            label="Duplicate"
            onClick={handleDuplicateRow(id)}
            color="inherit"
          />,
          <GridActionsCellItem
            icon={<DeleteIcon />}
            label="Delete"
            onClick={handleDeleteRow(id)}
            color="inherit"
          />,
        ];
      },
    });

    return cols;
  }, [datasetColumns, rows, handleDuplicateRow, handleDeleteRow]);

  // Generate column groups
  const columnGroupingModel: GridColumnGroupingModel = React.useMemo(() => {
    const datasetFields = datasetColumns.map(col => ({ field: `dataset.${col}` }));
    
    return [
      {
        groupId: 'Dataset',
        children: datasetFields,
      },
      {
        groupId: 'Output',
        children: [
          { field: 'output.modelA' },
          { field: 'output.modelB' }
        ]
      },
    ];
  }, [datasetColumns]);

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'row',
      width: '100%',
      height: '100%'
    }}>
      <ConfigurationBar
        selectedDatasetId={selectedDatasetId}
        isDatasetEdited={isDatasetEdited}
        onDatasetChange={handleDatasetChange}
        selectedModelIds={selectedModelIds}
        onModelsChange={handleModelsChange}
      />
      <Column>
        <StyledDataGrid 
          rows={rows} 
          columns={columns}
          rowHeight={36}
          columnGroupingModel={columnGroupingModel}
          columnHeaderHeight={36}
          editMode="row"
          rowModesModel={rowModesModel}
          onRowModesModelChange={setRowModesModel}
          onRowEditStop={handleRowEditStop}
          processRowUpdate={processRowUpdate}
          onProcessRowUpdateError={(error) => console.error(error)}
          slots={{
            toolbar: EditToolbar,
          }}
          slotProps={{
            toolbar: { onAddRow: handleAddRow, onAddColumn: handleAddColumn },
          }}
          columnVisibilityModel={{
            'dataset.rowDigest': false, // Hide the row digest column
          }}
        />
      </Column>
    </div>
  );
};


const Column: React.FC = ({children}) => {
    return <div style={{
        display: 'flex',
        flexDirection: 'column',
        width: '100%',
        height: '100%'
    }}>{children}</div>
}