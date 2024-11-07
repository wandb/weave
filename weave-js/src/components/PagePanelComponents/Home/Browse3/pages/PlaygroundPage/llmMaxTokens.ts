// This is a mapping of LLM names to their max token limits.
// Directly from the pycache model_providers.json in trace_server.
// Some were removed because they are not supported when Josiah tried on Oct 30, 2024.
export const LLM_MAX_TOKENS = {
  'gpt-4o-mini': {max_tokens: 16384, supports_function_calling: true},
  'claude-3-5-sonnet-20240620': {
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'claude-3-5-sonnet-20241022': {
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'claude-3-haiku-20240307': {
    max_tokens: 4096,
    supports_function_calling: true,
  },
  'claude-3-opus-20240229': {max_tokens: 4096, supports_function_calling: true},
  'claude-3-sonnet-20240229': {
    max_tokens: 4096,
    supports_function_calling: true,
  },
  'gemini/gemini-1.5-flash-001': {
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'gemini/gemini-1.5-flash-002': {
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'gemini/gemini-1.5-flash-8b-exp-0827': {
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'gemini/gemini-1.5-flash-8b-exp-0924': {
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'gemini/gemini-1.5-flash-exp-0827': {
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'gemini/gemini-1.5-flash-latest': {
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'gemini/gemini-1.5-flash': {
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'gemini/gemini-1.5-pro-001': {
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'gemini/gemini-1.5-pro-002': {
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'gemini/gemini-1.5-pro-exp-0801': {
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'gemini/gemini-1.5-pro-exp-0827': {
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'gemini/gemini-1.5-pro-latest': {
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'gemini/gemini-1.5-pro': {max_tokens: 8192, supports_function_calling: true},
  'gemini/gemini-pro': {max_tokens: 8192, supports_function_calling: true},
  'gpt-3.5-turbo-0125': {max_tokens: 4096, supports_function_calling: true},
  'gpt-3.5-turbo-1106': {max_tokens: 4096, supports_function_calling: true},
  'gpt-3.5-turbo-16k': {max_tokens: 4096, supports_function_calling: false},
  'gpt-3.5-turbo': {max_tokens: 4096, supports_function_calling: true},
  'gpt-4-0125-preview': {max_tokens: 4096, supports_function_calling: true},
  'gpt-4-0314': {max_tokens: 4096, supports_function_calling: false},
  'gpt-4-0613': {max_tokens: 4096, supports_function_calling: true},
  'gpt-4-1106-preview': {max_tokens: 4096, supports_function_calling: true},
  'gpt-4-32k-0314': {max_tokens: 4096, supports_function_calling: false},
  'gpt-4-turbo-2024-04-09': {max_tokens: 4096, supports_function_calling: true},
  'gpt-4-turbo-preview': {max_tokens: 4096, supports_function_calling: true},
  'gpt-4-turbo': {max_tokens: 4096, supports_function_calling: true},
  'gpt-4': {max_tokens: 4096, supports_function_calling: true},
  'gpt-4o-2024-05-13': {max_tokens: 4096, supports_function_calling: true},
  'gpt-4o-2024-08-06': {max_tokens: 16384, supports_function_calling: true},
  'gpt-4o-mini-2024-07-18': {
    max_tokens: 16384,
    supports_function_calling: true,
  },
  'gpt-4o': {max_tokens: 4096, supports_function_calling: true},
  'groq/gemma-7b-it': {max_tokens: 8192, supports_function_calling: true},
  'groq/gemma2-9b-it': {max_tokens: 8192, supports_function_calling: true},
  'groq/llama-3.1-70b-versatile': {
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'groq/llama-3.1-8b-instant': {
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'groq/llama3-70b-8192': {max_tokens: 8192, supports_function_calling: true},
  'groq/llama3-8b-8192': {max_tokens: 8192, supports_function_calling: true},
  'groq/llama3-groq-70b-8192-tool-use-preview': {
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'groq/llama3-groq-8b-8192-tool-use-preview': {
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'groq/mixtral-8x7b-32768': {
    max_tokens: 32768,
    supports_function_calling: true,
  },
  'o1-mini-2024-09-12': {max_tokens: 65536, supports_function_calling: true},
  'o1-mini': {max_tokens: 65536, supports_function_calling: true},
  'o1-preview-2024-09-12': {max_tokens: 32768, supports_function_calling: true},
  'o1-preview': {max_tokens: 32768, supports_function_calling: true},
};

export type LLMMaxTokensKey = keyof typeof LLM_MAX_TOKENS;
