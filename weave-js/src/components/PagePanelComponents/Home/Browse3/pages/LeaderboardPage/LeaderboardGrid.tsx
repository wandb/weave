import {Box} from '@mui/material';
import {
  GridColDef,
  GridColumnGroupingModel,
  GridPaginationModel,
  GridRenderCellParams,
} from '@mui/x-data-grid-pro';
import React, {useCallback, useMemo, useState} from 'react';

import {StyledDataGrid} from '../../StyledDataGrid';
import {PaginationButtons} from '../CallsPage/CallsTableButtons';
import {LeaderboardData} from './hooks';

interface LeaderboardGridProps {
  data: LeaderboardData;
  onCellClick: (modelName: string, metricName: string, score: number) => void;
}

interface RowData {
  id: number;
  model: string;
  [key: string]: number | string;
}

export const LeaderboardGrid: React.FC<LeaderboardGridProps> = ({
  data,
  onCellClick,
}) => {
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    pageSize: 25,
    page: 0,
  });

  const metricRanges = useMemo(() => {
    const ranges: {[key: string]: {min: number; max: number}} = {};
    Object.keys(data.metrics).forEach(metric => {
      const scores = data.models
        .map(model => data.scores?.[model]?.[metric])
        .filter(score => score !== undefined);
      ranges[metric] = {
        min: Math.min(...scores),
        max: Math.max(...scores),
      };
    });
    return ranges;
  }, [data]);

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

  const columns: GridColDef[] = useMemo(
    () => [
      {field: 'model', headerName: 'Model', width: 200, flex: 1},
      ...Object.keys(data.metrics).map(metric => ({
        field: metric,
        headerName: metric,
        width: 130,
        flex: 1,
        renderCell: (params: GridRenderCellParams) => {
          let inner = params.value;
          if (typeof inner === 'number') {
            if (inner < 1) {
              inner = `${(inner * 100).toFixed(2)}%`;
            } else {
              inner = `${inner.toFixed(2)}`;
            }
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
    [data.metrics, getColorForScore, onCellClick]
  );

  const rows: RowData[] = useMemo(
    () =>
      data.models.map((model, index) => ({
        id: index,
        model,
        ...data.scores[model],
      })),
    [data.models, data.scores]
  );

  const groupingModel: GridColumnGroupingModel = useMemo(
    () => {
      return [
        {
          groupId: 'metrics',
          children: Object.keys(data.metrics).map(metric => ({
            field: metric,
          })),
        },
      ];
    },
    [data.metrics]
  );

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
        pageSizeOptions={[25]}
        disableRowSelectionOnClick
        hideFooterSelectedRowCount
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
