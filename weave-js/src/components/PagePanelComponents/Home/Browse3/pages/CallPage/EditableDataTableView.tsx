import {Box} from '@mui/material';
import {
  GridColDef,
  GridPaginationModel,
  GridRenderCellParams,
} from '@mui/x-data-grid-pro';
import {Button} from '@wandb/weave/components/Button';
import {min} from 'lodash';
import React, {FC, useCallback, useMemo, useState} from 'react';
import {v4 as uuidv4} from 'uuid';

import {isWeaveObjectRef, parseRefMaybe} from '../../../../../../react';
import {flattenObjectPreservingWeaveTypes} from '../../../Browse2/browse2Util';
import {StyledDataGrid} from '../../StyledDataGrid';
import {useDatasetEditContext} from '../DatasetEditContext'; // Update the import
import {useWFHooks} from '../wfReactInterface/context';
import {SortBy} from '../wfReactInterface/traceServerClientTypes';
import CustomCellRenderer from './CustomCellRenderer';
import EditableCellRenderer from './EditableCellRenderer'; // Import the editable cell renderer

type DatasetObjectVal = {
  _type: 'Dataset';
  name: string | null;
  description: string | null;
  rows: string;
  _class_name: 'Dataset';
  _bases: ['Object', 'BaseModel'];
};

interface EditableDataTableViewProps {
  datasetObjectId: string;
  datasetObject: DatasetObjectVal;
  fullHeight?: boolean;
}

// Update the ControlCell component to handle both delete and restore
const ControlCell: FC<{
  params: GridRenderCellParams;
  deleteRow: (absoluteIndex: number) => void;
  restoreRow: (absoluteIndex: number) => void;
  deleteAddedRow: (rowId: string) => void;
  isDeleted: boolean;
  isNew: boolean;
}> = ({params, deleteRow, restoreRow, deleteAddedRow, isDeleted, isNew}) => {
  return (
    <Box
      sx={{
        display: 'flex',
        paddingTop: '12px',
        alignItems: 'top',
        justifyContent: 'center',
        height: '100%',
        width: '100%',
      }}>
      <Button
        onClick={() => {
          if (isNew) {
            deleteAddedRow(params.row.id);
          } else if (isDeleted) {
            restoreRow(params.row._index);
          } else {
            deleteRow(params.row._index);
          }
        }}
        tooltip={isNew ? 'Remove' : isDeleted ? 'Restore' : 'Delete'}
        icon={isNew ? 'close' : isDeleted ? 'undo' : 'delete'}
        size="small"
        variant="secondary"
      />
    </Box>
  );
};

// Custom header component for the controls column
const ControlsColumnHeader: FC<{onAddRow: () => void}> = ({onAddRow}) => {
  return (
    <Box
      sx={{
        margin: '4px',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        height: '100%',
      }}>
      <Button
        icon="add-new"
        onClick={onAddRow}
        variant="ghost"
        size="small"
        tooltip="Add row">
        Add row
      </Button>
    </Box>
  );
};

export const EditableDataTableView: FC<EditableDataTableViewProps> = props => {
  const {useTableRowsQuery, useTableQueryStats} = useWFHooks();
  const [sortBy] = useState<SortBy[]>([]);
  const {
    editedCellsMap,
    processRowUpdate,
    deletedRows,
    setDeletedRows,
    setAddedRows,
    addedRows,
  } = useDatasetEditContext(); // Keep setRowIndices and rowIndices

  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize: 10,
  });

  const [initialFields, setInitialFields] = useState<string[]>([]);

  // Parse table ref
  const parsedRef = useMemo(
    () => parseRefMaybe(props.datasetObject.rows),
    [props.datasetObject.rows]
  );

  const lookupKey = useMemo(() => {
    if (
      parsedRef == null ||
      !isWeaveObjectRef(parsedRef) ||
      parsedRef.weaveKind !== 'table'
    ) {
      return null;
    }
    return {
      entity: parsedRef.entityName,
      project: parsedRef.projectName,
      digest: parsedRef.artifactVersion,
    };
  }, [parsedRef]);

  // Fetch row count
  const numRowsQuery = useTableQueryStats(
    lookupKey?.entity ?? '',
    lookupKey?.project ?? '',
    lookupKey?.digest ?? '',
    {skip: lookupKey == null}
  );

  const numAddedRows = useMemo(() => {
    return Array.from(addedRows.values()).length;
  }, [addedRows]);

  const numRowsToFetch = useMemo(() => {
    // Case that added rows do not appear on the page.
    if (numAddedRows <= paginationModel.page * paginationModel.pageSize) {
      return paginationModel.pageSize;
    }
    // Case that added rows take up the entire page.
    if (numAddedRows > (paginationModel.page + 1) * paginationModel.pageSize) {
      return 0;
    }
    // Case that added rows take up part of the page.
    return paginationModel.pageSize - (numAddedRows % paginationModel.pageSize);
  }, [paginationModel, numAddedRows]);

  const offset = useMemo(() => {
    return paginationModel.page * paginationModel.pageSize <= numAddedRows
      ? 0
      : paginationModel.page * paginationModel.pageSize - numAddedRows;
  }, [paginationModel, numAddedRows]);

  // Fetch rows
  const fetchQuery = useTableRowsQuery(
    lookupKey?.entity ?? '',
    lookupKey?.project ?? '',
    lookupKey?.digest ?? '',
    undefined,
    numRowsToFetch,
    offset,
    sortBy,
    {skip: lookupKey == null}
  );

  // Convert data to list of dictionaries and flatten nested objects
  const dataAsListOfDict = useMemo(() => {
    return (fetchQuery.result?.rows ?? []).map((row, index) => {
      let val = row;
      const absoluteIndex =
        index + paginationModel.pageSize * paginationModel.page;
      if (val == null) {
        return {
          _index: absoluteIndex,
        };
      } else if (typeof val === 'object' && !Array.isArray(val)) {
        if ('val' in val) {
          val = val.val; // Extract val field
        }
        return {
          ...flattenObjectPreservingWeaveTypes(val),
          _index: absoluteIndex,
        };
      }
      return {
        '': val,
        _index: absoluteIndex,
      };
    });
  }, [fetchQuery.result?.rows, paginationModel.page, paginationModel.pageSize]);

  // Add restore function
  const restoreRow = useCallback(
    (absoluteIndex: number) => {
      setDeletedRows(prev => prev.filter(index => index !== absoluteIndex));
    },
    [setDeletedRows]
  );

  // Update the rows memo to not filter out deleted rows
  const rows = useMemo(() => {
    if (!fetchQuery.loading && fetchQuery.result?.rows) {
      return dataAsListOfDict.map((row, i) => {
        const digest = fetchQuery.result!.rows[i].digest;
        const editedRow = editedCellsMap.get(digest);
        const baseRow = editedRow ? {...row, ...editedRow} : row;
        return {
          id: digest,
          ...baseRow,
        };
      });
    }
    return [];
  }, [fetchQuery.loading, fetchQuery.result, dataAsListOfDict, editedCellsMap]);

  // Function to delete a row by absolute index
  const deleteRow = useCallback(
    (absoluteIndex: number) => {
      const rowKey = `new-${absoluteIndex}`;
      if (addedRows.has(rowKey)) {
        setAddedRows(prev => {
          const updatedMap = new Map(prev);
          updatedMap.delete(rowKey);
          return updatedMap;
        });
      } else {
        setDeletedRows(prev => [...prev, absoluteIndex]);
      }
    },
    [setDeletedRows, setAddedRows, addedRows]
  );

  const deleteAddedRow = useCallback(
    (rowId: string) => {
      setAddedRows(prev => {
        const updatedMap = new Map(prev);
        updatedMap.delete(rowId);
        return updatedMap;
      });
    },
    [setAddedRows]
  );

  const handleAddRowsClick = useCallback(() => {
    setAddedRows(prev => {
      const updatedMap = new Map(prev);
      const newId = `new-${uuidv4()}`;
      // Create new row with empty values for all initial fields
      const newRow = {
        id: newId,
        ...Object.fromEntries(initialFields.map(field => [field, ''])),
      };
      updatedMap.set(newId, newRow);
      return updatedMap;
    });
  }, [setAddedRows, initialFields]);

  // Handle pagination model change
  const handlePaginationModelChange = useCallback(
    (newModel: GridPaginationModel) => {
      setPaginationModel(newModel);
    },
    []
  );

  // Combine existing rows with new rows within pagination limits
  const combinedRows = useMemo(() => {
    // Case that added rows do not appear on the page.
    if (numAddedRows <= paginationModel.page * paginationModel.pageSize) {
      return rows;
    }
    // Case that added rows take up part of the page.
    const startIndex = paginationModel.page * paginationModel.pageSize;
    const endIndex = startIndex + paginationModel.pageSize;
    const displayedAddedRows = Array.from(addedRows.values())
      .slice(startIndex, endIndex)
      .map(row => ({
        ...row,
        id: row.id,
      }));
    console.log('displayedAddedRows', displayedAddedRows);
    return [...displayedAddedRows, ...rows];
  }, [
    rows,
    addedRows,
    numAddedRows,
    paginationModel.pageSize,
    paginationModel.page,
  ]);

  // Update columns to handle deleted rows
  const columns = useMemo(() => {
    const allFields = combinedRows.reduce((acc, row) => {
      Object.keys(row).forEach(key => acc.add(key));
      return acc;
    }, new Set<string>());

    // Save initial fields if not already set
    if (initialFields.length === 0 && allFields.size > 0) {
      const fields = Array.from(allFields).filter(
        field => !['id', '_index', 'controls'].includes(field as string)
      );
      setInitialFields(fields as string[]);
    }

    const allFieldsObj = Object.fromEntries(
      Array.from(allFields).map(field => [field, null])
    );
    return [
      {
        field: 'controls',
        headerName: '',
        width: 110,
        sortable: false,
        filterable: false,
        editable: false,
        renderHeader: () => (
          <ControlsColumnHeader onAddRow={handleAddRowsClick} />
        ), // Use custom header
        renderCell: (params: GridRenderCellParams) => {
          const isDeleted = deletedRows.includes(params.row._index);
          const isNew = params.row.id.startsWith('new-');
          return (
            <ControlCell
              params={params}
              deleteRow={deleteRow}
              deleteAddedRow={deleteAddedRow}
              restoreRow={restoreRow}
              isDeleted={isDeleted}
              isNew={isNew}
            />
          );
        },
      },
      ...Object.keys(allFieldsObj)
        .map(field => {
          if (field === 'id' || field === '_index') {
            return null;
          }
          return {
            field,
            headerName: field,
            flex: 1,
            editable: true,
            sortable: false,
            filterable: false,
            renderCell: (params: GridRenderCellParams) => {
              const rowKey = `${params.row.id}`;
              const editedRow = editedCellsMap.get(rowKey);
              const isDeleted = deletedRows.includes(params.row._index);
              const isEdited = editedRow && editedRow[field] !== undefined;
              const isNew = rowKey.startsWith('new-');
              console.log('isNew', isNew, rowKey);

              return (
                <CustomCellRenderer
                  {...params}
                  isEdited={isEdited}
                  isDeleted={isDeleted}
                  isNew={isNew}
                />
              );
            },
            renderEditCell: EditableCellRenderer,
          };
        })
        .filter(Boolean),
    ];
  }, [
    combinedRows,
    editedCellsMap,
    deleteRow,
    restoreRow,
    deletedRows,
    deleteAddedRow,
    handleAddRowsClick,
    initialFields,
  ]);

  return (
    <div
      style={{
        height: '100%',
        overflow: 'hidden',
      }}>
      <StyledDataGrid
        disableColumnMenu={true}
        density="standard"
        rows={combinedRows}
        columns={columns as GridColDef[]}
        editMode="cell"
        pagination={true}
        paginationMode="server"
        paginationModel={paginationModel}
        onPaginationModelChange={handlePaginationModelChange}
        rowCount={(numRowsQuery.result?.count ?? 0) + numAddedRows}
        pageSizeOptions={[5, 10, 20, 50, 100]}
        disableMultipleColumnsSorting
        loading={fetchQuery.loading}
        disableRowSelectionOnClick
        keepBorders={false}
        sx={{
          border: 'none',
          '& .MuiDataGrid-cell': {
            padding: '0',
          },
        }}
        processRowUpdate={processRowUpdate}
      />
    </div>
  );
};
