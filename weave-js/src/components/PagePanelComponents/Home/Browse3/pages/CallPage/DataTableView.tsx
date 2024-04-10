import LinkIcon from '@mui/icons-material/Link';
import {Alert, Box} from '@mui/material';
import {GridColDef, useGridApiRef} from '@mui/x-data-grid-pro';
import {
  isAssignableTo,
  list,
  listObjectType,
  maybe,
  Type,
  typedDict,
  typedDictPropertyTypes,
} from '@wandb/weave/core';
import React, {FC, useContext, useEffect, useMemo} from 'react';

import {toWeaveType} from '../../../../../Panel2/toWeaveType';
import {flattenObject} from '../../../Browse2/browse2Util';
import {CellValue} from '../../../Browse2/CellValue';
import {WeaveflowPeekContext} from '../../context';
import {StyledDataGrid} from '../../StyledDataGrid';

export const DataTableView: FC<{
  data: Array<{[key: string]: any}>;
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
        return val;
      }
      return {'': val};
    });
  }, [props.data, props.displayKey]);

  const gridRows = useMemo(
    () =>
      (dataAsListOfDict ?? []).map((row, i) => ({
        id: i,
        ...flattenObject(row),
      })),
    [dataAsListOfDict]
  );

  // Autosize when rows change
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      apiRef.current.autosizeColumns({
        includeHeaders: true,
        includeOutliers: true,
      });
    }, 0);
    return () => {
      clearInterval(timeoutId);
    };
  }, [gridRows, apiRef]);

  const objectType = useMemo(() => {
    if (dataAsListOfDict == null) {
      return list(typedDict({}));
    }
    if (!Array.isArray(dataAsListOfDict)) {
      // Is this right here?
      return list(typedDict({}));
    }
    if (dataAsListOfDict.length === 0) {
      return list(typedDict({}));
    }
    return listObjectType(toWeaveType(dataAsListOfDict));
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
            onClick={() =>
              props.onLinkClick!(dataAsListOfDict[params.id as number])
            }
          />
        ),
      });
    }
    return [...res, ...typeToDataGridColumnSpec(objectType, isPeeking, true)];
  }, [props.onLinkClick, dataAsListOfDict, objectType, isPeeking]);
  const isSingleColumn = columnSpec.length === 1 && columnSpec[0].field === '';
  if (isSingleColumn) {
    columnSpec[0].flex = 1;
  }
  const hideHeader = isSingleColumn;
  const displayRows = 10;
  const hideFooter = gridRows.length <= displayRows;
  const headerHeight = 40;
  const footerHeight = 52;
  const rowHeight = 36;
  const height =
    (hideHeader ? 0 : headerHeight) +
    (hideFooter ? 0 : footerHeight) +
    rowHeight * Math.min(displayRows, gridRows.length);
  return (
    <div style={{display: 'flex', flexDirection: 'column', width: '100%'}}>
      {props.isTruncated && (
        <Alert severity="warning">
          Showing {dataAsListOfDict.length.toLocaleString()} rows only.
        </Alert>
      )}
      <Box
        sx={{
          height,
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
  //   const cols: GridColDef[] = [];
  //   const colGrouping: GridColumnGroup[] = [];
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
              return <CellValue value={params.row[innerKey] ?? ''} />;
            },
          },
        ];
      }
      return valTypeCols.map(col => ({
        ...col,
        maxWidth,
        // field: `${key}.${col.field}`,
        // headerName: `${key}.${col.field}`,
      }));
    });
  }
  return [];
};
