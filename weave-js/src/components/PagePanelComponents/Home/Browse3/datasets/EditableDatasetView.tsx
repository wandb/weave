import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import {Box, Typography} from '@mui/material';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import MenuItem from '@mui/material/MenuItem';
import {
  GridColDef,
  GridColumnGroup,
  GridColumnMenu,
  GridColumnMenuItemProps,
  GridColumnMenuProps,
  GridFooterContainer,
  GridPagination,
  GridPaginationModel,
  GridRenderCellParams,
  GridRowModel,
  GridSortModel,
  useGridApiRef,
} from '@mui/x-data-grid-pro';
import {A} from '@wandb/weave/common/util/links';
import {Button} from '@wandb/weave/components/Button';
import {TextField} from '@wandb/weave/components/Form/TextField';
import {RowId} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/CallPage/DataTableView';
import {Tooltip} from '@wandb/weave/components/Tooltip';
import _ from 'lodash';
import get from 'lodash/get';
import React, {
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import {useHistory} from 'react-router-dom';
import {v4 as uuidv4} from 'uuid';

import {isWeaveObjectRef, parseRef, parseRefMaybe} from '../../../../../react';
import {CellValue} from '../../Browse2/CellValue';
import {useWeaveflowCurrentRouteContext} from '../context';
import {flattenObjectPreservingWeaveTypes} from '../flattenObject';
import {WeaveCHTableSourceRefContext} from '../pages/CallPage/DataTableView';
import {TABLE_ID_EDGE_NAME} from '../pages/wfReactInterface/constants';
import {useWFHooks} from '../pages/wfReactInterface/context';
import {SortBy} from '../pages/wfReactInterface/traceServerClientTypes';
import {ReusableDrawer} from '../ReusableDrawer';
import {StyledDataGrid} from '../StyledDataGrid';
import {
  CELL_COLORS,
  ControlCell,
  DatasetCellRenderer,
  DELETED_CELL_STYLES,
} from './CellRenderers';
import {useDatasetEditContext} from './DatasetEditorContext';

const ADDED_ROW_ID_PREFIX = 'new-';

// Dataset object schema as it is stored in the database.
export interface DatasetObjectVal {
  _type: 'Dataset';
  name: string | null;
  description: string | null;
  rows: string;
  _class_name: 'Dataset';
  _bases: ['Object', 'BaseModel'];
}

export interface EditableDatasetViewProps {
  datasetObject: DatasetObjectVal;
  isEditing?: boolean;
  hideRemoveForAddedRows?: boolean;
  showAddRowButton?: boolean;
  hideIdColumn?: boolean;
  disableNewRowHighlight?: boolean;
  // If true, then we assume that all the data is client-side
  // and we can make changes to columns
  isNewDataset?: boolean;
  extraFooterContent?: React.ReactNode;
  footerHeight?: number;
  // New props for column injection
  columnsBeforeData?: GridColDef[];
  columnsAfterData?: GridColDef[];
  columnGroups?: GridColumnGroup[];
}

interface OrderedRow {
  ___weave: any;
  [key: string]: any;
}

export const EditableDatasetView: React.FC<EditableDatasetViewProps> = ({
  datasetObject,
  isEditing = false,
  hideRemoveForAddedRows = false,
  showAddRowButton = true,
  hideIdColumn = false,
  disableNewRowHighlight = false,
  isNewDataset = false,
  extraFooterContent = null,
  footerHeight = undefined,
  columnsBeforeData = [],
  columnsAfterData = [],
  columnGroups = [],
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
    deletedRows,
    setDeletedRows,
    setAddedRows,
    addedRows,
    isFieldEdited,
  } = useDatasetEditContext();

  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize: 50,
  });

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

  const tableQueryParams = useMemo(
    () => ({
      entity: lookupKey?.entity ?? '',
      project: lookupKey?.project ?? '',
      digests: lookupKey?.digest ? [lookupKey?.digest] : [],
      skip: lookupKey == null,
    }),
    [lookupKey]
  );

  const numRowsQuery = useTableQueryStats(tableQueryParams);

  const totalRows = useMemo(() => {
    if (numRowsQuery.result == null) {
      return 0;
    }
    return numRowsQuery.result.tables?.[0]?.count ?? 0;
  }, [numRowsQuery.result]);

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

  const fetchQuery = useTableRowsQuery({
    entity: lookupKey?.entity ?? '',
    project: lookupKey?.project ?? '',
    digest: lookupKey?.digest ?? '',
    limit: numRowsToFetch,
    offset,
    sortBy,
    skip: lookupKey == null,
  });

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

  const rows = useMemo(() => {
    if (fetchQueryLoaded) {
      return loadedRows.map(row => {
        const digest = row.digest;
        const value = flattenObjectPreservingWeaveTypes(row.val);
        const editedRow = editedRows.get(row.original_index);
        return {
          ___weave: {
            id: `${digest}_${row.original_index}`,
            index: row.original_index,
            isNew: false,
            serverValue: value,
          },
          ...(editedRow ? {...value, ...editedRow} : value),
        };
      });
    }
    return [];
  }, [loadedRows, fetchQueryLoaded, editedRows]);

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

  const allFields = useMemo(() => {
    return combinedRows.reduce((acc, row) => {
      Object.keys(row)
        .filter(key => key !== '___weave')
        .forEach(key => {
          if (!acc.includes(key)) {
            acc.push(key);
          }
        });
      return acc;
    }, new Array<string>());
  }, [combinedRows]);

  const [initialFields, setInitialFields] = useState<string[]>([]);
  useEffect(() => {
    if (initialFields.length === 0 && allFields.length > 0) {
      setInitialFields(allFields);
    }
  }, [initialFields, allFields]);

  const handleAddColumnClick = useCallback(() => {
    let targetNumber = allFields.length + 1;
    let newFieldName = 'column_' + targetNumber;
    while (allFields.includes(newFieldName)) {
      targetNumber++;
      newFieldName = 'column_' + targetNumber;
    }
    setAddedRows(prev => {
      const addedRowEntries = Array.from(prev.entries());
      const newEntries: Array<[string, any]> = addedRowEntries.map(([key, row]) => {
        const newRow = {
          ...row,
          [newFieldName]: '',
        };
        return [key, newRow] as [string, any];
      });

      return new Map(newEntries);
    });
  }, [allFields, setAddedRows]);

  const initialFieldsSet = useMemo(
    () => new Set(initialFields),
    [initialFields]
  );

  const preserveFieldOrder = useCallback(
    (row: OrderedRow): OrderedRow => {
      const orderedRow: OrderedRow = {___weave: row.___weave};
      // First add all fields that are in initialFields in the correct order
      initialFields.forEach(field => {
        orderedRow[field] = row[field] !== undefined ? row[field] : '';
      });

      // Then add any additional fields that weren't in initialFields
      Object.keys(row).forEach(field => {
        if (field !== '___weave' && !initialFieldsSet.has(field)) {
          orderedRow[field] = row[field];
        }
      });

      return orderedRow;
    },
    [initialFields, initialFieldsSet]
  );

  const columns = useMemo(() => {
    // Create an array to hold all columns
    const allColumns: GridColDef[] = [];
    
    // Start with columnsBeforeData
    allColumns.push(...columnsBeforeData);

    // Add ID column only if not hidden
    if (!hideIdColumn) {
      allColumns.push({
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
                  : params.row.___weave?.isNew && !disableNewRowHighlight
                  ? CELL_COLORS.NEW
                  : CELL_COLORS.TRANSPARENT,
              }}>
              {!params.row.___weave?.isNew ? (
                <A onClick={() => onClick(rowId)}>{rowSpan}</A>
              ) : null}
            </Box>
          );
        },
      });
    }

    // Add control column if editing is enabled, regardless of hideIdColumn setting
    if (isEditing) {
      allColumns.push({
        field: 'controls',
        headerName: '',
        width: columnWidths.controls ?? 48,
        sortable: false,
        filterable: false,
        editable: false,
        disableColumnMenu: true,
        renderCell: (params: GridRenderCellParams) => (
          <ControlCell
            params={params}
            deleteRow={deleteRow}
            deleteAddedRow={deleteAddedRow}
            restoreRow={restoreRow}
            isDeleted={deletedRows.includes(params.row.___weave?.index)}
            isNew={params.row.___weave?.isNew}
            hideRemoveForAddedRows={hideRemoveForAddedRows}
            disableNewRowHighlight={disableNewRowHighlight}
          />
        ),
      });
    }

    const fieldColumns: GridColDef[] = Array.from(allFields).map(field => ({
      field: field as string,
      headerName: field as string,
      width: columnWidths[field as string] ?? undefined,
      flex: columnWidths[field as string] ? undefined : 1,
      minWidth: 100,
      editable: false,
      sortable: true,
      filterable: false,
      pinnable: false,
      reorderable: false,
      disableReorder: true,
      renderCell: (params: GridRenderCellParams) => {
        if (!isEditing) {
          return (
            <div
              style={{
                marginLeft: '8px',
                height: '100%',
                alignContent: 'center',
              }}>
              <CellValue value={params.value} />
            </div>
          );
        }
        const rowIndex = params.row.___weave?.index;

        return (
          <DatasetCellRenderer
            {...params}
            isEdited={
              rowIndex != null && !params.row.___weave?.isNew
                ? isFieldEdited(rowIndex, field as string)
                : false
            }
            isDeleted={deletedRows.includes(params.row.___weave?.index)}
            isNew={params.row.___weave?.isNew}
            serverValue={get(
              loadedRows[rowIndex - offset]?.val ?? {},
              field as string
            )}
            disableNewRowHighlight={disableNewRowHighlight}
            preserveFieldOrder={preserveFieldOrder}
          />
        );
      },
    }));

    // Add field columns
    allColumns.push(...fieldColumns);
    
    // Add columnsAfterData
    allColumns.push(...columnsAfterData);

    return allColumns;
  }, [
    allFields,
    hideIdColumn,
    isEditing,
    columnWidths,
    deletedRows,
    disableNewRowHighlight,
    onClick,
    deleteRow,
    deleteAddedRow,
    restoreRow,
    hideRemoveForAddedRows,
    isFieldEdited,
    loadedRows,
    offset,
    preserveFieldOrder,
    columnsBeforeData,
    columnsAfterData,
  ]);

  const handleColumnWidthChange = useCallback((params: any) => {
    setColumnWidths(prev => ({
      ...prev,
      [params.colDef.field]: params.width,
    }));
  }, []);

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
        ...Object.fromEntries(allFields.map(field => [field, ''])),
      };
      updatedMap.set(newId, newRow);

      // Wait for the next tick to ensure the row is added and grid is updated
      setTimeout(() => {
        const firstField = allFields[0];
        if (firstField) {
          apiRef.current.scrollToIndexes({rowIndex: numAddedRows});
        }
      }, 0);

      return updatedMap;
    });
  }, [setAddedRows, allFields, apiRef, numAddedRows]);

  const CustomFooter = useCallback(() => {
    const footHeightOverride: React.CSSProperties = {};
    if (footerHeight) {
      footHeightOverride.height = footerHeight;
      footHeightOverride.minHeight = footerHeight;
    }
    return (
      <GridFooterContainer sx={footHeightOverride}>
        {isEditing && showAddRowButton && (
          <Box
            sx={{
              padding: '8px 16px',
              display: 'flex',
              justifyContent: 'flex-start',
              alignItems: 'center',
              flex: 1,
              gap: 1,
            }}>
            {extraFooterContent}
            <Button
              icon="add-new"
              onClick={handleAddRowsClick}
              variant="secondary"
              tooltip="Add row">
              Add row
            </Button>
            {isNewDataset && (
              <Button
                icon="add-new"
                onClick={handleAddColumnClick}
                variant="secondary"
                tooltip="Add column">
                Add column
              </Button>
            )}
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
  }, [
    footerHeight,
    isEditing,
    showAddRowButton,
    handleAddRowsClick,
    isNewDataset,
    handleAddColumnClick,
    extraFooterContent,
  ]);

  const knownFieldNames = useMemo(() => {
    return new Set(combinedRows.flatMap(row => Object.keys(row)));
  }, [combinedRows]);

  const [edittingFieldName, setEdittingFieldName] = useState<string | null>(
    null
  );
  const [newFieldName, setNewFieldName] = useState<string | null>(null);

  const inputError = useMemo(() => {
    if (!newFieldName) {
      return 'Column name is required';
    }
    if (newFieldName.length > 255) {
      return 'Column name must be less than 255 characters';
    }
    if (newFieldName.length < 4) {
      return 'Column name must be at least 4 characters';
    }

    // valid characters: alphabetic + underscore
    if (!/^[a-zA-Z0-9_]+$/.test(newFieldName)) {
      return 'Column name must contain only alphabetic characters and underscores';
    }

    //cannot start with a number
    if (/^\d/.test(newFieldName)) {
      return 'Column name cannot start with a number';
    }

    if (
      knownFieldNames.has(newFieldName) &&
      newFieldName !== edittingFieldName
    ) {
      return 'Column name must be unique';
    }
    return null;
  }, [newFieldName, knownFieldNames, edittingFieldName]);

  const handleStartFieldName = useCallback((fieldName: string) => {
    setEdittingFieldName(fieldName);
    setNewFieldName(fieldName);
  }, []);

  const handleSaveNewFieldName = useCallback(() => {
    setAddedRows(prev => {
      const addedRowEntries = Array.from(prev.entries());
      const newEntries: Array<[string, any]> = addedRowEntries.map(([key, row]) => {
        const val = row[edittingFieldName ?? ''];
        const newRow = {
          ..._.omit(row, edittingFieldName ?? ''),
          [newFieldName ?? '']: val,
        };
        return [key, newRow] as [string, any];
      });

      return new Map(newEntries);
    });
    setEdittingFieldName(null);
    setNewFieldName(null);
  }, [edittingFieldName, newFieldName, setAddedRows]);

  const handleDeleteColumn = useCallback(
    (fieldName: string) => {
      setAddedRows(prev => {
        const newEntries: Array<[string, any]> = Array.from(prev.entries()).map(([key, row]) => {
          const newRow = _.omit(row, fieldName);
          return [key, newRow] as [string, any];
        });
        console.log(newEntries);
        return new Map(newEntries);
      });
      setEdittingFieldName(null);
      setNewFieldName(null);
    },
    [setAddedRows]
  );

  function CustomEditItem(props: GridColumnMenuItemProps) {
    return (
      <MenuItem onClick={() => handleStartFieldName(props.colDef.field)}>
        <ListItemIcon>
          <EditIcon fontSize="small" />
        </ListItemIcon>
        <ListItemText>Edit</ListItemText>
      </MenuItem>
    );
  }

  function CustomDeleteItem(props: GridColumnMenuItemProps) {
    return (
      <MenuItem onClick={() => handleDeleteColumn(props.colDef.field)}>
        <ListItemIcon>
          <DeleteIcon fontSize="small" />
        </ListItemIcon>
        <ListItemText>Delete</ListItemText>
      </MenuItem>
    );
  }

  function CustomColumnMenu(props: GridColumnMenuProps) {
    return (
      <GridColumnMenu
        {...props}
        slots={{
          columnMenuColumnsItem: null,
          columnMenuEditItem: CustomEditItem,
          columnMenuDeleteItem: CustomDeleteItem,
        }}
      />
    );
  }

  return (
    <div style={{display: 'flex', flexDirection: 'column', height: '100%'}}>
      <ReusableDrawer
        open={!!edittingFieldName}
        title="Edit Column Name"
        onClose={() => setEdittingFieldName(null)}
        onSave={() => {
          handleSaveNewFieldName();
        }}
        saveDisabled={!!inputError || newFieldName === edittingFieldName}>
        <TextField
          value={newFieldName ?? ''}
          onChange={value => setNewFieldName(value)}
          placeholder="Column Name"
          errorState={!!inputError}
        />
        {inputError && <Typography color="error">{inputError}</Typography>}
      </ReusableDrawer>
      <StyledDataGrid
        data-testid="dataset-table"
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
        columnGroupingModel={columnGroups}
        onColumnWidthChange={handleColumnWidthChange}
        columnBufferPx={50}
        autoHeight={false}
        disableColumnMenu={!isNewDataset}
        density="compact"
        rows={combinedRows}
        columns={columns}
        sortingMode="server"
        sortModel={sortModel}
        onSortModelChange={onSortModelChange}
        pagination
        paginationMode="server"
        paginationModel={paginationModel}
        onPaginationModelChange={setPaginationModel}
        rowCount={totalRows + (isEditing ? numAddedRows : 0)}
        disableMultipleColumnsSorting
        loading={!fetchQueryLoaded}
        disableRowSelectionOnClick
        keepBorders={false}
        pageSizeOptions={[50]}
        slots={{
          footer: isEditing ? CustomFooter : undefined,
          columnMenu: CustomColumnMenu,
        }}
        sx={{
          border: 'none',
          flex: 1,
          height: '100%',
          '& .MuiDataGrid-cell': {
            padding: '0',
            // This vertical / horizontal center aligns <span>'s inside of the columns
            // Fixes an issue where boolean checkboxes are top-aligned pre-edit
            '& .MuiBox-root': {
              '& span.cursor-inherit': {
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                height: '34px',
              },
            },
            lineHeight: '20px',
          },
          // Removed default MUI blue from editing cell
          '.MuiDataGrid-cell.MuiDataGrid-cell--editing': {
            '&:focus, &:focus-within': {
              outline: 'none',
            },
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
