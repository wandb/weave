import {Box} from '@mui/material';
import {
  GridColDef,
  GridPaginationModel,
  GridRenderCellParams,
  GridRenderEditCellParams,
  GridRowModel,
  GridSortModel,
} from '@mui/x-data-grid-pro';
import {A} from '@wandb/weave/common/util/links';
import {Button} from '@wandb/weave/components/Button';
import {RowId} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/CallPage/DataTableView';
import {Tooltip} from '@wandb/weave/components/Tooltip';
import React, {
  FC,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import {useHistory} from 'react-router-dom';
import {v4 as uuidv4} from 'uuid';

import {isWeaveObjectRef, parseRef, parseRefMaybe} from '../../../../../react';
import {flattenObjectPreservingWeaveTypes} from '../../Browse2/browse2Util';
import {CellValue} from '../../Browse2/CellValue';
import {useWeaveflowCurrentRouteContext} from '../context';
import {WeaveCHTableSourceRefContext} from '../pages/CallPage/DataTableView';
import {TABLE_ID_EDGE_NAME} from '../pages/wfReactInterface/constants';
import {useWFHooks} from '../pages/wfReactInterface/context';
import {SortBy} from '../pages/wfReactInterface/traceServerClientTypes';
import {StyledDataGrid} from '../StyledDataGrid';
import {CellEditingRenderer, CellViewingRenderer} from './CellRenderers';
import {useDatasetEditContext} from './DatasetEditorContext';

const ADDED_ROW_ID_PREFIX = 'new-';

// Dataset object schema as it is stored in the database.
interface DatasetObjectVal {
  _type: 'Dataset';
  name: string | null;
  description: string | null;
  rows: string;
  _class_name: 'Dataset';
  _bases: ['Object', 'BaseModel'];
}

interface EditableDataTableViewProps {
  datasetObject: DatasetObjectVal;
  isEditing: boolean;
}

interface ControlCellProps {
  params: GridRenderCellParams;
  deleteRow: (absoluteIndex: number) => void;
  restoreRow: (absoluteIndex: number) => void;
  deleteAddedRow: (rowId: string) => void;
  isDeleted: boolean;
  isNew: boolean;
}

interface ControlsColumnHeaderProps {
  onAddRow: () => void;
}

const ControlCell: FC<ControlCellProps> = ({
  params,
  deleteRow,
  restoreRow,
  deleteAddedRow,
  isDeleted,
  isNew,
}) => (
  <Box
    sx={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      height: '100%',
      width: '100%',
      padding: '4px',
    }}>
    <Button
      onClick={() => {
        if (isNew) {
          deleteAddedRow(params.row.___weave?.id);
        } else if (isDeleted) {
          restoreRow(params.row.___weave?.index);
        } else {
          deleteRow(params.row.___weave?.index);
        }
      }}
      tooltip={isNew ? 'Remove' : isDeleted ? 'Restore' : 'Delete'}
      icon={isNew ? 'close' : isDeleted ? 'undo' : 'delete'}
      size="small"
      variant="secondary"
    />
  </Box>
);

const ControlsColumnHeader: FC<ControlsColumnHeaderProps> = ({onAddRow}) => (
  <Box
    sx={{
      margin: '2px',
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
      tooltip="Add row"
    />
  </Box>
);

export const EditableDatasetView: FC<EditableDataTableViewProps> = ({
  datasetObject,
  isEditing,
}) => {
  const {useTableRowsQuery, useTableQueryStats} = useWFHooks();
  const [sortBy, setSortBy] = useState<SortBy[]>([]);
  const [sortModel, setSortModel] = useState<GridSortModel>([]);

  const onSortModelChange = useCallback((model: GridSortModel) => {
    setSortBy(
      model.map(sort => ({
        field: sort.field,
        direction: sort.sort === 'asc' ? 'asc' : 'desc',
      }))
    );
    setSortModel(model);
  }, []);

  const {
    editedCellsMap,
    processRowUpdate,
    deletedRows,
    setDeletedRows,
    setAddedRows,
    addedRows,
  } = useDatasetEditContext();

  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize: 50,
  });

  // Reset sort model and pagination if we enter edit mode with sorting applied.
  useEffect(() => {
    if (isEditing && sortModel.length > 0) {
      setPaginationModel({page: 0, pageSize: 50});
      setSortModel([]);
      setSortBy([]);
    }
  }, [isEditing, sortModel]);

  const sharedRef = useContext(WeaveCHTableSourceRefContext);

  const history = useHistory();
  const router = useWeaveflowCurrentRouteContext();
  const onClick = useCallback(
    val => {
      const ref = parseRef(sharedRef!);
      if (isWeaveObjectRef(ref)) {
        const extra = 'attr/rows/' + TABLE_ID_EDGE_NAME + '/' + val;

        const target = router.objectVersionUIUrl(
          ref.entityName,
          ref.projectName,
          ref.artifactName,
          ref.artifactVersion,
          'obj',
          extra
        );
        history.push(target);
      }
    },
    [history, router, sharedRef]
  );

  const [initialFields, setInitialFields] = useState<string[]>([]);

  const parsedRef = useMemo(
    () => parseRefMaybe(datasetObject.rows),
    [datasetObject.rows]
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

  const numRowsQuery = useTableQueryStats(
    lookupKey?.entity ?? '',
    lookupKey?.project ?? '',
    lookupKey?.digest ?? '',
    {skip: lookupKey == null}
  );

  const numAddedRows = useMemo(
    () => Array.from(addedRows.values()).length,
    [addedRows]
  );

  const {numRowsToFetch, offset} = useMemo(() => {
    const rowsToFetch =
      numAddedRows <= paginationModel.page * paginationModel.pageSize
        ? paginationModel.pageSize
        : numAddedRows > (paginationModel.page + 1) * paginationModel.pageSize
        ? 0
        : paginationModel.pageSize - (numAddedRows % paginationModel.pageSize);

    const offsetVal =
      paginationModel.page * paginationModel.pageSize <= numAddedRows
        ? 0
        : paginationModel.page * paginationModel.pageSize - numAddedRows;

    return {numRowsToFetch: rowsToFetch, offset: offsetVal};
  }, [paginationModel, numAddedRows]);

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

  const [loadedRows, setLoadedRows] = useState<Array<{[key: string]: any}>>([]);
  const [fetchQueryLoaded, setFetchQueryLoaded] = useState(false);

  useEffect(() => {
    if (!fetchQuery.loading) {
      if (fetchQuery.result) {
        setLoadedRows(fetchQuery.result.rows);
      }
      setFetchQueryLoaded(true);
    }
  }, [fetchQuery.loading, fetchQuery.result]);

  const restoreRow = useCallback(
    (absoluteIndex: number) => {
      setDeletedRows(prev => prev.filter(index => index !== absoluteIndex));
    },
    [setDeletedRows]
  );

  const deleteRow = useCallback(
    (absoluteIndex: number) => {
      const rowKey = `${ADDED_ROW_ID_PREFIX}${absoluteIndex}`;
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
    setPaginationModel(prev => ({...prev, page: 0}));
    setAddedRows(prev => {
      const updatedMap = new Map(prev);
      const newId = `${ADDED_ROW_ID_PREFIX}${uuidv4()}`;
      console.log(initialFields);
      const newRow = {
        ___weave: {
          id: newId,
          isNew: true,
        },
        ...Object.fromEntries(initialFields.map(field => [field, ''])),
      };
      updatedMap.set(newId, newRow);
      return updatedMap;
    });
  }, [setAddedRows, initialFields]);

  const rows = useMemo(() => {
    if (fetchQueryLoaded) {
      return loadedRows.map((row, i) => {
        const digest = row.digest;
        const absoluteIndex =
          i + paginationModel.pageSize * paginationModel.page;
        const editedRow = editedCellsMap.get(absoluteIndex);
        const value = flattenObjectPreservingWeaveTypes(row.val);
        return {
          ___weave: {
            id: `${digest}_${absoluteIndex}`,
            index: absoluteIndex,
            isNew: false,
          },
          ...(editedRow ? {...value, ...editedRow} : value),
        };
      });
    }
    return [];
  }, [loadedRows, fetchQueryLoaded, editedCellsMap, paginationModel]);

  const combinedRows = useMemo(() => {
    if (
      !isEditing ||
      numAddedRows <= paginationModel.page * paginationModel.pageSize
    ) {
      return rows;
    }
    const startIndex = paginationModel.page * paginationModel.pageSize;
    const endIndex = startIndex + paginationModel.pageSize;
    const displayedAddedRows = Array.from(addedRows.values()).slice(
      startIndex,
      endIndex
    );
    return [...displayedAddedRows, ...rows];
  }, [rows, addedRows, numAddedRows, paginationModel, isEditing]);

  const columns = useMemo(() => {
    const allFields = combinedRows.reduce((acc, row) => {
      Object.keys(row)
        .filter(key => key !== '___weave')
        .forEach(key => acc.add(key));
      return acc;
    }, new Set<string>());

    if (initialFields.length === 0 && allFields.size > 0) {
      setInitialFields(Array.from(allFields));
    }

    const baseColumns: GridColDef[] = [
      {
        field: '_row_click',
        headerName: 'id',
        sortable: false,
        disableColumnMenu: true,
        width: 50,
        renderCell: params => {
          const rowId = params.id as string;
          if (isEditing && params.row.___weave?.isNew) {
            return null;
          }
          const digestStr = rowId.split('_')[0];
          const rowLabel = digestStr ? digestStr.slice(-4) : rowId;
          const rowSpan = (
            <Tooltip trigger={<RowId>{rowLabel}</RowId>} content={digestStr} />
          );
          return (
            <Box sx={{marginLeft: '8px'}}>
              <A onClick={() => onClick(rowId)}>{rowSpan}</A>
            </Box>
          );
        },
      },
      ...(isEditing
        ? [
            {
              field: 'controls',
              headerName: '',
              width: 48,
              sortable: false,
              filterable: false,
              editable: false,
              renderHeader: () => (
                <ControlsColumnHeader onAddRow={handleAddRowsClick} />
              ),
              renderCell: (params: GridRenderCellParams) => (
                <ControlCell
                  params={params}
                  deleteRow={deleteRow}
                  deleteAddedRow={deleteAddedRow}
                  restoreRow={restoreRow}
                  isDeleted={deletedRows.includes(params.row.___weave?.index)}
                  isNew={params.row.___weave?.isNew}
                />
              ),
            },
          ]
        : []),
    ];

    const fieldColumns: GridColDef[] = Array.from(allFields).map(field => ({
      field: field as string,
      headerName: field as string,
      flex: 1,
      editable: isEditing,
      sortable: !isEditing,
      filterable: false,
      renderCell: (params: GridRenderCellParams) => {
        const editedRow = editedCellsMap.get(params.row.___weave?.index);
        if (!isEditing) {
          return (
            <Box sx={{marginLeft: '8px'}}>
              <CellValue value={params.value} />
            </Box>
          );
        }
        return (
          <CellViewingRenderer
            {...params}
            isEdited={editedRow && editedRow[field as string] !== undefined}
            isDeleted={deletedRows.includes(params.row.___weave?.index)}
            isNew={params.row.___weave?.isNew}
          />
        );
      },
      renderEditCell: (params: GridRenderEditCellParams) => (
        <CellEditingRenderer {...params} />
      ),
    }));

    return [...baseColumns, ...fieldColumns];
  }, [
    combinedRows,
    editedCellsMap,
    deleteRow,
    restoreRow,
    deletedRows,
    deleteAddedRow,
    handleAddRowsClick,
    initialFields,
    isEditing,
    onClick,
  ]);

  return (
    <div style={{height: '100%', overflow: 'hidden'}}>
      <StyledDataGrid
        initialState={{
          pinnedColumns: {
            right: ['controls'],
          },
        }}
        disableColumnMenu={true}
        density="compact"
        rows={combinedRows}
        columns={columns}
        sortingMode="server"
        sortModel={sortModel}
        onSortModelChange={onSortModelChange}
        editMode="cell"
        pagination
        paginationMode="server"
        paginationModel={paginationModel}
        onPaginationModelChange={setPaginationModel}
        rowCount={
          (numRowsQuery.result?.count ?? 0) + (isEditing ? numAddedRows : 0)
        }
        disableMultipleColumnsSorting
        loading={!fetchQueryLoaded}
        disableRowSelectionOnClick
        keepBorders={false}
        pageSizeOptions={[50]}
        sx={{
          border: 'none',
          '& .MuiDataGrid-cell': {
            padding: '0',
          },
          '& .MuiDataGrid-columnHeaders': {
            borderBottom: '1px solid rgba(224, 224, 224, 1)',
            marginBottom: '-1px', // offset the border
          },
        }}
        processRowUpdate={processRowUpdate}
        getRowId={(row: GridRowModel) => row.___weave?.id ?? row.id}
      />
    </div>
  );
};
