import {Box} from '@mui/material';
import {
  GridColDef,
  GridFooterContainer,
  GridPagination,
  GridPaginationModel,
  GridRenderCellParams,
  GridRenderEditCellParams,
  GridRowModel,
  GridSortModel,
  useGridApiRef,
} from '@mui/x-data-grid-pro';
import {A} from '@wandb/weave/common/util/links';
import {Button} from '@wandb/weave/components/Button';
import {RowId} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/CallPage/DataTableView';
import {Tooltip} from '@wandb/weave/components/Tooltip';
import get from 'lodash/get';
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
import {
  CELL_COLORS,
  CellEditingRenderer,
  CellViewingRenderer,
  ControlCell,
  DELETED_CELL_STYLES,
} from './CellRenderers';
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

interface OrderedRow {
  ___weave: any;
  [key: string]: any;
}

export const EditableDatasetView: FC<EditableDataTableViewProps> = ({
  datasetObject,
  isEditing,
}) => {
  const {useTableRowsQuery, useTableQueryStats} = useWFHooks();
  const [sortBy, setSortBy] = useState<SortBy[]>([]);
  const [sortModel, setSortModel] = useState<GridSortModel>([]);
  const [columnWidths, setColumnWidths] = useState<{[key: string]: number}>({});
  const apiRef = useGridApiRef();

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
    editedRows,
    getEditedFields,
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
        const digest = val.split('_')[0];
        const extra = 'attr/rows/' + TABLE_ID_EDGE_NAME + '/' + digest;

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
      const newRow = {
        ___weave: {
          id: newId,
          isNew: true,
        },
        ...Object.fromEntries(initialFields.map(field => [field, ''])),
      };
      updatedMap.set(newId, newRow);

      // Wait for the next tick to ensure the row is added and grid is updated
      setTimeout(() => {
        const firstField = initialFields[0];
        if (firstField) {
          apiRef.current.scrollToIndexes({rowIndex: numAddedRows});
        }
      }, 0);

      return updatedMap;
    });
  }, [setAddedRows, initialFields, apiRef, numAddedRows]);

  const rows = useMemo(() => {
    if (fetchQueryLoaded) {
      return loadedRows.map((row, i) => {
        const digest = row.digest;
        const absoluteIndex =
          i + paginationModel.pageSize * paginationModel.page;
        const value = flattenObjectPreservingWeaveTypes(row.val);
        const editedRow = editedRows.get(absoluteIndex);
        return {
          ___weave: {
            id: `${digest}_${absoluteIndex}`,
            index: absoluteIndex,
            isNew: false,
            serverValue: value,
          },
          ...(editedRow ? {...value, ...editedRow} : value),
        };
      });
    }
    return [];
  }, [loadedRows, fetchQueryLoaded, editedRows, paginationModel]);

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

  const preserveFieldOrder = useCallback(
    (row: OrderedRow): OrderedRow => {
      const orderedRow: OrderedRow = {___weave: row.___weave};
      initialFields.forEach(field => {
        orderedRow[field] = row[field] !== undefined ? row[field] : '';
      });
      return orderedRow;
    },
    [initialFields]
  );

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
        width: columnWidths._row_click ?? 50,
        minWidth: 50,
        maxWidth: 50,
        renderCell: params => {
          const rowId = params.id as string;
          const digestStr = rowId.split('_')[0];
          const rowLabel = digestStr ? digestStr.slice(-4) : rowId;
          const rowSpan = (
            <Tooltip trigger={<RowId>{rowLabel}</RowId>} content={digestStr} />
          );
          return (
            <Box
              sx={{
                height: '100%',
                width: '100%',
                padding: '8px',
                display: 'flex',
                alignItems: 'center',
                opacity: deletedRows.includes(params.row.___weave?.index)
                  ? DELETED_CELL_STYLES.opacity
                  : 1,
                textDecoration: deletedRows.includes(params.row.___weave?.index)
                  ? DELETED_CELL_STYLES.textDecoration
                  : 'none',
                backgroundColor: deletedRows.includes(
                  params.row.___weave?.index
                )
                  ? CELL_COLORS.DELETED
                  : params.row.___weave?.isNew
                  ? CELL_COLORS.NEW
                  : CELL_COLORS.TRANSPARENT,
              }}>
              {!params.row.___weave?.isNew ? (
                <A onClick={() => onClick(rowId)}>{rowSpan}</A>
              ) : null}
            </Box>
          );
        },
      },
      ...(isEditing
        ? [
            {
              field: 'controls',
              headerName: '',
              width: columnWidths.controls ?? 48,
              sortable: false,
              filterable: false,
              editable: false,
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
      width: columnWidths[field as string] ?? undefined,
      flex: columnWidths[field as string] ? undefined : 1,
      minWidth: 100,
      editable: isEditing,
      sortable: !isEditing,
      filterable: false,
      renderCell: (params: GridRenderCellParams) => {
        if (!isEditing) {
          return (
            <Box sx={{marginLeft: '8px'}}>
              <CellValue value={params.value} />
            </Box>
          );
        }
        const rowIndex = params.row.___weave?.index;

        const editedFields =
          rowIndex != null && !params.row.___weave?.isNew
            ? getEditedFields(rowIndex)
            : {};
        return (
          <CellViewingRenderer
            {...params}
            isEdited={editedFields[field as string] !== undefined}
            isDeleted={deletedRows.includes(params.row.___weave?.index)}
            isNew={params.row.___weave?.isNew}
            serverValue={get(
              loadedRows[rowIndex - offset]?.val ?? {},
              field as string
            )}
          />
        );
      },
      renderEditCell: (params: GridRenderEditCellParams) => {
        const rowIndex = params.row.___weave?.index;
        const serverValue =
          rowIndex != null && !params.row.___weave?.isNew
            ? get(loadedRows[rowIndex - offset]?.val ?? {}, params.field)
            : '';
        return (
          <CellEditingRenderer
            {...params}
            serverValue={serverValue}
            preserveFieldOrder={preserveFieldOrder}
          />
        );
      },
    }));

    return [...baseColumns, ...fieldColumns];
  }, [
    combinedRows,
    getEditedFields,
    deleteRow,
    restoreRow,
    deletedRows,
    deleteAddedRow,
    initialFields,
    isEditing,
    onClick,
    offset,
    loadedRows,
    columnWidths,
    preserveFieldOrder,
  ]);

  const handleColumnWidthChange = useCallback((params: any) => {
    setColumnWidths(prev => ({
      ...prev,
      [params.colDef.field]: params.width,
    }));
  }, []);

  const CustomFooter = useCallback(() => {
    return (
      <GridFooterContainer>
        {isEditing && (
          <Box
            sx={{
              padding: '8px 16px',
              display: 'flex',
              justifyContent: 'flex-start',
              alignItems: 'center',
              flex: 1,
            }}>
            <Button
              icon="add-new"
              onClick={handleAddRowsClick}
              variant="secondary"
              size="small"
              tooltip="Add row">
              Add row
            </Button>
          </Box>
        )}
        <Box
          sx={{
            padding: '0 8px',
          }}>
          <GridPagination />
        </Box>
      </GridFooterContainer>
    );
  }, [isEditing, handleAddRowsClick]);

  return (
    <div style={{display: 'flex', flexDirection: 'column', height: '100%'}}>
      <StyledDataGrid
        apiRef={apiRef}
        initialState={{
          pinnedColumns: {
            right: ['controls'],
          },
          columns: {
            columnVisibilityModel: {},
            orderedFields: columns.map(col => col.field),
          },
        }}
        onColumnWidthChange={handleColumnWidthChange}
        columnBufferPx={50}
        autoHeight={false}
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
        slots={{
          footer: isEditing ? CustomFooter : undefined,
        }}
        sx={{
          border: 'none',
          flex: 1,
          height: '100%',
          '& .MuiDataGrid-cell': {
            padding: '0',
          },
          '& .MuiDataGrid-columnHeaders': {
            borderBottom: '1px solid rgba(224, 224, 224, 1)',
            marginBottom: '-1px', // offset the border
          },
          '& .MuiDataGrid-cell[data-field="controls"]': {
            borderLeft: 'none',
            boxShadow: 'none',
            '&:focus, &:focus-within': {
              outline: 'none',
            },
            '&:hover': {
              backgroundColor: 'transparent',
            },
            '&.MuiDataGrid-cell--editing': {
              backgroundColor: 'transparent',
              boxShadow: 'none',
            },
            '&.Mui-selected, &.Mui-selected:hover, &.Mui-selected:focus': {
              backgroundColor: 'transparent',
              boxShadow: 'none',
            },
          },
          '& .MuiDataGrid-columnHeader[data-field="controls"]': {
            borderLeft: 'none',
            boxShadow: 'none',
            border: 'none',
            '&:focus, &:focus-within': {
              outline: 'none',
            },
          },
          '& .MuiDataGrid-footerContainer': {
            backgroundColor: 'white',
            border: 'none',
            borderTop: '1px solid rgba(224, 224, 224, 1)',
          },
          '& .MuiDataGrid-columnSeparator': {
            visibility: 'visible',
          },
          '& .MuiDataGrid-filler--pinnedRight': {
            borderLeft: 'none',
          },
        }}
        getRowId={(row: GridRowModel) => row.___weave?.id ?? row.id}
      />
    </div>
  );
};
