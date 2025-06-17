import React, { useMemo, useCallback } from 'react';
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
} from '@mui/x-data-grid-pro';
import IconButton from '@mui/material/IconButton';
import DeleteIcon from '@mui/icons-material/Delete';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import { StyledDataGrid } from '../../../StyledDataGrid';
import { EditToolbar } from './EditToolbar';
import { calculateRowDigest } from '../utils';
import { EvaluationRow } from '../types';

interface EvaluationDataGridProps {
  rows: GridRowsProp;
  datasetColumns: string[];
  rowModesModel: GridRowModesModel;
  onRowsChange: (rows: GridRowsProp) => void;
  onRowModesModelChange: (model: GridRowModesModel) => void;
  onAddRow: () => void;
  onAddColumn: () => void;
  onDeleteColumn: (columnName: string) => void;
  onDeleteRow: (id: GridRowId) => void;
  onDuplicateRow: (id: GridRowId) => void;
}

export const EvaluationDataGrid: React.FC<EvaluationDataGridProps> = ({
  rows,
  datasetColumns,
  rowModesModel,
  onRowsChange,
  onRowModesModelChange,
  onAddRow,
  onAddColumn,
  onDeleteColumn,
  onDeleteRow,
  onDuplicateRow,
}) => {
  const handleRowEditStop: GridEventListener<'rowEditStop'> = useCallback((params, event) => {
    if (params.reason === 'rowFocusOut') {
      event.defaultMuiPrevented = true;
    }
  }, []);

  const processRowUpdate = useCallback((newRow: GridRowModel) => {
    const updatedRow = { 
      ...newRow, 
      dataset: {
        ...newRow.dataset,
        rowDigest: calculateRowDigest(newRow)
      }
    };
    const newRows = rows.map((row) => (row.id === newRow.id ? updatedRow : row));
    onRowsChange(newRows);
    return updatedRow;
  }, [rows, onRowsChange]);

  const handleDeleteRow = useCallback((id: GridRowId) => () => {
    onDeleteRow(id);
  }, [onDeleteRow]);

  const handleDuplicateRow = useCallback((id: GridRowId) => () => {
    onDuplicateRow(id);
  }, [onDuplicateRow]);

  // Generate columns dynamically
  const columns: GridColDef[] = useMemo(() => {
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
                onDeleteColumn(colName);
              }}
            >
              <DeleteIcon fontSize="small" />
            </IconButton>
          </div>
        ),
      });
    });

    // Output columns - TODO: Make dynamic based on selected models
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
  }, [datasetColumns, handleDuplicateRow, handleDeleteRow, onDeleteColumn]);

  // Generate column groups
  const columnGroupingModel: GridColumnGroupingModel = useMemo(() => {
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
    <StyledDataGrid 
      rows={rows} 
      columns={columns}
      rowHeight={36}
      columnGroupingModel={columnGroupingModel}
      columnHeaderHeight={36}
      editMode="row"
      rowModesModel={rowModesModel}
      onRowModesModelChange={onRowModesModelChange}
      onRowEditStop={handleRowEditStop}
      processRowUpdate={processRowUpdate}
      onProcessRowUpdateError={(error) => console.error(error)}
      slots={{
        toolbar: EditToolbar as any,
      }}
      slotProps={{
        toolbar: { onAddRow, onAddColumn },
      }}
      columnVisibilityModel={{
        'dataset.rowDigest': false, // Hide the row digest column
      }}
    />
  );
}; 