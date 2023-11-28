import {Box} from '@mui/material';
import {DataGridPro as DataGrid} from '@mui/x-data-grid-pro';
import React, {useMemo} from 'react';

export const LinkTable = <RowType extends {[key: string]: any}>({
  rows,
  handleRowClick,
  columns,
}: {
  rows: RowType[];
  handleRowClick: (row: RowType) => void;
  columns?: any[];
}) => {
  const autoColumns = useMemo(() => {
    const row0 = rows[0];
    if (row0 == null) {
      return [];
    }
    const cols = Object.keys(row0).filter(
      k => k !== 'id' && !k.startsWith('_')
    );
    return row0 == null
      ? []
      : cols.map((key, i) => ({
          field: key,
          headerName: key,
          flex: i === 0 ? 1 : undefined,
        }));
  }, [rows]);
  return (
    <Box
      sx={{
        height: 460,
        width: '100%',
        '& .MuiDataGrid-root': {
          border: 'none',
        },
        '& .MuiDataGrid-row': {
          cursor: 'pointer',
        },
      }}>
      <DataGrid
        density="compact"
        rows={rows}
        columns={[
          ...autoColumns.filter(
            row =>
              !columns ||
              !columns.map(column => column.field).includes(row.field)
          ),
          ...(columns || []),
        ]}
        autoPageSize
        disableRowSelectionOnClick
        onRowClick={params => handleRowClick(params.row as RowType)}
      />
    </Box>
  );
};
