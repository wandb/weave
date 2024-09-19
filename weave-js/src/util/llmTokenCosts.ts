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
