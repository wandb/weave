import {
  DataGridProProps,
  GridApiPro,
  GridColDef,
  GridRowHeightParams,
} from '@mui/x-data-grid-pro';
import _ from 'lodash';
import React, {useEffect, useMemo, useState} from 'react';

import {useWeaveContext} from '../../../../../../context';
import {constString, opGet} from '../../../../../../core';
import {StyledDataGrid} from '../../StyledDataGrid';
import {isRef} from '../common/util';
import {ObjectViewerGroupingCell} from './ObjectViewerGroupingCell';
import {mapObject, traverse, TraverseContext, traversed} from './traverse';
import {ValueView} from './ValueView';

type Data = Record<string, any>;

type ObjectViewerProps = {
  apiRef: React.MutableRefObject<GridApiPro>;
  data: Data;
  isExpanded: boolean;
};

// Traverse the data and find all ref URIs.
const getRefs = (data: Data): string[] => {
  const refs = new Set<string>();
  traverse(data, (context: TraverseContext) => {
    if (isRef(context.value)) {
      refs.add(context.value);
    }
  });
  return Array.from(refs);
};

type RefValues = Record<string, any>; // ref URI to value

export const ObjectViewer = ({apiRef, data, isExpanded}: ObjectViewerProps) => {
  const weave = useWeaveContext();
  const {client} = weave;
  const [resolvedData, setResolvedData] = useState<Data>(data);

  useEffect(() => {
    const refs = getRefs(data);
    const refValueNodes = refs.map(ref =>
      opGet({uri: constString(ref)} as any)
    );
    const refQueries = refValueNodes.map(node => client.query(node));
    Promise.allSettled(refQueries).then(values => {
      const refValues: RefValues = {};
      for (const [r, v] of _.zip(refs, values)) {
        if (!r || !v) {
          // Shouldn't be possible
          continue;
        }
        let val = r;
        if (v.status === 'rejected') {
          console.error('Error resolving ref', r);
        } else {
          val = v.value;
          if (typeof val === 'object' && val !== null) {
            val = {
              ...v.value,
              _ref: r,
            };
          }
        }
        refValues[r] = val;
      }
      const resolved = mapObject(data, context => {
        if (isRef(context.value)) {
          return refValues[context.value];
        }
        return context.value;
      });
      setResolvedData(resolved);
    });
  }, [data, client]);

  const rows = useMemo(() => {
    const contexts = traversed(
      resolvedData,
      c =>
        c.depth !== 0 && !c.path.endsWith('_ref') && !c.path.endsWith('_type')
    );
    return contexts.map((c, id) => ({id, ...c}));
  }, [resolvedData]);

  const columns: GridColDef[] = [
    {
      field: 'value',
      headerName: 'Value',
      flex: 1,
      sortable: false,
      renderCell: ({row}) => {
        return <ValueView data={row} isExpanded={isExpanded} />;
      },
    },
  ];

  const groupingColDef: DataGridProProps['groupingColDef'] = useMemo(
    () => ({
      headerName: 'Path',
      hideDescendantCount: true,
      renderCell: params => <ObjectViewerGroupingCell {...params} />,
    }),
    []
  );

  return (
    <div style={{overflow: 'hidden'}}>
      <StyledDataGrid
        apiRef={apiRef}
        treeData
        getTreeDataPath={row => row.path.toStringArray()}
        rows={rows}
        columns={columns}
        defaultGroupingExpansionDepth={isExpanded ? -1 : 0}
        columnHeaderHeight={38}
        getRowHeight={(params: GridRowHeightParams) => {
          if (
            params.model.valueType === 'string' &&
            !isRef(params.model.value)
          ) {
            return 'auto';
          }
          return 38;
        }}
        hideFooter
        rowSelection={false}
        disableColumnMenu={true}
        groupingColDef={groupingColDef}
        sx={{
          '& .MuiDataGrid-row:hover': {
            backgroundColor: 'inherit',
          },
        }}
      />
    </div>
  );
};
