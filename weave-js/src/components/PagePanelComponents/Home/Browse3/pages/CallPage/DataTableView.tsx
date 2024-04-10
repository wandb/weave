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
import React, {
  FC,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import {useHistory} from 'react-router-dom';

import {isWeaveObjectRef, parseRef} from '../../../../../../react';
import {flattenObject} from '../../../Browse2/browse2Util';
import {CellValue} from '../../../Browse2/CellValue';
import {
  useWeaveflowCurrentRouteContext,
  WeaveflowPeekContext,
} from '../../context';
import {StyledDataGrid} from '../../StyledDataGrid';
import {TABLE_ID_EDGE_NAME} from '../wfReactInterface/constants';
import {useWFHooks} from '../wfReactInterface/context';
import {TableQuery} from '../wfReactInterface/wfDataModelHooksInterface';

const MAX_ROWS = 1000;
export const USE_TABLE_FOR_ARRAYS = false;

// Create a context that can be consumed by ObjectViewerSection
export const WeaveCHTableSourceRefContext = React.createContext<
  string | undefined
>(undefined);

export const WeaveCHTable: FC<{
  tableRefUri: string;
  fullHeight?: boolean;
}> = props => {
  const sourceRef = useContext(WeaveCHTableSourceRefContext);
  const fetchQuery = useValueOfRefUri(props.tableRefUri, {
    limit: MAX_ROWS + 1,
  });
  const [isTruncated, setIsTruncated] = useState(false);
  const [sourceRows, setSourceRows] = useState<any[] | undefined>();
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
  useEffect(() => {
    if (sourceRows != null) {
      return;
    }
    if (fetchQuery.loading) {
      return;
    }
    setIsTruncated((fetchQuery.result ?? []).length > MAX_ROWS);
    setSourceRows((fetchQuery.result ?? []).slice(0, MAX_ROWS));
  }, [sourceRows, fetchQuery]);

  return (
    <DataTableView
      data={sourceRows ?? []}
      loading={fetchQuery.loading}
      isTruncated={isTruncated}
      displayKey="val"
      onLinkClick={onClickEnabled ? onClick : undefined}
      fullHeight={props.fullHeight}
    />
  );
};

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

  const dataAsListOfDict = useMemo(() => {
    return props.data.map(row => {
      let val = row;
      if (props.displayKey) {
        val = row[props.displayKey];
      }
      if (val == null) {
        return {};
      } else if (typeof val === 'object' && !Array.isArray(val)) {
        return flattenObject(val);
      }
      return {'': val};
    });
  }, [props.data, props.displayKey]);

  const gridRows = useMemo(
    () =>
      (dataAsListOfDict ?? []).map((row, i) => ({
        id: i,
        ...row,
      })),
    [dataAsListOfDict]
  );

  // Autosize when rows change
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
