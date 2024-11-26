// This is a mapping of LLM names to their max token limits.
// Directly from the pycache model_providers.json in trace_server.
// Some were removed because they are not supported when Josiah tried on Oct 30, 2024.
// Others were removed because we want users to use models with the dates
export const LLM_MAX_TOKENS = {
  'gpt-4o-mini-2024-07-18': {
    provider: 'openai',
    max_tokens: 16384,
    supports_function_calling: true,
  },
  'gpt-3.5-turbo-0125': {
    provider: 'openai',
    max_tokens: 4096,
    supports_function_calling: true,
  },
  'gpt-3.5-turbo-1106': {
    provider: 'openai',
    max_tokens: 4096,
    supports_function_calling: true,
  },
  'gpt-3.5-turbo-16k': {
    provider: 'openai',
    max_tokens: 4096,
    supports_function_calling: true,
  },
  'gpt-4o-2024-05-13': {
    provider: 'openai',
    max_tokens: 4096,
    supports_function_calling: true,
  },
  'gpt-4o-2024-08-06': {
    provider: 'openai',
    max_tokens: 16384,
    supports_function_calling: true,
  },
  'o1-mini-2024-09-12': {
    provider: 'openai',
    max_tokens: 32768,
    supports_function_calling: true,
  },

  'claude-3-5-sonnet-20240620': {
    provider: 'anthropic',
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'claude-3-5-sonnet-20241022': {
    provider: 'anthropic',
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'claude-3-haiku-20240307': {
    provider: 'anthropic',
    max_tokens: 4096,
    supports_function_calling: true,
  },
  'claude-3-opus-20240229': {
    provider: 'anthropic',
    max_tokens: 4096,
    supports_function_calling: true,
  },
  'claude-3-sonnet-20240229': {
    provider: 'anthropic',
    max_tokens: 4096,
    supports_function_calling: true,
  },

  'gemini/gemini-1.5-flash-001': {
    provider: 'gemini',
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'gemini/gemini-1.5-flash-002': {
    provider: 'gemini',
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'gemini/gemini-1.5-flash-8b-exp-0827': {
    provider: 'gemini',
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'gemini/gemini-1.5-flash-8b-exp-0924': {
    provider: 'gemini',
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'gemini/gemini-1.5-flash-exp-0827': {
    provider: 'gemini',
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'gemini/gemini-1.5-flash-latest': {
    provider: 'gemini',
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'gemini/gemini-1.5-pro-001': {
    provider: 'gemini',
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'gemini/gemini-1.5-pro-002': {
    provider: 'gemini',
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'gemini/gemini-1.5-pro-exp-0801': {
    provider: 'gemini',
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'gemini/gemini-1.5-pro-exp-0827': {
    provider: 'gemini',
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'gemini/gemini-1.5-pro-latest': {
    provider: 'gemini',
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'gemini/gemini-pro': {
    provider: 'gemini',
    max_tokens: 8192,
    supports_function_calling: true,
  },

  'groq/gemma-7b-it': {
    provider: 'groq',
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'groq/gemma2-9b-it': {
    provider: 'groq',
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'groq/llama-3.1-70b-versatile': {
    provider: 'groq',
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'groq/llama-3.1-8b-instant': {
    provider: 'groq',
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'groq/llama3-70b-8192': {
    provider: 'groq',
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'groq/llama3-8b-8192': {
    provider: 'groq',
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'groq/llama3-groq-70b-8192-tool-use-preview': {
    provider: 'groq',
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'groq/llama3-groq-8b-8192-tool-use-preview': {
    provider: 'groq',
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'groq/mixtral-8x7b-32768': {
    provider: 'groq',
    max_tokens: 32768,
    supports_function_calling: true,
  },

  'ai21.j2-mid-v1': {
    provider: 'bedrock',
    max_tokens: 8191,
    supports_function_calling: false,
  },
  'ai21.j2-ultra-v1': {
    provider: 'bedrock',
    max_tokens: 8191,
    supports_function_calling: false,
  },
  'amazon.titan-text-lite-v1': {
    provider: 'bedrock',
    max_tokens: 4000,
    supports_function_calling: false,
  },
  'amazon.titan-text-express-v1': {
    provider: 'bedrock',
    max_tokens: 8000,
    supports_function_calling: false,
  },
  'mistral.mistral-7b-instruct-v0:2': {
    provider: 'bedrock',
    max_tokens: 8191,
    supports_function_calling: false,
  },
  'mistral.mixtral-8x7b-instruct-v0:1': {
    provider: 'bedrock',
    max_tokens: 8191,
    supports_function_calling: false,
  },
  'mistral.mistral-large-2402-v1:0': {
    provider: 'bedrock',
    max_tokens: 8191,
    supports_function_calling: true,
  },
  'mistral.mistral-large-2407-v1:0': {
    provider: 'bedrock',
    max_tokens: 8191,
    supports_function_calling: true,
  },
  'anthropic.claude-3-sonnet-20240229-v1:0': {
    provider: 'bedrock',
    max_tokens: 4096,
    supports_function_calling: true,
  },
  'anthropic.claude-3-5-sonnet-20240620-v1:0': {
    provider: 'bedrock',
    max_tokens: 4096,
    supports_function_calling: true,
  },

  'anthropic.claude-3-haiku-20240307-v1:0': {
    provider: 'bedrock',
    max_tokens: 4096,
    supports_function_calling: true,
  },
  'anthropic.claude-3-opus-20240229-v1:0': {
    provider: 'bedrock',
    max_tokens: 4096,
    supports_function_calling: true,
  },
  'anthropic.claude-v2': {
    provider: 'bedrock',
    max_tokens: 8191,
    supports_function_calling: false,
  },
  'anthropic.claude-v2:1': {
    provider: 'bedrock',
    max_tokens: 8191,
    supports_function_calling: false,
  },
  'anthropic.claude-instant-v1': {
    provider: 'bedrock',
    max_tokens: 8191,
    supports_function_calling: false,
  },
  'cohere.command-text-v14': {
    provider: 'bedrock',
    max_tokens: 4096,
    supports_function_calling: false,
  },
  'cohere.command-light-text-v14': {
    provider: 'bedrock',
    max_tokens: 4096,
    supports_function_calling: false,
  },
  'cohere.command-r-plus-v1:0': {
    provider: 'bedrock',
    max_tokens: 4096,
    supports_function_calling: false,
  },
  'cohere.command-r-v1:0': {
    provider: 'bedrock',
    max_tokens: 4096,
    supports_function_calling: false,
  },
  'meta.llama2-13b-chat-v1': {
    provider: 'bedrock',
    max_tokens: 4096,
    supports_function_calling: false,
  },
  'meta.llama2-70b-chat-v1': {
    provider: 'bedrock',
    max_tokens: 4096,
    supports_function_calling: false,
  },
  'meta.llama3-8b-instruct-v1:0': {
    provider: 'bedrock',
    max_tokens: 2048,
    supports_function_calling: false,
  },
  'meta.llama3-70b-instruct-v1:0': {
    provider: 'bedrock',
    max_tokens: 2048,
    supports_function_calling: false,
  },
  'meta.llama3-1-8b-instruct-v1:0': {
    provider: 'bedrock',
    max_tokens: 2048,
    supports_function_calling: true,
  },
  'meta.llama3-1-70b-instruct-v1:0': {
    provider: 'bedrock',
    max_tokens: 2048,
    supports_function_calling: true,
  },
  'meta.llama3-1-405b-instruct-v1:0': {
    provider: 'bedrock',
    max_tokens: 4096,
    supports_function_calling: true,
  },
};

export type LLMMaxTokensKey = keyof typeof LLM_MAX_TOKENS;

export const LLM_PROVIDERS = [
  'openai',
  'anthropic',
  'gemini',
  'groq',
  'bedrock',
];
export const LLM_PROVIDER_LABELS: Record<
  (typeof LLM_PROVIDERS)[number],
  string
> = {
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  gemini: 'Gemini',
  groq: 'Groq',
  bedrock: 'Bedrock',
};

export const LLM_MAX_TOKENS_KEYS: LLMMaxTokensKey[] = Object.keys(
  LLM_MAX_TOKENS
) as LLMMaxTokensKey[];

// Helper function to calculate string similarity using Levenshtein distance
const getLevenshteinDistance = (str1: string, str2: string): number => {
  const track = Array(str2.length + 1)
    .fill(null)
    .map(() => Array(str1.length + 1).fill(null));

  for (let i = 0; i <= str1.length; i++) {
    track[0][i] = i;
  }
  for (let j = 0; j <= str2.length; j++) {
    track[j][0] = j;
  }

  for (let j = 1; j <= str2.length; j++) {
    for (let i = 1; i <= str1.length; i++) {
      const indicator = str1[i - 1] === str2[j - 1] ? 0 : 1;
      track[j][i] = Math.min(
        track[j][i - 1] + 1, // deletion
        track[j - 1][i] + 1, // insertion
        track[j - 1][i - 1] + indicator // substitution
      );
    }
  }
  return track[str2.length][str1.length];
};

// Main function to find most similar LLM name
export const findMostSimilarLLMName = (
  input: string,
  llmList: LLMMaxTokensKey[]
): string => {
  const normalizedInput = input.toLowerCase().trim();

  // If exact match exists, return it
  if (llmList.includes(normalizedInput as LLMMaxTokensKey)) {
    return normalizedInput;
  }

  let closestMatch = llmList[0];
  let smallestDistance = Infinity;

  llmList.forEach(llmName => {
    const distance = getLevenshteinDistance(
      normalizedInput,
      llmName.toLowerCase()
    );

    if (distance < smallestDistance) {
      smallestDistance = distance;
      closestMatch = llmName;
    }

    if (llmName.includes(normalizedInput)) {
      closestMatch = llmName;
      smallestDistance = 0;
    }
  });

  return closestMatch;
};
