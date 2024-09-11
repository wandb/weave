import LinkIcon from '@mui/icons-material/Link';
import {Alert, Box} from '@mui/material';
import {GridColDef, useGridApiRef} from '@mui/x-data-grid-pro';
import {
  isAssignableTo,
  list,
  maybe,
  Type,
  typedDict,
  typedDictPropertyTypes,
} from '@wandb/weave/core';
import _ from 'lodash';
import React, {FC, useCallback, useContext, useEffect, useMemo} from 'react';
import {useHistory} from 'react-router-dom';

import {
  isWeaveObjectRef,
  parseRef,
  WeaveObjectRef,
} from '../../../../../../react';
import {flattenObjectPreservingWeaveTypes} from '../../../Browse2/browse2Util';
import {CellValue} from '../../../Browse2/CellValue';
import {
  useWeaveflowCurrentRouteContext,
  WeaveflowPeekContext,
} from '../../context';
import {StyledDataGrid} from '../../StyledDataGrid';
import {CustomWeaveTypeProjectContext} from '../../typeViews/CustomWeaveTypeDispatcher';
import {TABLE_ID_EDGE_NAME} from '../wfReactInterface/constants';
import {useWFHooks} from '../wfReactInterface/context';
import {TableQuery} from '../wfReactInterface/wfDataModelHooksInterface';

// Controls the maximum number of rows to display in the table
const MAX_ROWS = 10_000;

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

  // Retrieves the data for the table, with a limit of MAX_ROWS + 1
  const fetchQuery = useValueOfRefUri(props.tableRefUri, {
    limit: MAX_ROWS + 1,
  });

  const parsedRef = useMemo(
    () => parseRef(props.tableRefUri) as WeaveObjectRef,
    [props.tableRefUri]
  );

  // Determines if the table itself is truncated
  const isTruncated = useMemo(() => {
    return (fetchQuery.result ?? []).length > MAX_ROWS;
  }, [fetchQuery.result]);

  // `sourceRows` are the effective rows to display. If the table is truncated,
  // we only display the first MAX_ROWS rows.
  const sourceRows = useMemo(() => {
    return (fetchQuery.result ?? []).slice(0, MAX_ROWS);
  }, [fetchQuery.result]);

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

  return (
    <CustomWeaveTypeProjectContext.Provider
      value={{entity: parsedRef.entityName, project: parsedRef.projectName}}>
      <DataTableView
        data={sourceRows ?? []}
        loading={fetchQuery.loading}
        isTruncated={isTruncated}
        // Display key is "val" as the resulting rows have metadata/ref
        // information outside of the actual data
        displayKey="val"
        onLinkClick={onClickEnabled ? onClick : undefined}
        fullHeight={props.fullHeight}
      />
    </CustomWeaveTypeProjectContext.Provider>
  );
};

// This is a general purpose table view that can be used to render any data.
export const DataTableView: FC<{
  data: Array<{[key: string]: any}>;
  fullHeight?: boolean;
  loading?: boolean;
  displayKey?: string;
  isTruncated?: boolean;
  onLinkClick?: (row: any) => void;
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
        ...row,
      })),
    [dataAsListOfDict]
  );

  // This effect will resize the columns after the table is rendered. We use a
  // timeout to ensure that the table has been rendered before we resize the
  // columns.
  useEffect(() => {
    let mounted = true;
    const timeoutId = setTimeout(() => {
      if (!mounted) {
        return;
      }
      apiRef.current.autosizeColumns({
        includeHeaders: true,
        includeOutliers: true,
      });
    }, 0);
    return () => {
      mounted = false;
      clearInterval(timeoutId);
    };
  }, [gridRows, apiRef]);

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

  // Here we define the column spec for the table. It is based on
  // the type of the data and if we have a link or not.
  const columnSpec: GridColDef[] = useMemo(() => {
    const res: GridColDef[] = [];
    if (props.onLinkClick) {
      res.push({
        field: '_row_click',
        headerName: '',
        width: 50,
        renderCell: params => (
          <LinkIcon
            style={{
              cursor: 'pointer',
            }}
            onClick={() => props.onLinkClick!(props.data[params.id as number])}
          />
        ),
      });
    }
    return [...res, ...typeToDataGridColumnSpec(objectType, isPeeking, true)];
  }, [props.onLinkClick, props.data, objectType, isPeeking]);

  // Finally, we do some math to determine the height of the table.
  const isSingleColumn =
    USE_TABLE_FOR_ARRAYS &&
    columnSpec.length === 1 &&
    columnSpec[0].field === '';
  if (isSingleColumn) {
    columnSpec[0].flex = 1;
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
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        width: '100%',
        height: props.fullHeight ? '100%' : 'inherit',
      }}>
      {props.isTruncated && (
        <Alert severity="warning">
          Showing {dataAsListOfDict.length.toLocaleString()} rows only.
        </Alert>
      )}
      <Box
        sx={{
          height: props.fullHeight
            ? `calc(100% - ${props.isTruncated ? '48px' : '0px'})`
            : height,
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
          autoPageSize={true}
          keepBorders={false}
          apiRef={apiRef}
          density="compact"
          experimentalFeatures={{columnGrouping: true}}
          rows={gridRows}
          columns={columnSpec}
          loading={props.loading}
          disableRowSelectionOnClick
          sx={{
            border: 'none',
          }}
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
        let colType = 'string';
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
              type: 'string',
              editable: false,
              field: innerKey,
              headerName: innerKey,
              renderCell: params => {
                const listValue = params.row[innerKey];
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
            type: colType,
            editable: editable && !disableEdits,
            field: innerKey,
            headerName: innerKey,
            renderCell: params => {
              const data = params.row[innerKey];
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

const useValueOfRefUri = (refUriStr: string, tableQuery?: TableQuery) => {
  const {useRefsData} = useWFHooks();
  const data = useRefsData([refUriStr], tableQuery);
  return useMemo(() => {
    if (data.loading) {
      return {
        loading: true,
        result: undefined,
      };
    }
    if (data.result == null || data.result.length === 0) {
      return {
        loading: true,
        result: undefined,
      };
    }
    return {
      loading: false,
      result: data.result[0],
    };
  }, [data]);
};
