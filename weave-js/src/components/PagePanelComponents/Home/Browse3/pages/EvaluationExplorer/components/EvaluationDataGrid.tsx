import React, { useMemo, useCallback, useState } from 'react';
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
  GridRenderCellParams,
} from '@mui/x-data-grid-pro';
import IconButton from '@mui/material/IconButton';
import DeleteIcon from '@mui/icons-material/Delete';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Box from '@mui/material/Box';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import { StyledDataGrid } from '../../../StyledDataGrid';
import { EditToolbar } from './EditToolbar';
import { calculateRowDigest } from '../utils';
import { EvaluationRow, Model } from '../types';

export interface EvaluationDataGridProps {
  rows: GridRowsProp;
  datasetColumns: string[];
  selectedModelIds: string[];
  models: Model[];
  rowModesModel: GridRowModesModel;
  onRowsChange: (rows: GridRowsProp) => void;
  onRowModesModelChange: React.Dispatch<React.SetStateAction<GridRowModesModel>>;
  onAddRow: () => void;
  onAddColumn: () => void;
  onDeleteColumn: (columnName: string) => void;
  onDeleteRow: (id: GridRowId) => void;
  onDuplicateRow: (id: GridRowId) => void;
  onRunModel: (rowId: string, modelId: string) => void;
  onOpenConfig?: () => void;
}

export const EvaluationDataGrid: React.FC<EvaluationDataGridProps> = ({
  rows,
  datasetColumns,
  selectedModelIds,
  models,
  rowModesModel,
  onRowsChange,
  onRowModesModelChange,
  onAddRow,
  onAddColumn,
  onDeleteColumn,
  onDeleteRow,
  onDuplicateRow,
  onRunModel,
  onOpenConfig
}) => {
  const [menuAnchorEl, setMenuAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedRowId, setSelectedRowId] = useState<string | null>(null);

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, rowId: string) => {
    setMenuAnchorEl(event.currentTarget);
    setSelectedRowId(rowId);
  };

  const handleMenuClose = () => {
    setMenuAnchorEl(null);
    setSelectedRowId(null);
  };

  const handleDuplicate = () => {
    if (selectedRowId) {
      onDuplicateRow(selectedRowId);
    }
    handleMenuClose();
  };

  const handleDelete = () => {
    if (selectedRowId) {
      onDeleteRow(selectedRowId);
    }
    handleMenuClose();
  };

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

    // Actions column (now first)
    cols.push({
      field: 'actions',
      type: 'actions',
      headerName: '',
      width: 40,
      cellClassName: 'actions',
      getActions: ({ id }) => {
        return [
          <GridActionsCellItem
            icon={<MoreVertIcon fontSize="small" />}
            label="More"
            onClick={(e) => handleMenuOpen(e, id as string)}
            sx={{ 
              color: 'text.secondary',
              '&:hover': { color: 'primary.main' }
            }}
          />,
        ];
      },
    });

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
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'space-between', 
            width: '100%',
            paddingRight: 8
          }}>
            <span>{params.colDef.headerName}</span>
            <IconButton
              size="small"
              onClick={(e) => {
                e.stopPropagation();
                onDeleteColumn(colName);
              }}
              sx={{
                padding: '2px',
                color: 'text.secondary',
                opacity: 0.5,
                transition: 'opacity 0.2s',
                '&:hover': {
                  opacity: 1,
                  backgroundColor: 'rgba(0, 0, 0, 0.04)'
                }
              }}
            >
              <DeleteIcon sx={{ fontSize: 16 }} />
            </IconButton>
          </div>
        ),
      });
    });

    // Dynamic model output columns
    selectedModelIds.forEach(modelId => {
      const model = models.find(m => m.id === modelId);
      const modelName = model?.name || modelId;
      
      cols.push({
        field: `output.${modelId}`,
        headerName: modelName,
        width: 200,
        valueGetter: (value, row) => row.output?.[modelId],
        renderCell: (params: GridRenderCellParams) => {
          const output = params.value;
          
          if (output && output.length > 0) {
            // Model has output
            return (
              <Box sx={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: 0.5,
                width: '100%',
                height: '100%',
                px: 1
              }}>
                <Chip 
                  label={`Output: ${JSON.stringify(output).substring(0, 30)}...`}
                  size="small"
                  variant="outlined"
                  sx={{ 
                    fontSize: '0.75rem',
                    height: 24,
                    maxWidth: '100%'
                  }}
                />
              </Box>
            );
          } else {
            // No output - show run button
            return (
              <Box sx={{ 
                display: 'flex', 
                alignItems: 'center',
                justifyContent: 'center',
                width: '100%',
                height: '100%'
              }}>
                <Button
                  size="small"
                  startIcon={<PlayArrowIcon fontSize="small" />}
                  onClick={(e) => {
                    e.stopPropagation();
                    if (onRunModel) {
                      onRunModel(params.row.id as string, modelId);
                    }
                  }}
                  sx={{ 
                    fontSize: '0.75rem',
                    py: 0.25,
                    px: 1,
                    minWidth: 'auto',
                    textTransform: 'none'
                  }}
                >
                  Run
                </Button>
              </Box>
            );
          }
        },
      });
    });

    return cols;
  }, [datasetColumns, handleDuplicateRow, handleDeleteRow, onDeleteColumn, selectedModelIds, models, onRunModel]);

  // Generate column groups
  const columnGroupingModel: GridColumnGroupingModel = useMemo(() => {
    const datasetFields = datasetColumns.map(col => ({ field: `dataset.${col}` }));
    const outputFields = selectedModelIds.map(modelId => ({ field: `output.${modelId}` }));
    
    const groups: any[] = [
      {
        groupId: 'Dataset',
        children: datasetFields,
      },
    ];
    
    if (outputFields.length > 0) {
      groups.push({
        groupId: 'Output',
        children: outputFields
      });
    }
    
    return groups;
  }, [datasetColumns, selectedModelIds]);

  return (
    <>
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
          toolbar: { onAddRow, onAddColumn, onOpenConfig },
        }}
        columnVisibilityModel={{
          'dataset.rowDigest': false, // Hide the row digest column
        }}
      />
      <Menu
        anchorEl={menuAnchorEl}
        open={Boolean(menuAnchorEl)}
        onClose={handleMenuClose}
        onClick={handleMenuClose}
        PaperProps={{
          elevation: 0,
          sx: {
            overflow: 'visible',
            filter: 'drop-shadow(0px 2px 8px rgba(0,0,0,0.15))',
            mt: 1.5,
            '& .MuiAvatar-root': {
              width: 32,
              height: 32,
              ml: -0.5,
              mr: 1,
            },
            '&:before': {
              content: '""',
              display: 'block',
              position: 'absolute',
              top: 0,
              right: 14,
              width: 10,
              height: 10,
              bgcolor: 'background.paper',
              transform: 'translateY(-50%) rotate(45deg)',
              zIndex: 0,
            },
          },
        }}
        transformOrigin={{ horizontal: 'right', vertical: 'top' }}
        anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
      >
        <MenuItem onClick={handleDuplicate}>
          <ListItemIcon>
            <ContentCopyIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>Duplicate</ListItemText>
        </MenuItem>
        <MenuItem onClick={handleDelete}>
          <ListItemIcon>
            <DeleteIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>Delete</ListItemText>
        </MenuItem>
      </Menu>
    </>
  );
}; 