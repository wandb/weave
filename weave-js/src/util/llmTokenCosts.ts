import {LLM_TOKEN_COSTS} from './tokenCosts';

export type Model = keyof typeof LLM_TOKEN_COSTS;
export const isValidLLMModel = (model: string): model is Model => {
  return Object.keys(LLM_TOKEN_COSTS).includes(model);
};

export const getLLMTokenCost = (
  model: string,
  type: 'input' | 'output',
  tokens: number
) => {
  if (tokens === 0) {
    return 0;
  }

  if (isValidLLMModel(model)) {
    return (LLM_TOKEN_COSTS[model][type] * tokens) / 1000;
  }
  return (LLM_TOKEN_COSTS.default[type] * tokens) / 1000;
};

export const getLLMTotalTokenCost = (
  model: string,
  inputTokens: number,
  outputTokens: number
) => {
  if (inputTokens + outputTokens === 0) {
    return 0;
  }

  if (isValidLLMModel(model)) {
    return (
      (LLM_TOKEN_COSTS[model].input * inputTokens +
        LLM_TOKEN_COSTS[model].output * outputTokens) /
      1000
    );
  }
  return (
    (LLM_TOKEN_COSTS.default.input * inputTokens +
      LLM_TOKEN_COSTS.default.output * outputTokens) /
    1000
  );
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
