import {GridApiPro, GridColDef} from '@mui/x-data-grid-pro';
import React, {useCallback, useMemo, useRef} from 'react';

import {traverse, TraverseContext} from '../../pages/CallPage/traverse';
import {ValueView} from '../../pages/CallPage/ValueView';
import {StyledDataGrid} from '../../StyledDataGrid';

interface OpenAICompletionViewProps {
  entity: string;
  project: string;
  mode?: string;
  data: {
    val: {
      client: {
        base_url: string;
      };
    };
    weave_type: {
      type: string;
    };
  };
}

const DEFAULT_ROW_HEIGHT = 38;

export const OpenAICompletionView = ({data}: OpenAICompletionViewProps) => {
  const apiRef = useRef<GridApiPro>(null!);

  // Create tree data structure from data.val
  const {rows} = useMemo(() => {
    const contexts: Array<TraverseContext> = [];

    traverse(data.val, context => {
      // Skip hidden keys that start with underscore
      if (context.depth !== 0 && context.path.hasHiddenKey()) {
        return 'skip';
      }
      contexts.push(context);
      return true;
    });

    const rowsInner = contexts.map(c => ({
      id: c.path.toString(),
      depth: c.depth,
      isLeaf: c.isLeaf,
      path: c.path,
      value: c.value,
      valueType: c.valueType,
      parent:
        c.depth > 0
          ? contexts.find(
              parent =>
                parent.depth === c.depth - 1 &&
                c.path.toString().startsWith(parent.path.toString())
            )
          : undefined,
    }));

    return {rows: rowsInner};
  }, [data.val]);

  // Setup columns
  const columns: GridColDef[] = useMemo(() => {
    return [
      {
        field: 'value',
        headerName: '',
        flex: 1,
        display: 'flex',
        sortable: false,
        renderCell: ({row}) => {
          return <ValueView data={row} isExpanded={false} />;
        },
      },
    ];
  }, []);

  // Get tree data path for each row
  const getTreeDataPath = useCallback((row: any) => {
    return row.path.toStringArray();
  }, []);

  // Always expand all rows
  const isGroupExpandedByDefault = useCallback(() => {
    return true;
  }, []);

  // Setup grouping column with no interaction
  const groupingColDef = useMemo(
    () => ({
      headerName: '',
      hideDescendantCount: true,
      renderCell: (params: any) => {
        return (
          <div
            style={{
              paddingLeft: `${params.row.depth * 16}px`,
              display: 'flex',
              alignItems: 'center',
              pointerEvents: 'none', // Disable all interactions
            }}>
            {params.row.path.tail()?.toString() || 'root'}
          </div>
        );
      },
    }),
    []
  );

  // Memoize getRowHeight function
  const getRowHeight = useCallback(() => {
    return DEFAULT_ROW_HEIGHT;
  }, []);

  return (
    <div style={{height: '100%', width: '100%'}}>
      <StyledDataGrid
        apiRef={apiRef}
        // Column Menu settings
        disableColumnFilter={true}
        disableColumnMenu={true}
        disableColumnPinning={false}
        disableColumnReorder={true}
        disableColumnResize={false}
        disableColumnSelector={true}
        disableMultipleColumnsFiltering={true}
        disableMultipleColumnsSorting={true}
        // Tree data configuration
        treeData
        getTreeDataPath={getTreeDataPath}
        rows={rows}
        columns={columns}
        isGroupExpandedByDefault={isGroupExpandedByDefault}
        groupingColDef={groupingColDef}
        // Layout settings
        columnHeaderHeight={0}
        rowHeight={DEFAULT_ROW_HEIGHT}
        getRowHeight={getRowHeight}
        hideFooter
        rowSelection={false}
        // Styling
        sx={{
          '& .MuiDataGrid-filler': {
            height: '0px !important',
          },
          '& .MuiDataGrid-row:hover': {
            backgroundColor: 'inherit',
          },
          '& .MuiDataGrid-columnHeaders': {
            display: 'none',
          },
          '& .MuiDataGrid-columnHeader': {
            display: 'none',
          },
        }}
      />
    </div>
  );
};
