import {Box} from '@mui/material';
import {GridColDef, GridRenderCellParams} from '@mui/x-data-grid-pro';
import {
  FORMAT_NUMBER_NO_DECIMALS,
  formatTokenCost,
} from '@wandb/weave/util/llmTokenCosts';
import React from 'react';

import {StyledDataGrid} from '../../StyledDataGrid';
import {
  LLMCostSchema,
  LLMUsageSchema,
} from '../wfReactInterface/traceServerClientTypes';
import {sumUsageData} from './TraceUsageStats';
import {sumCostData} from './TraceCostStats';

const renderNumberCell = (params: GridRenderCellParams) => (
  <Box sx={{textAlign: 'right', width: '100%'}}>
    {FORMAT_NUMBER_NO_DECIMALS.format(params.value)}
  </Box>
);

const columns: GridColDef[] = [
  {field: 'id', headerName: 'Model', flex: 5},
  {
    field: 'requests',
    headerName: 'Requests',
    flex: 2,
    renderCell: renderNumberCell,
  },
  {
    field: 'prompt_tokens',
    headerName: 'Input tokens',
    flex: 3,
    renderCell: renderNumberCell,
  },
  {
    field: 'completion_tokens',
    headerName: 'Output tokens',
    flex: 3,
    renderCell: renderNumberCell,
  },
  {
    field: 'total_tokens',
    headerName: 'Total tokens',
    flex: 3,
    renderCell: renderNumberCell,
  },
  {
    field: 'cost',
    headerName: 'Total Cost',
    flex: 3,
    renderCell: (params: GridRenderCellParams) => (
      <Box sx={{textAlign: 'right', width: '100%'}}>
        {formatTokenCost(params.value)}
      </Box>
    ),
  },
];

export const CostTable = ({
  costs,
  usage,
}: {
  costs: {[key: string]: LLMCostSchema};
  usage: {[key: string]: LLMUsageSchema};
}) => {
  const costData = sumCostData(costs);
  const usageData = sumUsageData(usage);

  console.log(costData);
  console.log(usageData);

  return (
    <StyledDataGrid
      // For this super small table, we don't need a lot of features.
      disableColumnMenu={true}
      // In this context, we don't need to filter columns.
      disableColumnFilter={true}
      disableMultipleColumnsFiltering={true}
      // There is no need to reorder the 2 columns in this context.
      disableColumnReorder={true}
      // There are only 6 columns, let's not confuse the user.
      disableColumnSelector={true}
      // We don't need to sort multiple columns.
      disableMultipleColumnsSorting={true}
      slots={{
        // removes the sorting icon, since we don't need it.
        columnUnsortedIcon: null,
      }}
      hideFooter
      // Enabled stuff
      // Resizing columns might be helpful to show more data
      disableColumnResize={false}
      // ColumnPinning seems to be required in DataGridPro, else it crashes.
      disableColumnPinning={false}
      columnHeaderHeight={38}
      columns={columns}
      rows={costData || usageData}
      rowHeight={38}
      rowSelection={false}
      keepBorders={true}
    />
  );
};
