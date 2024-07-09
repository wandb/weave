export type Model = keyof typeof LLM_TOKEN_COSTS;
export const isValidLLMModel = (model: string): model is Model => {
  return Object.keys(LLM_TOKEN_COSTS).includes(model);
};

export const LLM_TOKEN_COSTS = {
  // Default pricing if model has no specific pricing
  default: {
    input: 0.005,
    output: 0.015,
  },

  // OPENAI pricing for 1k LLM tokens taken on June 4, 2024
  // https://openai.com/api/pricing/
  'gpt-4o': {
    input: 0.005,
    output: 0.015,
  },
  'gpt-4o-2024-05-13': {
    input: 0.005,
    output: 0.015,
  },
  'gpt-4-turbo': {
    input: 0.01,
    output: 0.03,
  },
  'gpt-4-turbo-2024-04-09': {
    input: 0.01,
    output: 0.03,
  },
  'gpt-4': {
    input: 0.03,
    output: 0.06,
  },
  'gpt-4-32k': {
    input: 0.06,
    output: 0.12,
  },
  'gpt-4-0125-preview': {
    input: 0.01,
    output: 0.03,
  },
  'gpt-4-1106-preview': {
    input: 0.01,
    output: 0.03,
  },
  'gpt-4-vision-preview': {
    input: 0.01,
    output: 0.03,
  },
  'gpt-3.5-turbo-1106': {
    input: 0.001,
    output: 0.002,
  },
  'gpt-3.5-turbo-0613': {
    input: 0.0015,
    output: 0.002,
  },
  'gpt-3.5-turbo-16k-0613': {
    input: 0.003,
    output: 0.004,
  },
  'gpt-3.5-turbo-0301': {
    input: 0.0015,
    output: 0.002,
  },
  'gpt-3.5-turbo-0125': {
    input: 0.0005,
    output: 0.0015,
  },
  'gpt-3.5-turbo-instruct': {
    input: 0.0015,
    output: 0.002,
  },
  'davinci-002': {
    input: 0.002,
    output: 0.002,
  },
  'babbage-002': {
    input: 0.0004,
    output: 0.0004,
  },

  // Anthropic pricing for 1k LLM tokens taken on June 4, 2024
  // https://docs.anthropic.com/en/docs/models-overview
  'claude-3-opus-20240229': {
    input: 0.015,
    output: 0.075,
  },
  'claude-3-sonnet-20240229': {
    input: 0.003,
    output: 0.015,
  },
  'claude-3-haiku-20240307': {
    input: 0.00025,
    output: 0.00125,
  },
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
