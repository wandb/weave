import React from 'react';
import { DataGrid, GridColDef, GridValueGetterParams, GridRenderCellParams } from '@mui/x-data-grid';

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
  const columns: GridColDef[] = [
    { field: 'model', headerName: 'Model', width: 200 },
    ...data.metrics.map(metric => ({
      field: metric,
      headerName: metric,
      width: 130,
    //   valueGetter: ((params: GridValueGetterParams)) => params.row[metric],
      renderCell: (params: GridRenderCellParams) => (
        <div
          style={{
            width: '100%',
            height: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: `hsl(${120 * (params.value as number / 100)}, 70%, 90%)`,
          }}
          onClick={() =>
            onCellClick(
              params.row.model,
              params.field as string,
              params.value as number
            )
          }
        >
          {`${(params.value as number).toFixed(2)}%`}
        </div>
      ),
    })),
  ];

  const rows: RowData[] = data.models.map((model, index) => ({
    id: index,
    model,
    ...data.scores[model],
  }));

  return (
    <DataGrid
      rows={rows}
      columns={columns}
      initialState={{
        pagination: {
          paginationModel: { pageSize: 25, page: 0 },
        },
      }}
      pageSizeOptions={[25, 50, 100]}
      disableRowSelectionOnClick
      sx={{ height: '100%', width: '100%' }}
    />
  );
};
