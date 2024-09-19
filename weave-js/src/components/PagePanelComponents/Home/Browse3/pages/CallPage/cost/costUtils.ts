import {
  LLMCostSchema,
  LLMUsageSchema,
} from '../../wfReactInterface/traceServerClientTypes';
import {DEFAULT_COST_DATA, isCostDataKey} from './costTypes';

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

// This needs to updated eventually, to either include more possible keys or to be more dynamic
// accounts for openai and anthropic usage objects (prompt_tokens, input_tokens)
export const getUsageInputTokens = (usage: LLMUsageSchema) => {
  return usage.input_tokens ?? usage.prompt_tokens ?? 0;
};
export const getUsageOutputTokens = (usage: LLMUsageSchema) => {
  return usage.output_tokens ?? usage.completion_tokens ?? 0;
};
