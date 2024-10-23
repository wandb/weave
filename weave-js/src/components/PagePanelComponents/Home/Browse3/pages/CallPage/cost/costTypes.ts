import {
  LLMCostSchema,
  LLMUsageSchema,
} from '../../wfReactInterface/traceServerClientTypes';

export const DEFAULT_COST_DATA: LLMCostSchema = {
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

type CostDataKey = keyof LLMCostSchema;
export const isCostDataKey = (key: any): key is CostDataKey => {
  if (typeof key !== 'string') {
    return false;
  }

  const costDataKeys: CostDataKey[] = Object.keys(DEFAULT_COST_DATA);
  return costDataKeys.includes(key as CostDataKey);
};

type UsageDataKeys = keyof LLMUsageSchema;
export const isUsageDataKey = (key: any): key is UsageDataKeys => {
  if (typeof key !== 'string') {
    return false;
  }
  const usageDataKeys: UsageDataKeys[] = [
    'requests',
    'prompt_tokens',
    'completion_tokens',
    'total_tokens',
    'input_tokens',
    'output_tokens',
  ];
  return usageDataKeys.includes(key as UsageDataKeys);
};

export type CostTotals = {
  inputs: {
    cost: Record<string, number>;
  };
  outputs: {
    cost: Record<string, number>;
  };
};

export type TokenTotals = {
  inputs: {
    tokens: Record<string, number>;
  };
  outputs: {
    tokens: Record<string, number>;
  };
};
