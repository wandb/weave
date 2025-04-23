import {GridColDef} from '@mui/x-data-grid-pro';
import {MOON_600, OBLIVION} from '@wandb/weave/common/css/color.styles';
import {hexToRGB} from '@wandb/weave/common/css/utils';
import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import React from 'react';

import {StyledDataGrid} from '../../StyledDataGrid';

const HEADER_BACKGROUND = hexToRGB(OBLIVION, 0.02);

interface ProviderTableProps {
  columns: GridColDef[];
  providers: any[];
  loading: boolean;
}

export const ProviderTable: React.FC<ProviderTableProps> = ({
  columns,
  providers,
  loading,
}) => {
  return loading ? (
    <div className="flex h-full min-h-[200px] items-center justify-center">
      <LoadingDots />
    </div>
  ) : (
    <StyledDataGrid
      disableColumnMenu={true}
      disableColumnFilter={true}
      disableMultipleColumnsFiltering={true}
      disableColumnReorder={true}
      disableColumnSelector={true}
      disableMultipleColumnsSorting={true}
      slots={{
        columnUnsortedIcon: null,
      }}
      hideFooter
      disableColumnResize={false}
      disableColumnPinning={false}
      columnHeaderHeight={38}
      columns={columns}
      rows={providers}
      rowHeight={38}
      rowSelection={false}
      keepBorders={true}
      sx={{
        '& .MuiDataGrid-columnHeader': {
          backgroundColor: HEADER_BACKGROUND,
        },
        '& .MuiDataGrid-columnHeaderTitle': {
          color: MOON_600,
          fontWeight: 600,
        },
      }}
    />
  );
};
