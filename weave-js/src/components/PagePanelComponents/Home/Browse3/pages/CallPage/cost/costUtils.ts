import {
  LLMCostSchema,
  LLMUsageSchema,
} from '../../wfReactInterface/traceServerClientTypes';
import {CallSchema} from '../../wfReactInterface/wfDataModelHooksInterface';
import {DEFAULT_COST_DATA, isCostDataKey, isUsageDataKey} from './costTypes';

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

export const FORMAT_NUMBER_NO_DECIMALS = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
  useGrouping: true,
});

// Number formatting function that formats numbers in the thousands and millions with 3 sigfigs
export const formatTokenCount = (num: number): string => {
  if (num < 1000000) {
    return FORMAT_NUMBER_NO_DECIMALS.format(num);
  }
  // Format numbers in the millions
  const millions = (num / 1000000).toFixed(2);
  return parseFloat(millions).toString() + 'm';
};

export const formatTokenCost = (cost: number): string => {
  if (cost < 0.0001) {
    return '<$0.0001';
  }
  return `$${cost.toFixed(4)}`;
};

// TODO(Josiah): this is here because sometimes the cost query is not returning all the ids I believe for unfinished calls,
// to get this cost uptake out, this function can be removed, once that is fixed
export const addCostsToCallResults = (
  callResults: CallSchema[],
  costResults: CallSchema[]
) => {
  const costDict = costResults.reduce((acc, cost) => {
    if (cost.callId) {
      acc[cost.callId] = cost;
    }
    return acc;
  }, {} as Record<string, CallSchema>);

  return callResults.map(call => {
    if (call.callId && costDict[call.callId]) {
      if (!call.traceCall) {
        return call;
      }
      return {
        ...call,
        traceCall: {
          ...call.traceCall,
          summary: {
            ...call.traceCall?.summary,
            weave: {
              ...call.traceCall?.summary?.weave,
              costs: costDict[call.callId].traceCall?.summary?.weave?.costs,
            },
          },
        },
      };
    }
    return call;
  });
};
