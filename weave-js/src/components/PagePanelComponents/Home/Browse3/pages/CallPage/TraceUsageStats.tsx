import {Divider} from '@mui/material';
import Box from '@mui/material/Box';
import {Pill} from '@wandb/weave/components/Tag';
import {formatNumber} from '@wandb/weave/core/util/number';
import React, {ReactNode} from 'react';

import {MOON_600} from '../../../../../../common/css/color.styles';
import {IconName} from '../../../../../Icon';
import {Tooltip} from '../../../../../Tooltip';

export const FORMAT_NUMBER_NO_DECIMALS = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
  useGrouping: true,
});

// Number formatting function that formats numbers in the thousands and millions with 3 sigfigs
export const formatTokenCount = (num: number): string => {
  if (num < 10000) {
    return FORMAT_NUMBER_NO_DECIMALS.format(num);
  } else if (num >= 10000 && num < 1000000) {
    // Format numbers in the thousands
    const thousands = (num / 1000).toFixed(1);
    return parseFloat(thousands).toString() + 'k';
  }
  // Format numbers in the millions
  const millions = (num / 1000000).toFixed(2);
  return parseFloat(millions).toString() + 'm';
};

export const formatTokenCost = (cost: number): string => {
  if (cost === 0) {
    return '$0.00';
  } else if (cost < 0.01) {
    return '$<0.01';
  }
  return `$${cost.toFixed(2)}`;
};

export type UsageData = {
  requests: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  input_tokens?: number;
  output_tokens?: number;
};

export type CostData = {
  requests: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;

  prompt_tokens_cost?: number;
  completion_tokens_cost?: number;
  prompt_token_cost?: number;
  completion_token_cost?: number;

  effective_date?: string;

  provider_id?: string;
  pricing_level?: string;
  pricing_level_id?: string;

  input_tokens?: number;
  output_tokens?: number;
};

type CostDataKeys = keyof CostData;
const isCostDataKey = (key: string): key is CostDataKeys => {
  const costDataKeys: CostDataKeys[] = [
    'requests',
    'prompt_tokens',
    'completion_tokens',
    'total_tokens',
    'input_tokens',
    'output_tokens',
    'prompt_tokens_cost',
    'completion_tokens_cost',
    'prompt_token_cost',
    'completion_token_cost',
  ];
  return costDataKeys.includes(key as CostDataKeys);
};

export const TraceUsageStats = ({
  costData,
  latency_s,
}: {
  costData: {[key: string]: CostData};
  latency_s: number;
}) => {
  const {cost, tokens, costToolTip, tokenToolTip} =
    getTokensAndCostFromCostData(costData);

  const latency =
    (latency_s < 0.01 ? '<0.01' : formatNumber(latency_s, 'Number')) + 's';

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
      }}>
      <TraceStat icon="recent-clock" label={latency} />
      {costData && (
        <>
          {/* Tokens */}
          <TraceStat
            icon="database-artifacts"
            label={tokens}
            tooltip={tokenToolTip}
          />
          {/* Cost */}
          <TraceStat label={cost} tooltip={costToolTip} />
        </>
      )}
    </Box>
  );
};

export const getCostFromCellParams = (params: {[key: string]: any}) => {
  const costData: {[key: string]: CostData} = {};
  for (const key in params) {
    if (key.startsWith('summary.costs')) {
      const costKeys = key.replace('summary.costs.', '').split('.');
      const costKey = costKeys.pop() || '';
      if (isCostDataKey(costKey)) {
        const model = costKeys.join('.');
        if (!costData[model]) {
          costData[model] = {
            requests: 0,
            prompt_tokens: 0,
            completion_tokens: 0,
            total_tokens: 0,
            prompt_tokens_cost: 0,
            completion_tokens_cost: 0,
            prompt_token_cost: 0,
            completion_token_cost: 0,
          };
        }
        costData[model][costKey] = params[key];
      }
    }
  }
  return costData;
};

// This needs to updated eventually, to either include more possible keys or to be more dynamic
// accounts for openai and anthropic usage objects (prompt_tokens, input_tokens)
export const getInputTokens = (cost: CostData) => {
  return cost.input_tokens ?? cost.prompt_tokens ?? 0;
};

export const getOutputTokens = (cost: CostData) => {
  return cost.output_tokens ?? cost.completion_tokens ?? 0;
};

export const getTokensAndCostFromCostData = (cost: {
  [key: string]: CostData;
}) => {
  const metrics: {
    inputs: {
      cost: Record<string, number>;
      tokens: Record<string, number>;
    };
    outputs: {
      cost: Record<string, number>;
      tokens: Record<string, number>;
    };
  } = {
    inputs: {
      cost: {
        total: 0,
      },
      tokens: {total: 0},
    },
    outputs: {
      cost: {total: 0},
      tokens: {total: 0},
    },
  };
  if (cost) {
    for (const model of Object.keys(cost)) {
      const inputTokens = getInputTokens(cost[model]);
      const outputTokens = getOutputTokens(cost[model]);
      const inputCost = cost[model].prompt_tokens_cost ?? 0;
      const outputCost = cost[model].completion_tokens_cost ?? 0;

      metrics.inputs.cost[model] = inputCost;
      metrics.inputs.tokens[model] = inputTokens;
      metrics.outputs.cost[model] = outputCost;
      metrics.outputs.tokens[model] = outputTokens;

      metrics.inputs.cost.total += inputCost;
      metrics.inputs.tokens.total += inputTokens;
      metrics.outputs.cost.total += outputCost;
      metrics.outputs.tokens.total += outputTokens;
    }
  }
  const costNum = metrics.inputs.cost.total + metrics.outputs.cost.total;
  const formattedCost = formatTokenCost(costNum);
  const tokensNum = metrics.inputs.tokens.total + metrics.outputs.tokens.total;
  const tokens = formatTokenCount(tokensNum);

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

  const tokenToolTip = (
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

  const costToolTip = (
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
  return {
    costNum,
    cost: formattedCost,
    tokensNum,
    tokens,
    costToolTip,
    tokenToolTip,
  };
};

const TraceStat = ({
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
