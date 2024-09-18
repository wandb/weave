import {Divider} from '@mui/material';
import Box from '@mui/material/Box';
import React from 'react';

import {MOON_600} from '../../../../../../../common/css/color.styles';
import {
  LLMCostSchema,
  LLMUsageSchema,
} from '../../wfReactInterface/traceServerClientTypes';
import {
  CostMetrics,
  DEFAULT_COST_DATA,
  isCostDataKey,
  isUsageDataKey,
  TokenMetrics,
} from './costTypes';

const COST_PARAM_PREFIX = 'summary.weave.costs.';

export const getCostFromCellParams = (params: {[key: string]: any}) => {
  const costData: {[key: string]: LLMCostSchema} = {};
  for (const key in params) {
    if (key.startsWith(COST_PARAM_PREFIX)) {
      const costKeys = key.replace(COST_PARAM_PREFIX, '').split('.');
      const costKey = costKeys.pop() || '';
      if (isCostDataKey(costKey)) {
        const model = costKeys.join('.');
        if (!costData[model]) {
          costData[model] = {...DEFAULT_COST_DATA};
        }
        // this is giving a type error: cant assign any to never
        costData[model][costKey] = params[key];
      }
    }
  }
  return costData;
};

// This needs to updated eventually, to either include more possible keys or to be more dynamic
// accounts for openai and anthropic usage objects (prompt_tokens, input_tokens)
export const getInputTokens = (cost: LLMCostSchema) => {
  return cost.input_tokens ?? cost.prompt_tokens ?? 0;
};

export const getOutputTokens = (cost: LLMCostSchema) => {
  return cost.output_tokens ?? cost.completion_tokens ?? 0;
};

export const getCostFromCostData = (
  cost: {[key: string]: LLMCostSchema} | undefined
) => {
  if (!cost) {
    return {};
  }
  const metrics: CostMetrics = {
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

  const costToolTipContent = <CostToolTipContent {...metrics} />;
  return {
    costNum,
    cost: formattedCost,
    costToolTipContent,
  };
};

export const getCostsFromCellParams = (params: {[key: string]: any}) => {
  const costData = getCostFromCellParams(params);
  return getCostFromCostData(costData);
};

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

export const getUsageFromCellParams = (params: {[key: string]: any}) => {
  const usage: {[key: string]: LLMUsageSchema} = {};
  for (const key in params) {
    if (key.startsWith('summary.usage')) {
      const usageKeys = key.replace('summary.usage.', '').split('.');
      const usageKey = usageKeys.pop() || '';
      if (isUsageDataKey(usageKey)) {
        const model = usageKeys.join('.');
        if (!usage[model]) {
          usage[model] = {
            requests: 0,
            prompt_tokens: 0,
            completion_tokens: 0,
            total_tokens: 0,
          };
        }
        usage[model][usageKey] = params[key];
      }
    }
  }
  return usage;
};

// This needs to updated eventually, to either include more possible keys or to be more dynamic
// accounts for openai and anthropic usage objects (prompt_tokens, input_tokens)
export const getUsageInputTokens = (usage: LLMUsageSchema) => {
  return usage.input_tokens ?? usage.prompt_tokens ?? 0;
};

export const getUsageOutputTokens = (usage: LLMUsageSchema) => {
  return usage.output_tokens ?? usage.completion_tokens ?? 0;
};

export const getTokensFromUsage = (
  usage:
    | {
        [key: string]: LLMUsageSchema;
      }
    | undefined
) => {
  if (!usage) {
    return {};
  }
  const metrics: TokenMetrics = {
    inputs: {
      tokens: {total: 0},
    },
    outputs: {
      tokens: {total: 0},
    },
  };
  if (usage) {
    for (const model of Object.keys(usage)) {
      const inputTokens = getUsageInputTokens(usage[model]);
      const outputTokens = getUsageOutputTokens(usage[model]);

      metrics.inputs.tokens[model] = inputTokens;
      metrics.outputs.tokens[model] = outputTokens;

      metrics.inputs.tokens.total += inputTokens;
      metrics.outputs.tokens.total += outputTokens;
    }
  }
  const tokensNum = metrics.inputs.tokens.total + metrics.outputs.tokens.total;
  const tokens = formatTokenCount(tokensNum);

  const tokenToolTipContent = <TokenToolTipContent {...metrics} />;

  return {tokensNum, tokens, tokenToolTipContent};
};

export const getTokensFromCellParams = (params: {[key: string]: any}) => {
  const usage = getUsageFromCellParams(params);

  const metrics: TokenMetrics = {
    inputs: {
      tokens: {total: 0},
    },
    outputs: {
      tokens: {total: 0},
    },
  };
  if (usage) {
    for (const model of Object.keys(usage)) {
      const inputTokens = getUsageInputTokens(usage[model]);
      const outputTokens = getUsageOutputTokens(usage[model]);

      metrics.inputs.tokens[model] = inputTokens;
      metrics.outputs.tokens[model] = outputTokens;

      metrics.inputs.tokens.total += inputTokens;
      metrics.outputs.tokens.total += outputTokens;
    }
  }
  const tokensNum = metrics.inputs.tokens.total + metrics.outputs.tokens.total;
  const tokens = formatTokenCount(tokensNum);

  const tokenToolTipContent = <TokenToolTipContent {...metrics} />;

  return {tokensNum, tokens, tokenToolTipContent};
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

const tooltipRowStyles = {
  display: 'flex',
  justifyContent: 'space-between',
  alignContent: 'center',
  gap: '16px',
};

export const TokenToolTipContent = (metrics: TokenMetrics) => (
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

export const CostToolTipContent = (metrics: CostMetrics) => (
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
