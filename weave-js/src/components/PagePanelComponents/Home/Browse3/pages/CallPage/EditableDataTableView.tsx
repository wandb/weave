import {Box} from '@mui/material';
import {
  GridColDef,
  GridPaginationModel,
  GridRenderCellParams,
} from '@mui/x-data-grid-pro';
import {Button} from '@wandb/weave/components/Button';
import React, {FC, useCallback, useEffect, useMemo, useState} from 'react';

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
  isDeleted: boolean;
}> = ({params, deleteRow, restoreRow, isDeleted}) => {
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
          if (isDeleted) {
            restoreRow(params.row._index);
          } else {
            deleteRow(params.row._index);
          }
        }}
        tooltip={isDeleted ? 'Restore' : 'Delete'}
        icon={isDeleted ? 'undo' : 'delete'}
        size="small"
        variant="secondary"
      />
    </Box>
  );
};

export const EditableDataTableView: FC<EditableDataTableViewProps> = props => {
  const {useTableRowsQuery, useTableQueryStats} = useWFHooks();
  const [sortBy] = useState<SortBy[]>([]);
  const {editedCellsMap, processRowUpdate, deletedRows, setDeletedRows} =
    useDatasetEditContext(); // Keep setRowIndices and rowIndices

  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize: 5,
  });

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

  // Fetch rows
  const fetchQuery = useTableRowsQuery(
    lookupKey?.entity ?? '',
    lookupKey?.project ?? '',
    lookupKey?.digest ?? '',
    undefined,
    paginationModel.pageSize,
    paginationModel.page * paginationModel.pageSize,
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
      setDeletedRows(prev => [...prev, absoluteIndex]);
    },
    [setDeletedRows]
  );

  // Update columns to handle deleted rows
  const columns = useMemo(() => {
    const firstRow = rows[0] ?? {};
    return [
      {
        field: 'controls',
        headerName: '',
        width: 40,
        sortable: false,
        filterable: false,
        editable: false,
        renderCell: (params: GridRenderCellParams) => {
          const isDeleted = deletedRows.includes(params.row._index);
          return (
            <ControlCell
              params={params}
              deleteRow={deleteRow}
              restoreRow={restoreRow}
              isDeleted={isDeleted}
            />
          );
        },
      },
      ...Object.keys(firstRow)
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

              return (
                <CustomCellRenderer
                  {...params}
                  isEdited={isEdited}
                  isDeleted={isDeleted}
                />
              );
            },
            renderEditCell: EditableCellRenderer,
          };
        })
        .filter(Boolean),
    ];
  }, [rows, editedCellsMap, deleteRow, restoreRow, deletedRows]);

  // Handle pagination model change
  const handlePaginationModelChange = useCallback(
    (newModel: GridPaginationModel) => {
      setPaginationModel(newModel);
    },
    []
  );

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        width: '100%',
        height: props.fullHeight ? '100%' : 'inherit',
      }}>
      <StyledDataGrid
        disableColumnMenu={true}
        density="comfortable"
        rows={rows}
        columns={columns as GridColDef[]}
        editMode="cell"
        pagination={true}
        paginationMode="server"
        paginationModel={paginationModel}
        onPaginationModelChange={handlePaginationModelChange}
        rowCount={numRowsQuery.result?.count ?? 0}
        pageSizeOptions={[5, 10, 20, 50, 100]}
        disableMultipleColumnsSorting
        loading={fetchQuery.loading}
        disableRowSelectionOnClick
        keepBorders={false}
        getRowHeight={params => {
          const rowIndex = rows.findIndex(row => row.id === params.id);
          const isDeleted = deletedRows.includes(rowIndex);
          return isDeleted ? 48 : 120; // Adjust height for deleted rows
        }}
        sx={{
          border: 'none',
          '& .MuiDataGrid-cell': {
            padding: '0',
            whiteSpace: 'normal',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          },
        }}
        processRowUpdate={processRowUpdate}
      />
    </div>
  );
};
