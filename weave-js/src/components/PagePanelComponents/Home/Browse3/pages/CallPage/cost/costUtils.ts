import {
  LLMCostSchema,
  LLMUsageSchema,
} from '../../wfReactInterface/traceServerClientTypes';
import { CallSchema } from '../../wfReactInterface/wfDataModelHooksInterface';
import { DEFAULT_COST_DATA, isCostDataKey, isUsageDataKey } from './costTypes';

const COST_PARAM_PREFIX = 'summary.weave.costs.';
const USAGE_PARAM_PREFIX = 'summary.usage.';

// Define which fields are considered cost-related
const COST_FIELD_PREFIXES = [
  COST_PARAM_PREFIX,
  USAGE_PARAM_PREFIX,
] as const;

// Helper to check if a field is cost-related
const isCostField = (key: string): boolean => {
  return COST_FIELD_PREFIXES.some(prefix => key.startsWith(prefix));
};

// Extract just the cost-related fields from an object
const extractCostFields = (obj: Record<string, any>): Record<string, any> => {
  return Object.entries(obj).reduce((acc, [key, value]) => {
    if (isCostField(key)) {
      acc[key] = value;
    }
    return acc;
  }, {} as Record<string, any>);
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

export const getUsageFromCellParams = (params: {[key: string]: any}) => {
  const usage: {[key: string]: LLMUsageSchema} = {};
  for (const key in params) {
    if (key.startsWith(USAGE_PARAM_PREFIX)) {
      const usageKeys = key.replace(`${USAGE_PARAM_PREFIX}.`, '').split('.');
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

export const addCostsToCallResults = (
  callResults: CallSchema[],
  costResults: CallSchema[]
): CallSchema[] => {
  const costDict = costResults.reduce((acc, costResult) => {
    if (costResult.callId) {
      acc[costResult.callId] = extractCostFields(costResult);
    }
    return acc;
  }, {} as Record<string, Record<string, any>>);

  return callResults.map(call => {
    if (call.callId && costDict[call.callId]) {
      // Merge cost fields into existing call data
      return {
        ...call,
        ...costDict[call.callId]
      };
    }
    return call;
  });
};
