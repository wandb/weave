import {Box} from '@material-ui/core';
import LinkIcon from '@mui/icons-material/Link';
import {Alert} from '@mui/material';
import {GridColDef, useGridApiRef} from '@mui/x-data-grid-pro';
import React, {FC, useContext, useEffect, useMemo} from 'react';

import {
  isAssignableTo,
  listObjectType,
  maybe,
  Type,
  typedDict,
  typedDictPropertyTypes,
} from '../../../../../core';
import {toWeaveType} from '../../../../Panel2/toWeaveType';
import {flattenObject} from '../../Browse2/browse2Util';
import {CellValue} from '../../Browse2/CellValue';
import {WeaveflowPeekContext} from '../context';
import {StyledDataGrid} from '../StyledDataGrid';

const MAX_ROWS = 1000;

export const TableView: FC<{
  data: any[];
  displayKey?: string;
  loading?: boolean;
  isTruncated?: boolean;
  onLinkClick?: (row: any) => void;
}> = props => {
  const data = useMemo(() => {
    return props.data.map(row => {
      let val = row;
      if (props.displayKey) {
        val = row[props.displayKey];
      }
      if (val == null) {
        return {};
      } else if (typeof val === 'object') {
        return val;
      }
      return {'   ': val};
    });
  }, [props.data, props.displayKey]);
  const apiRef = useGridApiRef();
  const {isPeeking} = useContext(WeaveflowPeekContext);

  const gridRows = useMemo(
    () =>
      data.map((row: {[key: string]: any}, i: number) => ({
        id: i,
        ...flattenObject(row),
      })),
    [data]
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
    if (data == null) {
      return typedDict({});
    }
    return listObjectType(toWeaveType(data));
  }, [data]);

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
    console.log({objectType});
    return [...res, ...typeToDataGridColumnSpec(objectType, isPeeking, true)];
  }, [props.onLinkClick, objectType, isPeeking, props.data]);
  console.log(gridRows);
  const height = 92 + 36 * Math.min(10, gridRows.length);
  return (
    <div style={{display: 'flex', flexDirection: 'column', width: '100%'}}>
      {props.isTruncated && (
        <Alert severity="warning">
          Showing {MAX_ROWS.toLocaleString()} rows only.
        </Alert>
      )}
      <Box
        sx={{
          height,
          width: '100%',
        }}>
        <StyledDataGrid
          keepBorders={false}
          apiRef={apiRef}
          density="compact"
          experimentalFeatures={{columnGrouping: true}}
          rows={gridRows}
          columns={columnSpec}
          initialState={{
            pagination: {
              paginationModel: {
                pageSize: 10,
              },
            },
          }}
          loading={props.loading}
          disableRowSelectionOnClick
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
                return (
                  // <Typography>
                  params.row[innerKey] == null
                    ? '-'
                    : `[${params.row[innerKey].length} item list]`
                  // </Typography>
                );
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
        flex: 1,
        // field: `${key}.${col.field}`,
        // headerName: `${key}.${col.field}`,
      }));
    });
  }
  return [];
};
