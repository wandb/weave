import {Divider} from '@mui/material';
import Box from '@mui/material/Box';
import {Pill} from '@wandb/weave/components/Tag';
import {formatNumber} from '@wandb/weave/core/util/number';
import {
  FORMAT_NUMBER_NO_DECIMALS,
  formatTokenCost,
  formatTokenCount,
} from '@wandb/weave/util/llmTokenCosts';
import React, {ReactNode} from 'react';

import {MOON_600} from '../../../../../../common/css/color.styles';
import {IconName} from '../../../../../Icon';
import {Tooltip} from '../../../../../Tooltip';
import {LLMCostSchema} from '../wfReactInterface/traceServerClientTypes';

type CostDataKey = keyof LLMCostSchema;
const isCostDataKey = (key: any): key is CostDataKey => {
  if (typeof key !== 'string') {
    return false;
  }

  const costDataKeys: CostDataKey[] = [
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
  return costDataKeys.includes(key as CostDataKey);
};

export const TraceCostStats = ({
  costData,
  latency_s,
}: {
  costData: {[key: string]: LLMCostSchema};
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
  const costData: {[key: string]: LLMCostSchema} = {};
  for (const key in params) {
    if (key.startsWith('summary._weave.costs')) {
      const costKeys = key.replace('summary._weave.costs.', '').split('.');
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
          } as LLMCostSchema;
        }
        // this is giving a type error: cant assign any to never
        (costData[model] as any)[costKey] = params[key];
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

export const getTokensAndCostFromCostData = (cost: {
  [key: string]: LLMCostSchema;
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

export const sumCostData = (costs: {[key: string]: LLMCostSchema}) => {
  const costData: any[] = Object.entries(costs ?? {}).map(([k, v]) => {
    const promptTokens = v.input_tokens ?? v.prompt_tokens ?? 0;
    const completionTokens = v.output_tokens ?? v.completion_tokens ?? 0;
    return {
      id: k,
      ...v,
      prompt_tokens: promptTokens,
      completion_tokens: completionTokens,
      total_tokens: promptTokens + completionTokens,
      cost: (v.completion_tokens_cost ?? 0) + (v.prompt_tokens_cost ?? 0),
    };
  });

  // if more than one model is used, add a row for the total usage
  if (costData.length > 1) {
    const totalUsage = costData.reduce(
      (acc, curr) => {
        const promptTokens = curr.input_tokens ?? curr.prompt_tokens;
        const completionTokens = curr.output_tokens ?? curr.completion_tokens;
        acc.requests += curr.requests;
        acc.prompt_tokens += promptTokens;
        acc.completion_tokens += completionTokens;
        acc.total_tokens += promptTokens + completionTokens;
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

export const getTokensAndCostFromCellParams = (params: {
  [key: string]: any;
}) => {
  const costData = getCostFromCellParams(params);
  return getTokensAndCostFromCostData(costData);
};
