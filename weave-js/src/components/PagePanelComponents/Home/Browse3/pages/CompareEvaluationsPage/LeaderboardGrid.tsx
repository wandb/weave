import {Box} from '@mui/material';
import {
  GridColDef,
  GridPaginationModel,
  GridRenderCellParams,
} from '@mui/x-data-grid-pro';
import React, {useCallback, useMemo, useState} from 'react';

import {StyledDataGrid} from '../../StyledDataGrid';
import {PaginationButtons} from '../CallsPage/CallsTableButtons';

interface LeaderboardGridProps {
  data: {
    models: string[];
    metrics: string[];
    scores: {[key: string]: {[key: string]: number}};
  };
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
    data.metrics.forEach(metric => {
      const scores = data.models.map(model => data.scores[model][metric]);
      ranges[metric] = {
        min: Math.min(...scores),
        max: Math.max(...scores),
      };
    });
    return ranges;
  }, [data]);

  const getColorForScore = useCallback(
    (metric: string, score: number) => {
      const {min, max} = metricRanges[metric];
      const normalizedScore = (score - min) / (max - min);
      return `hsl(${120 * normalizedScore}, 70%, 85%)`;
    },
    [metricRanges]
  );

  const columns: GridColDef[] = useMemo(
    () => [
      {field: 'model', headerName: 'Model', width: 200, flex: 1},
      ...data.metrics.map(metric => ({
        field: metric,
        headerName: metric,
        width: 130,
        flex: 1,
        renderCell: (params: GridRenderCellParams) => (
          <div
            style={{
              width: '100%',
              height: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              backgroundColor: getColorForScore(metric, params.value as number),
            }}
            onClick={() =>
              onCellClick(
                params.row.model,
                params.field as string,
                params.value as number
              )
            }>
            {`${(params.value as number).toFixed(2)}%`}
          </div>
        ),
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
        pagination
        paginationModel={paginationModel}
        onPaginationModelChange={setPaginationModel}
        pageSizeOptions={[25]}
        disableColumnMenu
        disableRowSelectionOnClick
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
          pagination: PaginationButtons,
        }}
      />
    </Box>
  );
};
