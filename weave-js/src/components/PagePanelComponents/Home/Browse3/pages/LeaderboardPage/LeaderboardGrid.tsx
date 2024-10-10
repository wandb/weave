import {Box} from '@mui/material';
import {
  GridColDef,
  GridColumnGroup,
  GridColumnGroupingModel,
  GridColumnNode,
  GridPaginationModel,
  GridRenderCellParams,
  GridSortDirection,
} from '@mui/x-data-grid-pro';
import React, {useCallback, useMemo, useState} from 'react';

import {parseRefMaybe, SmallRef} from '../../../Browse2/SmallRef';
import {StyledDataGrid} from '../../StyledDataGrid';
import {PaginationButtons} from '../CallsPage/CallsTableButtons';
// import {ObjectVersionLink} from '../common/Links';
import {buildTree} from '../common/tabularListViews/buildTree';
import {LeaderboardData} from './hooks';

interface LeaderboardGridProps {
  entity: string;
  project: string;
  data: LeaderboardData;
  loading: boolean;
  onCellClick: (modelName: string, metricName: string, score: number) => void;
}

type RowData = {
  id: number;
  model: string;
} & LeaderboardData['scores'][string];

export const LeaderboardGrid: React.FC<LeaderboardGridProps> = ({
  entity,
  project,
  data,
  loading,
  onCellClick,
}) => {
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    pageSize: 50,
    page: 0,
  });

  const orderedMetrics = useMemo(() => {
    return Object.keys(data.metrics);
    // return Object.keys(data.metrics).sort((a, b) => {
    //   return a.localeCompare(b);
    // });
  }, [data.metrics]);

  const metricRanges = useMemo(() => {
    const ranges: {[key: string]: {min: number; max: number}} = {};
    orderedMetrics.forEach(metric => {
      const scores = data.models
        .map(model => data.scores?.[model]?.[metric]?.value)
        .filter(score => score !== undefined);
      ranges[metric] = {
        min: Math.min(...scores),
        max: Math.max(...scores),
      };
    });
    return ranges;
  }, [data.models, data.scores, orderedMetrics]);

  const getColorForScore = useCallback(
    (metric: string, score: number | undefined) => {
      if (score === undefined) {
        return 'transparent';
      }
      const {min, max} = metricRanges[metric];
      const normalizedScore = (score - min) / (max - min);
      return `hsl(${120 * normalizedScore}, 70%, 85%)`;
    },
    [metricRanges]
  );

  const rows: RowData[] = useMemo(
    () =>
      data.models.map((model, index) => ({
        id: index,
        model,
        ...data.scores[model],
      })) as RowData[],
    [data.models, data.scores]
  );

  const columns: Array<GridColDef<RowData>> = useMemo(
    () => [
      {
        field: 'model',
        headerName: 'Model',
        minWidth: 100,
        flex: 1,
        renderCell: (params: GridRenderCellParams) => {
          const modelRef = parseRefMaybe(params.value);
          if (modelRef) {
            return (
              <div
                style={{
                  width: '100%',
                  height: '100%',
                  alignContent: 'center',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  lineHeight: '20px',
                }}>
                <SmallRef objRef={modelRef} />
              </div>
            );
          }
          return <div>{params.value}</div>;
        },
      },
      ...orderedMetrics.map(metric => ({
        field: metric,
        headerName: data.metrics[metric].metricPath.split('.').pop(),
        minWidth: 100,
        flex: 1,
        valueGetter: (value: RowData) => {
          return value?.value;
        },
        getSortComparator: (dir: GridSortDirection) => (a: any, b: any) => {
          const aValue = a;
          const bValue = b;
          if (aValue == null && bValue == null) {
            return 0;
          }
          // Ignoring direction here allows nulls to always sort to the end
          if (aValue == null) {
            return 1;
          }
          if (bValue == null) {
            return -1;
          }
          if (typeof aValue === 'number' && typeof bValue === 'number') {
            if (dir === 'asc') {
              return aValue - bValue;
            } else {
              return bValue - aValue;
            }
          }
          return aValue.localeCompare(bValue);
        },
        renderCell: (params: GridRenderCellParams) => {
          let inner = params.value;
          if (typeof inner === 'number') {
            if (inner < 1) {
              inner = `${(inner * 100).toFixed(2)}%`;
            } else {
              inner = `${inner.toFixed(2)}`;
            }
          } else {
            inner = JSON.stringify(params.value);
          }
          // const value =
          // <CellValue value={params.value} />
          return (
            <div
              style={{
                width: '100%',
                height: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                backgroundColor: getColorForScore(metric, params.value),
              }}
              onClick={() =>
                onCellClick(
                  params.row.model,
                  params.field as string,
                  params.value as number
                )
              }>
              {' '}
              {inner}
            </div>
          );
        },
      })),
    ],
    [data.metrics, getColorForScore, onCellClick, orderedMetrics]
  );

  const tree = buildTree([...Object.keys(data.metrics)]);
  let groupingModel: GridColumnGroupingModel = tree.children.filter(
    c => 'groupId' in c
  ) as GridColumnGroup[];
  groupingModel = walkGroupingModel(groupingModel, node => {
    if ('groupId' in node) {
      if (node.children.length === 1) {
        if (
          'groupId' in node.children[0] &&
          !node.headerName?.includes(':') &&
          !node.children[0].headerName?.includes(':')
        ) {
          const currNode = node;
          node = node.children[0];
          node.headerName = currNode.headerName + '.' + node.headerName;
        } else {
          // pass
          // node = node.children[0];
        }
      }
    }
    return node;
  }) as GridColumnGroup[];
  groupingModel = walkGroupingModel(groupingModel, node => {
    if ('groupId' in node) {
      node.renderHeaderGroup = params => {
        const ref = parseRefMaybe(
          `weave:///${entity}/${project}/object/${node.headerName}` ?? ''
        );
        // console.log(node.headerName, ref);
        if (ref) {
          return <SmallRef objRef={ref} />;
        }
        return <div>{node.headerName}</div>;
      };
    }
    return node;
  }) as GridColumnGroup[];

  // const groupingModel: GridColumnGroupingModel = useMemo(
  //   () => {
  //     return [
  //       {
  //         groupId: 'metrics',
  //         children: Object.keys(data.metrics).map(metric => ({
  //           field: metric,
  //         })),
  //       },
  //     ];
  //   },
  //   [data.metrics]
  // );

  return (
    <Box
      sx={{
        height: '100%',
        width: '100%',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden', // Prevent outer container from scrolling
      }}>
      <StyledDataGrid
        rows={rows}
        columns={columns}
        columnGroupingModel={groupingModel}
        pagination
        paginationModel={paginationModel}
        onPaginationModelChange={setPaginationModel}
        pageSizeOptions={[50]}
        disableRowSelectionOnClick
        hideFooterSelectedRowCount
        disableMultipleColumnsSorting={false}
        columnHeaderHeight={40}
        loading={loading}
        sx={{
          borderRadius: 0,
          '& .MuiDataGrid-footerContainer': {
            justifyContent: 'flex-start',
          },
          '& .MuiDataGrid-cell': {
            cursor: 'pointer',
          },
          flexGrow: 1,
          width: 'calc(100% + 1px)', // Add 1px to account for the right border
          '& .MuiDataGrid-main': {
            overflow: 'hidden',
          },
          '& .MuiDataGrid-virtualScroller': {
            overflow: 'auto',
          },
          '& .MuiDataGrid-columnHeaders': {
            overflow: 'hidden',
          },
        }}
        slots={{
          // columnMenu: CallsCustomColumnMenu,
          pagination: PaginationButtons,
        }}
      />
    </Box>
  );
};

const walkGroupingModel = (
  nodes: GridColumnNode[],
  fn: (node: GridColumnNode) => GridColumnNode
) => {
  return nodes.map(node => {
    if ('children' in node) {
      node.children = walkGroupingModel(node.children, fn);
    }
    return fn(node);
  });
};
