import { GridColDef, GridColumnGroupingModel, GridRowsProp, GridRowModesModel, GridRowModel, GridEventListener, GridRowId, GridRowModes, GridActionsCellItem, GridRowParams, GridToolbarContainer, GridAddIcon, GridCellParams, GridRenderEditCellParams, GridPreProcessEditCellProps } from '@mui/x-data-grid-pro';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React from 'react';
import IconButton from '@mui/material/IconButton';
import Button from '@mui/material/Button';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import TextField from '@mui/material/TextField';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import { v4 as uuidv4 } from 'uuid';

import { StyledDataGrid } from '../../StyledDataGrid';
import {SimplePageLayoutWithHeader} from '../common/SimplePageLayout';

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

const dummyRows:GridRowsProp = [
    {
        id: "1",
        dataset: {
            rowDigest: "1234567890",
            columnA: "1234567890",
            columnB: "1234567890",
        },
        "output": {
            "modelA": [
                {"key": "val"}
            ],
            "modelB": [
                {"key": "val"}
            ]
        },
        "scores": {
            "scorerA": {
                "modelA": {
                    "score": "1",
                    "reason": "A"
                },
                "modelB": {
                    "score": "1",
                    "reason": "A"
                }
            }
        }
    }
]

const dummyColumns:GridColDef<typeof dummyRows[0]>[] = [
    {
        field: "dataset.rowDigest",
        headerName: "Row Digest",
        width: 100,
        valueGetter: (value, row) => {
            return row.dataset.rowDigest;
        }
    },
    {
        field: "dataset.columnA",
        headerName: "Column A",
        width: 100,
    },
    {
        field: "dataset.columnB",
        headerName: "Column B",
        width: 100,
    },
    {
        field: "output.modelA",
        headerName: "Model A",
        width: 100,
    },
    {
        field: "output.modelB",
        headerName: "Model B",
        width: 100,
    },
]

const dummyColumnGroups: GridColumnGroupingModel = [
    {
        groupId: "Datset",
        children: [
            {
                field: "dataset.rowDigest",
                headerName: "Row Digest",
                
            },
            {
                field: "dataset.columnA",
                headerName: "Column A",
                
            },  
            {
                field: "dataset.columnB",
                headerName: "Column B",
                
            }
        ]
    },
    {
        groupId: "Output",
        children: [
            {
                field: "output.modelA",
                headerName: "Model A",
                
            },
            {
                field: "output.modelB",
                headerName: "Model B",
                
            }
        ]
    },
]

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
const EditToolbar: React.FC<{
  onAddRow: () => void;
  onAddColumn: () => void;
}> = ({ onAddRow, onAddColumn }) => {
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
  const [contextMenu, setContextMenu] = React.useState<{
    mouseX: number;
    mouseY: number;
    rowId: GridRowId;
  } | null>(null);

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

  const handleEditClick = (id: GridRowId) => () => {
    setRowModesModel({ ...rowModesModel, [id]: { mode: GridRowModes.Edit } });
  };

  const handleSaveClick = (id: GridRowId) => () => {
    setRowModesModel({ ...rowModesModel, [id]: { mode: GridRowModes.View } });
  };

  const handleDeleteRow = (id: GridRowId) => () => {
    setRows(rows.filter((row) => row.id !== id));
  };

  const handleDuplicateRow = (id: GridRowId) => () => {
    const rowToDuplicate = rows.find(row => row.id === id);
    if (rowToDuplicate) {
      const newRow = {
        ...rowToDuplicate,
        id: uuidv4(),
        dataset: { ...rowToDuplicate.dataset }
      };
      setRows([...rows, newRow]);
    }
  };

  const handleCancelClick = (id: GridRowId) => () => {
    setRowModesModel({
      ...rowModesModel,
      [id]: { mode: GridRowModes.View, ignoreModifications: true },
    });
  };

  const processRowUpdate = (newRow: GridRowModel) => {
    const updatedRow = { 
      ...newRow, 
      dataset: {
        ...newRow.dataset,
        rowDigest: calculateRowDigest(newRow)
      }
    };
    setRows(rows.map((row) => (row.id === newRow.id ? updatedRow : row)));
    return updatedRow;
  };

  const handleAddRow = () => {
    const newId = uuidv4();
    const newDataset: any = {};
    datasetColumns.forEach(col => {
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
    
    setRows((oldRows) => [...oldRows, newRow]);
    setRowModesModel((oldModel) => ({
      ...oldModel,
      [newId]: { mode: GridRowModes.Edit },
    }));
  };

  const handleAddColumn = () => {
    const columnName = `column${datasetColumns.length + 1}`;
    setDatasetColumns([...datasetColumns, columnName]);
    
    // Add the new column to all existing rows
    setRows(rows.map(row => ({
      ...row,
      dataset: {
        ...row.dataset,
        [columnName]: ''
      }
    })));
  };

  const handleDeleteColumn = (columnName: string) => {
    setDatasetColumns(datasetColumns.filter(col => col !== columnName));
    
    // Remove the column from all rows
    setRows(rows.map(row => {
      const newDataset = { ...row.dataset };
      delete newDataset[columnName];
      return {
        ...row,
        dataset: newDataset
      };
    }));
  };

  const handleContextMenu = (event: React.MouseEvent, rowId: GridRowId) => {
    event.preventDefault();
    setContextMenu(
      contextMenu === null
        ? {
            mouseX: event.clientX + 2,
            mouseY: event.clientY - 6,
            rowId,
          }
        : null
    );
  };

  const handleCloseContextMenu = () => {
    setContextMenu(null);
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
  }, [datasetColumns]);

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
          experimentalFeatures={{ newEditingApi: true }}
          onRowContextMenu={(params, event) => handleContextMenu(event as React.MouseEvent, params.id)}
          columnVisibilityModel={{
            'dataset.rowDigest': false, // Hide the row digest column
          }}
        />
        
        <Menu
          open={contextMenu !== null}
          onClose={handleCloseContextMenu}
          anchorReference="anchorPosition"
          anchorPosition={
            contextMenu !== null
              ? { top: contextMenu.mouseY, left: contextMenu.mouseX }
              : undefined
          }
        >
          <MenuItem onClick={() => {
            if (contextMenu) {
              handleDuplicateRow(contextMenu.rowId)();
              handleCloseContextMenu();
            }
          }}>
            <ListItemIcon>
              <ContentCopyIcon fontSize="small" />
            </ListItemIcon>
            <ListItemText>Duplicate Row</ListItemText>
          </MenuItem>
          <MenuItem onClick={() => {
            if (contextMenu) {
              handleDeleteRow(contextMenu.rowId)();
              handleCloseContextMenu();
            }
          }}>
            <ListItemIcon>
              <DeleteIcon fontSize="small" />
            </ListItemIcon>
            <ListItemText>Delete Row</ListItemText>
          </MenuItem>
        </Menu>
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