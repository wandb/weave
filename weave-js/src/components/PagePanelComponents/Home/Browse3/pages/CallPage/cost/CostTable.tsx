import {Box} from '@mui/material';
import {GridColDef, GridRenderCellParams} from '@mui/x-data-grid-pro';
import React from 'react';

import {StyledDataGrid} from '../../../StyledDataGrid';
import {LLMCostSchema} from '../../wfReactInterface/traceServerClientTypes';
import {FORMAT_NUMBER_NO_DECIMALS, formatTokenCost} from './costUtils';

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
    headerAlign: 'right',
    flex: 2,
    renderCell: renderNumberCell,
  },
  {
    field: 'prompt_tokens',
    headerName: 'Input tokens',
    headerAlign: 'right',
    flex: 3,
    renderCell: renderNumberCell,
  },
  {
    field: 'completion_tokens',
    headerName: 'Output tokens',
    headerAlign: 'right',
    flex: 3,
    renderCell: renderNumberCell,
  },
  {
    field: 'total_tokens',
    headerName: 'Total tokens',
    headerAlign: 'right',
    flex: 3,
    renderCell: renderNumberCell,
  },
  {
    field: 'cost',
    headerName: 'Total Cost',
    headerAlign: 'right',
    flex: 3,
    renderCell: (params: GridRenderCellParams) => (
      <Box sx={{textAlign: 'right', width: '100%'}}>
        {formatTokenCost(params.value)}
      </Box>
    ),
  },
];

const sumCostDataForCostTable = (costs: {[key: string]: LLMCostSchema}) => {
  const costData: any[] = Object.entries(costs ?? {}).map(([k, v]) => {
    const promptTokens = v.input_tokens ?? v.prompt_tokens ?? 0;
    const completionTokens = v.output_tokens ?? v.completion_tokens ?? 0;
    return {
      id: k,
      ...v,
      prompt_tokens: promptTokens,
      completion_tokens: completionTokens,
      total_tokens: promptTokens + completionTokens,
      cost:
        (v.completion_tokens_total_cost ?? 0) +
        (v.prompt_tokens_total_cost ?? 0),
    };
  });

  // if more than one model is used, add a row for the total usage
  if (costData.length > 1) {
    const totalUsage = costData.reduce(
      (acc, curr) => {
        acc.requests += curr.requests;
        acc.prompt_tokens += curr.prompt_tokens;
        acc.completion_tokens += curr.completion_tokens;
        acc.total_tokens += curr.total_tokens;
        acc.cost += curr.cost;
        return acc;
      },
      {
        requests: 0,
        prompt_tokens: 0,
        completion_tokens: 0,
        total_tokens: 0,
        cost: 0,
      }
    );

    costData.push({
      id: 'Total',
      ...totalUsage,
    });
  }

  return costData;
};

export const CostTable = ({costs}: {costs: {[key: string]: LLMCostSchema}}) => {
  const costData = sumCostDataForCostTable(costs);

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
      rows={costData}
      rowHeight={38}
      rowSelection={false}
      keepBorders={true}
    />
  );
};
