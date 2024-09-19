import {Divider} from '@mui/material';
import Box from '@mui/material/Box';
import {MOON_600} from '@wandb/weave/common/css/color.styles';
import {IconName} from '@wandb/weave/components/Icon';
import {Pill} from '@wandb/weave/components/Tag';
import {Tooltip} from '@wandb/weave/components/Tooltip';
import React, {ReactNode} from 'react';

import {LLMCostSchema} from '../../wfReactInterface/traceServerClientTypes';
import {CostTotals, TokenTotals} from './costTypes';
import {
  FORMAT_NUMBER_NO_DECIMALS,
  formatTokenCost,
  getCostFromCellParams,
} from './costUtils';

const tooltipRowStyles = {
  display: 'flex',
  justifyContent: 'space-between',
  alignContent: 'center',
  gap: '16px',
};

const tooltipDivider = (
  <Divider
    sx={{
      borderColor: MOON_600,
      marginTop: '8px',
      marginBottom: '7px',
    }}
  />
);

export const TokenToolTip = (metrics: TokenTotals) => (
  <Box>
    {Object.keys(metrics.inputs.tokens).map(model => (
      <Box key={model + 'input'} sx={tooltipRowStyles}>
        <span>{model === 'total' ? 'Input tokens' : model}: </span>
        <span>
          {FORMAT_NUMBER_NO_DECIMALS.format(metrics.inputs.tokens[model])}
        </span>
      </Box>
    ))}
    {tooltipDivider}
    {Object.keys(metrics.outputs.tokens).map(model => (
      <Box key={model + 'output'} sx={tooltipRowStyles}>
        <span>{model === 'total' ? 'Output tokens' : model}: </span>
        <span>
          {FORMAT_NUMBER_NO_DECIMALS.format(metrics.outputs.tokens[model])}
        </span>
      </Box>
    ))}
  </Box>
);

// TODO: change this to use CostTotals
export const CostToolTip = (metrics: CostTotals) => (
  <Box>
    <span style={{fontWeight: 600}}>Estimated Cost</span>
    {Object.keys(metrics.inputs.cost).map(model => (
      <Box key={model + 'input'} sx={tooltipRowStyles}>
        <span>{model === 'total' ? 'Input cost' : model}: </span>
        <span>{formatTokenCost(metrics.inputs.cost[model])}</span>
      </Box>
    ))}
    {tooltipDivider}
    {Object.keys(metrics.outputs.cost).map(model => (
      <Box key={model + 'output'} sx={tooltipRowStyles}>
        <span>{model === 'total' ? 'Output cost' : model}: </span>
        <span>{formatTokenCost(metrics.outputs.cost[model])}</span>
      </Box>
    ))}
  </Box>
);

export const getCostFromCostData = (cost: {[key: string]: LLMCostSchema}) => {
  const metrics: CostTotals = {
    inputs: {
      cost: {
        total: 0,
      },
    },
    outputs: {
      cost: {total: 0},
    },
  };
  if (cost) {
    // Sums up the total cost and tokens for all models
    for (const model of Object.keys(cost)) {
      const inputCost = cost[model].prompt_tokens_total_cost ?? 0;
      const outputCost = cost[model].completion_tokens_total_cost ?? 0;

      metrics.inputs.cost[model] = inputCost;
      metrics.outputs.cost[model] = outputCost;

      metrics.inputs.cost.total += inputCost;
      metrics.outputs.cost.total += outputCost;
    }
  }
  const costNum = metrics.inputs.cost.total + metrics.outputs.cost.total;
  const formattedCost = formatTokenCost(costNum);

  const costToolTip = <CostToolTip {...metrics} />;
  return {
    costNum,
    cost: formattedCost,
    costToolTip,
  };
};

export const getCostsFromCellParams = (params: {[key: string]: any}) => {
  const costData = getCostFromCellParams(params);
  return getCostFromCostData(costData);
};

export const TraceStat = ({
  icon,
  label,
  tooltip,
}: {
  icon?: IconName;
  label: string;
  tooltip?: ReactNode;
}) => {
  const trigger = (
    <div>
      <Pill
        icon={icon}
        label={label}
        color="moon"
        className="bg-transparent text-moon-500 dark:bg-transparent dark:text-moon-500"
      />
    </div>
  );

  if (!tooltip) {
    return trigger;
  }

  return <Tooltip trigger={trigger} content={tooltip} />;
};
