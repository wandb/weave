import {Box} from '@mui/material';
import {
  GridColDef,
  GridEventListener,
  GridPaginationModel,
  GridSortModel,
  useGridApiRef,
} from '@mui/x-data-grid-pro';
import {
  isAssignableTo,
  list,
  maybe,
  Type,
  typedDict,
  typedDictPropertyTypes,
} from '@wandb/weave/core';
import {useDeepMemo} from '@wandb/weave/hookUtils';
import _ from 'lodash';
import React, {
  FC,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {useHistory} from 'react-router-dom';
import styled from 'styled-components';

import {
  isWeaveObjectRef,
  parseRef,
  parseRefMaybe,
} from '../../../../../../react';
import {Tooltip} from '../../../../../Tooltip';
import {CellValue} from '../../../Browse2/CellValue';
import {
  useWeaveflowCurrentRouteContext,
  WeaveflowPeekContext,
} from '../../context';
import {flattenObjectPreservingWeaveTypes} from '../../flattenObject';
import {DEFAULT_PAGE_SIZE} from '../../grid/pagination';
import {StyledDataGrid} from '../../StyledDataGrid';
import {CustomWeaveTypeProjectContext} from '../../typeViews/CustomWeaveTypeDispatcher';
import {A} from '../common/Links';
import {TABLE_ID_EDGE_NAME} from '../wfReactInterface/constants';
import {useWFHooks} from '../wfReactInterface/context';
import {SortBy} from '../wfReactInterface/traceServerClientTypes';

export const RowId = styled.span`
  font-family: 'Inconsolata', monospace;
`;
RowId.displayName = 'S.RowId';

// Controls whether to use a table for arrays or not.
export const USE_TABLE_FOR_ARRAYS = false;

// Callers are responsible for setting the source ref context. This is because
// by the time the WeaveCHTable is rendered, the ref is already resolved to be a
// table ref. However, that is just an implementation detail. The user-facing
// contract is in terms of the the object ref, so we need to have the later in
// order to render links.
export const WeaveCHTableSourceRefContext = React.createContext<
  string | undefined
>(undefined);

// This component is designed to be used to render weave `tables`.
export const WeaveCHTable: FC<{
  tableRefUri: string;
  fullHeight?: boolean;
}> = props => {
  // Gets the source of this Table (set by a few levels up)
  const sourceRef = useContext(WeaveCHTableSourceRefContext);

  const {useTableQueryStats, useTableRowsQuery} = useWFHooks();

  const parsedRef = useMemo(
    () => parseRefMaybe(props.tableRefUri),
    [props.tableRefUri]
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

  const [limit, setLimit] = useState(DEFAULT_PAGE_SIZE);
  const [offset, setOffset] = useState(0);
  const [sortBy, setSortBy] = useState<SortBy[]>([]);
  const [sortModel, setSortModel] = useState<GridSortModel>([]);

  const onSortModelChange = useCallback(
    (model: GridSortModel) => {
      setSortModel(model);
    },
    [setSortModel]
  );

  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize: DEFAULT_PAGE_SIZE,
  });

  const onPaginationModelChange = useCallback(
    (model: GridPaginationModel) => {
      setPaginationModel(model);
    },
    [setPaginationModel]
  );

  useEffect(() => {
    setOffset(paginationModel.page * paginationModel.pageSize);
    setLimit(paginationModel.pageSize);
  }, [paginationModel]);

  useEffect(() => {
    setSortBy(
      sortModel.map(sort => ({
        field: sort.field,
        direction: sort.sort === 'asc' ? 'asc' : 'desc',
      }))
    );
  }, [sortModel]);

  const fetchQuery = useTableRowsQuery(
    lookupKey?.entity ?? '',
    lookupKey?.project ?? '',
    lookupKey?.digest ?? '',
    undefined,
    limit,
    offset,
    sortBy,
    false,
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

  const pagedRows = useMemo(() => {
    return loadedRows ?? [];
  }, [loadedRows]);

  const totalRows = useMemo(() => {
    return numRowsQuery.result?.count ?? pagedRows.length;
  }, [numRowsQuery.result, pagedRows]);

  // In this block, we setup a click handler. The underlying datatable is more general
  // and not aware of the nuances of our links and ref model. Therefore, we handle
  // the click in this component and navigate to the appropriate page.
  const history = useHistory();
  const onClickEnabled = sourceRef != null;
  const router = useWeaveflowCurrentRouteContext();
  const onClick = useCallback(
    val => {
      const ref = parseRef(sourceRef!);
      if (isWeaveObjectRef(ref)) {
        let extra = ref.artifactRefExtra ?? '';
        if (extra !== '') {
          extra += '/';
        }
        extra += TABLE_ID_EDGE_NAME + '/' + val.digest;

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
    [history, sourceRef, router]
  );

  const pageControl: DataTableServerSidePaginationControls = useMemo(
    () => ({
      paginationModel,
      onPaginationModelChange,
      totalRows,
      pageSizeOptions: [DEFAULT_PAGE_SIZE],
      sortModel,
      onSortModelChange,
    }),
    [
      paginationModel,
      onPaginationModelChange,
      totalRows,
      sortModel,
      onSortModelChange,
    ]
  );

  return (
    <CustomWeaveTypeProjectContext.Provider
      value={{
        entity: lookupKey?.entity ?? '',
        project: lookupKey?.project ?? '',
      }}>
      <DataTableView
        data={pagedRows}
        loading={!fetchQueryLoaded}
        displayKey="val"
        onLinkClick={onClickEnabled ? onClick : undefined}
        fullHeight={props.fullHeight}
        pageControl={pageControl}
      />
    </CustomWeaveTypeProjectContext.Provider>
  );
};

export type DataTableServerSidePaginationControls = {
  paginationModel: GridPaginationModel;
  onPaginationModelChange: (model: GridPaginationModel) => void;
  totalRows: number;
  pageSizeOptions: number[];
  sortModel: GridSortModel;
  onSortModelChange: (model: GridSortModel) => void;
};

// This is a general purpose table view that can be used to render any data.
export const DataTableView: FC<{
  data: Array<{[key: string]: any}>;
  fullHeight?: boolean;
  loading?: boolean;
  displayKey?: string;
  onLinkClick?: (row: any) => void;
  pageControl?: DataTableServerSidePaginationControls;
  autoPageSize?: boolean;
}> = props => {
  const apiRef = useGridApiRef();
  const {isPeeking} = useContext(WeaveflowPeekContext);

  // First, we convert the data to a list of dictionaries, since that is the
  // format expected by the rest of the logic. We also flatten any nested
  // objects so the keys are always dot-separated paths.
  const dataAsListOfDict = useMemo(() => {
    return props.data.map(row => {
      let val = row;
      if (props.displayKey) {
        val = row[props.displayKey];
      }
      if (val == null) {
        return {};
      } else if (typeof val === 'object' && !Array.isArray(val)) {
        return flattenObjectPreservingWeaveTypes(val);
      }
      return {'': val};
    });
  }, [props.data, props.displayKey]);

  // Next, we add an id to each row (index-based)
  const gridRows = useMemo(
    () =>
      (dataAsListOfDict ?? []).map((row, i) => ({
        id: i,
        data: row,
      })),
    [dataAsListOfDict]
  );

  // Next, we determine the type of the data. Previously, we used the WeaveJS
  // `Type` system to determine the type of the data. However, this is way to
  // slow for big tables and too detailed for our purposes. We just need to know
  // if each column is a string, number, boolean, or list. (or mixed)
  const objectType = useMemo(() => {
    if (dataAsListOfDict == null) {
      return list(typedDict({}));
    }
    if (!Array.isArray(dataAsListOfDict)) {
      throw new Error('Expected array, got ' + typeof dataAsListOfDict);
    }
    if (dataAsListOfDict.length === 0) {
      return list(typedDict({}));
    }

    const propertyTypes: {[col: string]: Type} = {};
    dataAsListOfDict.forEach(row => {
      Object.keys(row).forEach(col => {
        if (propertyTypes[col] == null) {
          if (row[col] == null) {
            // Do nothing
          } else if (typeof row[col] === 'boolean') {
            if (
              propertyTypes[col] != null &&
              propertyTypes[col] !== 'boolean'
            ) {
              propertyTypes[col] = 'any';
            } else {
              propertyTypes[col] = 'boolean';
            }
          } else if (typeof row[col] === 'string') {
            if (propertyTypes[col] != null && propertyTypes[col] !== 'string') {
              propertyTypes[col] = 'any';
            } else {
              propertyTypes[col] = 'string';
            }
          } else if (typeof row[col] === 'number') {
            if (propertyTypes[col] != null && propertyTypes[col] !== 'number') {
              propertyTypes[col] = 'any';
            } else {
              propertyTypes[col] = 'number';
            }
          } else if (Array.isArray(row[col])) {
            if (
              propertyTypes[col] != null &&
              !_.isEqual(propertyTypes[col], {type: 'list', objectType: 'any'})
            ) {
              propertyTypes[col] = 'any';
            } else {
              propertyTypes[col] = {type: 'list', objectType: 'any'};
            }
          } else {
            propertyTypes[col] = 'any';
          }
        }
      });
    });
    return typedDict(propertyTypes);
  }, [dataAsListOfDict]);

  const propsDataRef = useRef(props.data);
  useEffect(() => {
    propsDataRef.current = props.data;
  }, [props.data]);

  const objectTypeDeepMemo = useDeepMemo(objectType);

  // Here we define the column spec for the table. It is based on
  // the type of the data and if we have a link or not.
  const dataInitializedColumnSpec: GridColDef[] = useMemo(() => {
    const res: GridColDef[] = [];
    if (props.onLinkClick) {
      res.push({
        field: '_row_click',
        headerName: 'id',
        width: 50,
        renderCell: params => {
          const rowId = params.id as number;
          const dataRefValue = propsDataRef.current[rowId];
          const {digest} = dataRefValue;
          const rowLabel = digest ? digest.slice(-4) : rowId;
          const rowSpan = (
            <Tooltip trigger={<RowId>{rowLabel}</RowId>} content={digest} />
          );
          return (
            <A onClick={() => props.onLinkClick!(dataRefValue)}>{rowSpan}</A>
          );
        },
      });
    }
    return [
      ...res,
      ...typeToDataGridColumnSpec(objectTypeDeepMemo, isPeeking, true),
    ];
  }, [props.onLinkClick, objectTypeDeepMemo, isPeeking]);

  // Finally, we do some math to determine the height of the table.
  const isSingleColumn =
    USE_TABLE_FOR_ARRAYS &&
    dataInitializedColumnSpec.length === 1 &&
    dataInitializedColumnSpec[0].field === '';
  if (isSingleColumn) {
    dataInitializedColumnSpec[0].flex = 1;
  }
  const hideHeader = isSingleColumn;
  const displayRows = 10;
  const hideFooter = USE_TABLE_FOR_ARRAYS && gridRows.length <= displayRows;
  const headerHeight = 40;
  const footerHeight = 52;
  const rowHeight = 36;
  const contentHeight = rowHeight * Math.min(displayRows, gridRows.length);
  const loadingHeight = 100;
  const height =
    (hideHeader ? 0 : headerHeight) +
    (hideFooter ? 0 : footerHeight) +
    (props.loading ? loadingHeight : contentHeight);

  const [columnSpec, setColumnSpec] = useState<GridColDef[]>([]);

  // This effect will resize the columns after the table is rendered. We use a
  // timeout to ensure that the table has been rendered before we resize the
  // columns.
  const hasLinkClick = props.onLinkClick != null;
  useEffect(() => {
    let mounted = true;

    // Update the column set if the column spec changes (ignore empty columns
    // which can occur during loading)
    setColumnSpec(curr => {
      const dataFieldSet = new Set(
        dataInitializedColumnSpec.map(col => col.field)
      );
      const currFieldSet = new Set(curr.map(col => col.field));
      if (dataFieldSet.size > (hasLinkClick ? 1 : 0)) {
        // Update if they are different
        if (!_.isEqual(dataFieldSet, currFieldSet)) {
          return dataInitializedColumnSpec;
        }
      }
      return curr;
    });

    const timeoutId = setTimeout(() => {
      if (!mounted) {
        return;
      }
      apiRef.current.autosizeColumns({
        includeHeaders: true,
        includeOutliers: true,
      });
      // apiRef.current.forceUpdate()
    }, 0);
    return () => {
      mounted = false;
      clearInterval(timeoutId);
    };
  }, [dataInitializedColumnSpec, apiRef, hasLinkClick]);

  const onColumnOrderChange: GridEventListener<'columnOrderChange'> =
    useCallback(params => {
      const oldIndex = params.oldIndex;
      const newIndex = params.targetIndex;
      setColumnSpec(currSpec => {
        const col = currSpec[oldIndex];
        currSpec.splice(oldIndex, 1);
        currSpec.splice(newIndex, 0, col);
        return currSpec;
      });
    }, []);

  const onColumnWidthChange: GridEventListener<'columnWidthChange'> =
    useCallback(params => {
      const field = params.colDef.field;
      const newWidth = params.width;
      setColumnSpec(currSpec => {
        for (const col of currSpec) {
          if (col.field === field) {
            col.width = newWidth;
          }
        }
        return currSpec;
      });
    }, []);

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        width: '100%',
        height: props.fullHeight ? '100%' : 'inherit',
      }}>
      <Box
        sx={{
          height: props.fullHeight ? `100%` : height,
          width: '100%',
        }}>
        <StyledDataGrid
          // Start Column Menu
          // We need the ColumnMenu to support Pinning.
          // disableColumnMenu
          // Let's disable Filters on Object Data for now
          disableColumnFilter={true}
          disableMultipleColumnsFiltering={true}
          // ColumnPinning seems to be required in DataGridPro, else it crashes.
          // However, in this case it is also useful.
          disableColumnPinning={false}
          // ColumnReorder is useful for large datasets
          disableColumnReorder={false}
          // ColumnResize is useful for large datasets
          disableColumnResize={false}
          // Column Selector might be overkill for now, disable it.
          disableColumnSelector={true}
          // No need for sorting on multiple columns MVP
          disableMultipleColumnsSorting={true}
          // End Column Menu
          hideFooter={hideFooter}
          slots={{
            ...(hideHeader
              ? {
                  columnHeaders: () => null,
                }
              : {}),
          }}
          autoPageSize={props.autoPageSize}
          keepBorders={false}
          apiRef={apiRef}
          density="compact"
          rows={gridRows}
          columns={columnSpec}
          loading={props.loading}
          disableRowSelectionOnClick
          sx={{
            border: 'none',
          }}
          pagination
          paginationModel={props.pageControl?.paginationModel}
          onPaginationModelChange={props.pageControl?.onPaginationModelChange}
          pageSizeOptions={props.pageControl?.pageSizeOptions}
          paginationMode={props.pageControl ? 'server' : 'client'}
          rowCount={props.pageControl?.totalRows}
          sortingMode={props.pageControl ? 'server' : 'client'}
          sortModel={props.pageControl?.sortModel}
          onSortModelChange={props.pageControl?.onSortModelChange}
          onColumnOrderChange={onColumnOrderChange}
          onColumnWidthChange={onColumnWidthChange}
        />
      </Box>
    </div>
  );
};

export const typeToDataGridColumnSpec = (
  type: Type,
  isPeeking?: boolean,
  disableEdits?: boolean,
  parentKey?: string
): GridColDef[] => {
  if (isAssignableTo(type, {type: 'typedDict', propertyTypes: {}})) {
    const maxWidth = window.innerWidth * (isPeeking ? 0.5 : 0.75);
    const minWidth = 100;
    const propertyTypes = typedDictPropertyTypes(type);
    return Object.entries(propertyTypes).flatMap(([key, valueType]) => {
      const innerKey = parentKey ? `${parentKey}.${key}` : key;
      const valTypeCols = typeToDataGridColumnSpec(
        valueType,
        undefined,
        undefined,
        innerKey
      );
      if (valTypeCols.length === 0) {
        let colType: GridColDef['type'] = 'string';
        let editable = false;
        if (isAssignableTo(valueType, maybe('boolean'))) {
          editable = true;
          colType = 'boolean';
        } else if (isAssignableTo(valueType, maybe('number'))) {
          editable = true;
          colType = 'number';
        } else if (isAssignableTo(valueType, maybe('string'))) {
          editable = true;
        } else if (
          isAssignableTo(valueType, maybe({type: 'list', objectType: 'any'}))
        ) {
          return [
            {
              maxWidth,
              minWidth,
              flex: 1,
              type: 'string' as const,
              editable: false,
              field: innerKey,
              headerName: innerKey,
              renderCell: params => {
                const listValue = params.row.data[innerKey];
                if (listValue == null) {
                  return '-';
                }
                const listLen = listValue.length;
                return `[${listLen} item list]`;
              },
            },
          ];
        }
        return [
          {
            maxWidth,
            minWidth,
            flex: 1,
            display: 'flex',
            type: colType,
            editable: editable && !disableEdits,
            field: innerKey,
            headerName: innerKey,
            renderCell: params => {
              const data = params.row.data[innerKey];
              return <CellValue value={data ?? ''} />;
            },
          },
        ];
      }
      return valTypeCols.map(col => ({
        ...col,
        maxWidth,
      }));
    });
  }
  return [];
};
