import {formatTokenCost} from '@wandb/weave/util/llmTokenCosts';
import React from 'react';

import {LLMCostSchema} from '../wfReactInterface/traceServerClientTypes';
import {CostToolTip, TokenAndCostMetrics} from './TraceUsageStats';

const DEFAULT_COST_DATA: LLMCostSchema = {
  requests: 0,
  prompt_tokens: 0,
  completion_tokens: 0,
  total_tokens: 0,
  prompt_tokens_total_cost: 0,
  completion_tokens_total_cost: 0,
  prompt_token_cost: 0,
  completion_token_cost: 0,
  input_tokens: 0,
  output_tokens: 0,
};

const COST_PARAM_PREFIX = 'summary.weave.costs.';

type CostDataKey = keyof LLMCostSchema;
const isCostDataKey = (key: any): key is CostDataKey => {
  if (typeof key !== 'string') {
    return false;
  }

  const costDataKeys: CostDataKey[] = Object.keys(DEFAULT_COST_DATA);
  return costDataKeys.includes(key as CostDataKey);
};

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

export const getCostFromCostData = (cost: {[key: string]: LLMCostSchema}) => {
  const metrics: TokenAndCostMetrics = {
    inputs: {
      cost: {
        total: 0,
      },
      tokens: {
        total: 0,
      },
    },
    outputs: {
      cost: {total: 0},
      tokens: {
        total: 0,
      },
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
