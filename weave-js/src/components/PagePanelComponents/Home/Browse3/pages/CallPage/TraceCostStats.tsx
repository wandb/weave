import {
  formatTokenCost,
  formatTokenCount,
} from '@wandb/weave/util/llmTokenCosts';
import React from 'react';

import {LLMCostSchema} from '../wfReactInterface/traceServerClientTypes';
import {
  CostToolTip,
  TokenAndCostMetrics,
  TokenToolTip,
} from './TraceUsageStats';

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

export const getCostFromCellParams = (params: {[key: string]: any}) => {
  const costData: {[key: string]: LLMCostSchema} = {};
  for (const key in params) {
    if (key.startsWith('summary.weave.costs')) {
      const costKeys = key.replace('summary.weave.costs.', '').split('.');
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
  const metrics: TokenAndCostMetrics = {
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

  const costToolTip = <CostToolTip {...metrics} />;
  const tokenToolTip = <TokenToolTip {...metrics} />;
  return {
    costNum,
    cost: formattedCost,
    tokensNum,
    tokens,
    costToolTip,
    tokenToolTip,
  };
};

export const getCostsFromCellParams = (params: {[key: string]: any}) => {
  const costData = getCostFromCellParams(params);
  return getTokensAndCostFromCostData(costData);
};
