import levenshtein from 'js-levenshtein';

// Type definition for model configuration
export interface LLMModelConfig {
  label?: string;
  provider: string;
  max_tokens: number;
  supports_function_calling: boolean;
}

// This is a mapping of LLM names to their max token limits.
// Directly from the pycache model_providers.json in trace_server.
// Some were removed because they are not supported when Josiah tried on Oct 30, 2024.
export const LLM_MAX_TOKENS: Record<string, LLMModelConfig> = {
  // CoreWeave hosted models
  'cw_meta-llama_Llama-3.1-8B-Instruct': {
    label: 'Llama 3.1 8B',
    provider: 'coreweave',
    max_tokens: 1000,
    supports_function_calling: false,
  },
  'cw_deepseek-ai_DeepSeek-R1-0528': {
    label: 'DeepSeek R1-0528',
    provider: 'coreweave',
    max_tokens: 1000,
    supports_function_calling: false,
  },
  'cw_deepseek-ai_DeepSeek-V3-0324': {
    label: 'DeepSeek V3-0324',
    provider: 'coreweave',
    max_tokens: 1000,
    supports_function_calling: false,
  },
  'cw_meta-llama_Llama-3.3-70B-Instruct': {
    label: 'Llama 3.3 70B',
    provider: 'coreweave',
    max_tokens: 1000,
    supports_function_calling: false,
  },
  'cw_meta-llama_Llama-4-Scout-17B-16E-Instruct': {
    label: 'Llama 4 Scout',
    provider: 'coreweave',
    max_tokens: 1000,
    supports_function_calling: false,
  },
  'cw_microsoft_Phi-4-mini-instruct': {
    label: 'Phi 4 Mini',
    provider: 'coreweave',
    max_tokens: 1000,
    supports_function_calling: false,
  },
  'cw_moonshotai_Kimi-K2-Instruct': {
    label: 'Kimi K2',
    provider: 'coreweave',
    max_tokens: 1000,
    supports_function_calling: false,
  },
  // End hosted models
  'gpt-4.1-mini-2025-04-14': {
    provider: 'openai',
    max_tokens: 32768,
    supports_function_calling: true,
  },
  'gpt-4.1-mini': {
    provider: 'openai',
    max_tokens: 32768,
    supports_function_calling: true,
  },
  'gpt-4.1-2025-04-14': {
    provider: 'openai',
    max_tokens: 32768,
    supports_function_calling: true,
  },
  'gpt-4.1': {
    provider: 'openai',
    max_tokens: 32768,
    supports_function_calling: true,
  },
  'gpt-4.1-nano-2025-04-14': {
    provider: 'openai',
    max_tokens: 32768,
    supports_function_calling: true,
  },
  'gpt-4.1-nano': {
    provider: 'openai',
    max_tokens: 32768,
    supports_function_calling: true,
  },
  'o4-mini-2025-04-16': {
    provider: 'openai',
    max_tokens: 100000,
    supports_function_calling: true,
  },
  'o4-mini': {
    provider: 'openai',
    max_tokens: 100000,
    supports_function_calling: true,
  },
  'o3-2025-04-16': {
    provider: 'openai',
    max_tokens: 100000,
    supports_function_calling: true,
  },
  o3: {
    provider: 'openai',
    max_tokens: 100000,
    supports_function_calling: true,
  },

  'o3-mini-2025-01-31': {
    provider: 'openai',
    max_tokens: 100000,
    supports_function_calling: true,
  },
  'o3-mini': {
    provider: 'openai',
    max_tokens: 100000,
    supports_function_calling: true,
  },
  'gpt-4.5-preview-2025-02-27': {
    provider: 'openai',
    max_tokens: 16384,
    supports_function_calling: true,
  },
  'gpt-4.5-preview': {
    provider: 'openai',
    max_tokens: 16384,
    supports_function_calling: true,
  },
  'gpt-4o-mini': {
    provider: 'openai',
    max_tokens: 16384,
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
  'gpt-4o-mini-2024-07-18': {
    provider: 'openai',
    max_tokens: 16384,
    supports_function_calling: true,
  },
  'gpt-4o': {
    provider: 'openai',
    max_tokens: 4096,
    supports_function_calling: true,
  },
  'gpt-4o-2024-11-20': {
    provider: 'openai',
    max_tokens: 4096,
    supports_function_calling: true,
  },
  'o1-mini-2024-09-12': {
    provider: 'openai',
    max_tokens: 65536,
    supports_function_calling: true,
  },
  'o1-mini': {
    provider: 'openai',
    max_tokens: 65536,
    supports_function_calling: true,
  },
  'o1-preview-2024-09-12': {
    provider: 'openai',
    max_tokens: 32768,
    supports_function_calling: true,
  },
  'o1-preview': {
    provider: 'openai',
    max_tokens: 32768,
    supports_function_calling: true,
  },
  'o1-2024-12-17': {
    provider: 'openai',
    max_tokens: 100000,
    supports_function_calling: true,
  },
  'gpt-4-1106-preview': {
    provider: 'openai',
    max_tokens: 4096,
    supports_function_calling: true,
  },
  'gpt-4-32k-0314': {
    provider: 'openai',
    max_tokens: 4096,
    supports_function_calling: false,
  },
  'gpt-4-turbo-2024-04-09': {
    provider: 'openai',
    max_tokens: 4096,
    supports_function_calling: true,
  },
  'gpt-4-turbo-preview': {
    provider: 'openai',
    max_tokens: 4096,
    supports_function_calling: true,
  },
  'gpt-4-turbo': {
    provider: 'openai',
    max_tokens: 4096,
    supports_function_calling: true,
  },
  'gpt-4': {
    provider: 'openai',
    max_tokens: 4096,
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

  // Anthropic models
  'claude-opus-4-20250514': {
    provider: 'anthropic',
    max_tokens: 32000,
    supports_function_calling: true,
  },
  'claude-sonnet-4-20250514': {
    provider: 'anthropic',
    max_tokens: 64000,
    supports_function_calling: true,
  },
  'claude-3-7-sonnet-20250219': {
    provider: 'anthropic',
    max_tokens: 8192,
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

  // Azure models
  'azure/gpt-4.1': {
    provider: 'azure',
    max_tokens: 32768,
    supports_function_calling: true,
  },
  'azure/gpt-4.1-2025-04-14': {
    provider: 'azure',
    max_tokens: 32768,
    supports_function_calling: true,
  },
  'azure/gpt-4.1-mini': {
    provider: 'azure',
    max_tokens: 32768,
    supports_function_calling: true,
  },
  'azure/gpt-4.1-mini-2025-04-14': {
    provider: 'azure',
    max_tokens: 32768,
    supports_function_calling: true,
  },
  'azure/gpt-4.1-nano': {
    provider: 'azure',
    max_tokens: 32768,
    supports_function_calling: true,
  },
  'azure/gpt-4.1-nano-2025-04-14': {
    provider: 'azure',
    max_tokens: 32768,
    supports_function_calling: true,
  },
  'azure/o3': {
    provider: 'azure',
    max_tokens: 100000,
    supports_function_calling: true,
  },
  'azure/o3-2025-04-16': {
    provider: 'azure',
    max_tokens: 100000,
    supports_function_calling: true,
  },
  'azure/o3-mini': {
    provider: 'azure',
    max_tokens: 100000,
    supports_function_calling: true,
  },
  'azure/o3-mini-2025-01-31': {
    provider: 'azure',
    max_tokens: 100000,
    supports_function_calling: true,
  },
  'azure/o4-mini': {
    provider: 'azure',
    max_tokens: 100000,
    supports_function_calling: true,
  },
  'azure/o4-mini-2025-04-16': {
    provider: 'azure',
    max_tokens: 100000,
    supports_function_calling: true,
  },
  'azure/o1-pro': {
    provider: 'azure',
    max_tokens: 100000,
    supports_function_calling: true,
  },
  'azure/o1-pro-2025-03-19': {
    provider: 'azure',
    max_tokens: 100000,
    supports_function_calling: true,
  },
  'azure/o1-2024-12-17': {
    provider: 'azure',
    max_tokens: 100000,
    supports_function_calling: true,
  },
  'azure/o1-mini': {
    provider: 'azure',
    max_tokens: 65536,
    supports_function_calling: true,
  },
  'azure/o1-mini-2024-09-12': {
    provider: 'azure',
    max_tokens: 65536,
    supports_function_calling: true,
  },
  'azure/o1': {
    provider: 'azure',
    max_tokens: 100000,
    supports_function_calling: true,
  },
  'azure/o1-preview': {
    provider: 'azure',
    max_tokens: 32768,
    supports_function_calling: true,
  },
  'azure/o1-preview-2024-09-12': {
    provider: 'azure',
    max_tokens: 32768,
    supports_function_calling: true,
  },
  'azure/gpt-4o': {
    provider: 'azure',
    max_tokens: 16384,
    supports_function_calling: true,
  },
  'azure/gpt-4o-2024-08-06': {
    provider: 'azure',
    max_tokens: 16384,
    supports_function_calling: true,
  },
  'azure/gpt-4o-2024-11-20': {
    provider: 'azure',
    max_tokens: 16384,
    supports_function_calling: true,
  },
  'azure/gpt-4o-2024-05-13': {
    provider: 'azure',
    max_tokens: 4096,
    supports_function_calling: true,
  },
  'azure/gpt-4o-mini': {
    provider: 'azure',
    max_tokens: 16384,
    supports_function_calling: true,
  },
  'azure/gpt-4o-mini-2024-07-18': {
    provider: 'azure',
    max_tokens: 16384,
    supports_function_calling: true,
  },

  // Gemini models
  'gemini/gemini-2.5-pro-preview-03-25': {
    provider: 'gemini',
    max_tokens: 65536,
    supports_function_calling: true,
  },
  'gemini/gemini-2.0-pro-exp-02-05': {
    provider: 'gemini',
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'gemini/gemini-2.0-flash-exp': {
    provider: 'gemini',
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'gemini/gemini-2.0-flash-001': {
    provider: 'gemini',
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'gemini/gemini-2.0-flash-thinking-exp': {
    provider: 'gemini',
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'gemini/gemini-2.0-flash-thinking-exp-01-21': {
    provider: 'gemini',
    max_tokens: 65536,
    supports_function_calling: false,
  },
  'gemini/gemini-2.0-flash': {
    provider: 'gemini',
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'gemini/gemini-2.0-flash-lite': {
    provider: 'gemini',
    max_tokens: 1048576,
    supports_function_calling: true,
  },
  'gemini/gemini-2.0-flash-lite-preview-02-05': {
    provider: 'gemini',
    max_tokens: 8192,
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
  'gemini/gemini-1.5-flash-latest': {
    provider: 'gemini',
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'gemini/gemini-1.5-flash': {
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
  'gemini/gemini-1.5-pro-latest': {
    provider: 'gemini',
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'gemini/gemini-1.5-pro': {
    provider: 'gemini',
    max_tokens: 8192,
    supports_function_calling: true,
  },

  // Groq models
  'groq/deepseek-r1-distill-llama-70b': {
    provider: 'groq',
    max_tokens: 131072,
    supports_function_calling: false,
  },
  'groq/llama-3.3-70b-versatile': {
    provider: 'groq',
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'groq/llama-3.3-70b-specdec': {
    provider: 'groq',
    max_tokens: 8192,
    supports_function_calling: false,
  },
  'groq/llama-3.2-1b-preview': {
    provider: 'groq',
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'groq/llama-3.2-3b-preview': {
    provider: 'groq',
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'groq/llama-3.2-11b-vision-preview': {
    provider: 'groq',
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'groq/llama-3.2-90b-vision-preview': {
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
  'groq/gemma2-9b-it': {
    provider: 'groq',
    max_tokens: 8192,
    supports_function_calling: true,
  },

  // Bedrock models
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
  'amazon.nova-micro-v1:0': {
    provider: 'bedrock',
    max_tokens: 4096,
    supports_function_calling: true,
  },
  'amazon.nova-lite-v1:0': {
    provider: 'bedrock',
    max_tokens: 4096,
    supports_function_calling: true,
  },
  'amazon.nova-pro-v1:0': {
    provider: 'bedrock',
    max_tokens: 4096,
    supports_function_calling: true,
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

  // xAI models
  'xai/grok-4': {
    provider: 'xai',
    max_tokens: 256000,
    supports_function_calling: true,
  },
  'xai/grok-4-0709': {
    provider: 'xai',
    max_tokens: 256000,
    supports_function_calling: true,
  },
  'xai/grok-4-latest': {
    provider: 'xai',
    max_tokens: 256000,
    supports_function_calling: true,
  },
  'xai/grok-3-beta': {
    provider: 'xai',
    max_tokens: 131072,
    supports_function_calling: true,
  },
  'xai/grok-3-fast-beta': {
    provider: 'xai',
    max_tokens: 131072,
    supports_function_calling: true,
  },
  'xai/grok-3-fast-latest': {
    provider: 'xai',
    max_tokens: 131072,
    supports_function_calling: true,
  },
  'xai/grok-3-mini-beta': {
    provider: 'xai',
    max_tokens: 131072,
    supports_function_calling: true,
  },
  'xai/grok-3-mini-fast-beta': {
    provider: 'xai',
    max_tokens: 131072,
    supports_function_calling: true,
  },
  'xai/grok-3-mini-fast-latest': {
    provider: 'xai',
    max_tokens: 131072,
    supports_function_calling: true,
  },
  'xai/grok-beta': {
    provider: 'xai',
    max_tokens: 131072,
    supports_function_calling: true,
  },
  'xai/grok-2-1212': {
    provider: 'xai',
    max_tokens: 131072,
    supports_function_calling: true,
  },
  'xai/grok-2': {
    provider: 'xai',
    max_tokens: 131072,
    supports_function_calling: true,
  },
  'xai/grok-2-latest': {
    provider: 'xai',
    max_tokens: 131072,
    supports_function_calling: true,
  },

  // DeepSeek models
  'deepseek/deepseek-reasoner': {
    provider: 'deepseek',
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'deepseek/deepseek-chat': {
    provider: 'deepseek',
    max_tokens: 8192,
    supports_function_calling: true,
  },

  // Mistral models
  'mistral/mistral-large-latest': {
    provider: 'mistral',
    max_tokens: 128000,
    supports_function_calling: true,
  },
  'mistral/mistral-medium-latest': {
    provider: 'mistral',
    max_tokens: 8192,
    supports_function_calling: true,
  },
  'mistral/mistral-small-latest': {
    provider: 'mistral',
    max_tokens: 8191,
    supports_function_calling: true,
  },
  'mistral/codestral-mamba-latest': {
    provider: 'mistral',
    max_tokens: 256000,
    supports_function_calling: true,
  },
  'mistral/pixtral-large-latest': {
    provider: 'mistral',
    max_tokens: 128000,
    supports_function_calling: true,
  },
  'mistral/open-mistral-nemo': {
    provider: 'mistral',
    max_tokens: 128000,
    supports_function_calling: true,
  },
};

export const DEFAULT_LLM_MODEL: LLMMaxTokensKey =
  'cw_meta-llama_Llama-3.1-8B-Instruct';

export type LLMMaxTokensKey = keyof typeof LLM_MAX_TOKENS;

export const LLM_MAX_TOKENS_KEYS: LLMMaxTokensKey[] = Object.keys(
  LLM_MAX_TOKENS
) as LLMMaxTokensKey[];

export const LLM_PROVIDER_SECRETS: Record<string, string[]> = {
  coreweave: [],
  openai: ['OPENAI_API_KEY'],
  anthropic: ['ANTHROPIC_API_KEY'],
  gemini: ['GEMINI_API_KEY'],
  xai: ['XAI_API_KEY'],
  bedrock: ['AWS_SECRET_ACCESS_KEY', 'AWS_REGION_NAME', 'AWS_ACCESS_KEY_ID'],
  azure: ['AZURE_API_BASE', 'AZURE_API_VERSION', 'AZURE_API_KEY'],
  groq: ['GROQ_API_KEY'],
  deepseek: ['DEEPSEEK_API_KEY'],
  mistral: ['MISTRAL_API_KEY'],
};

export const LLM_PROVIDERS = Object.keys(LLM_PROVIDER_SECRETS) as Array<
  keyof typeof LLM_PROVIDER_SECRETS
>;

export const LLM_PROVIDER_LABELS: Record<
  (typeof LLM_PROVIDERS)[number],
  string
> = {
  coreweave: 'W&B Inference',
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  azure: 'Azure',
  gemini: 'Google Gemini',
  groq: 'Groq',
  bedrock: 'AWS Bedrock',
  xai: 'xAI',
  deepseek: 'DeepSeek',
  mistral: 'Mistral',
};

// Example usage:
// findMaxTokensByModelName('gpt-4') // returns 4096
// findMaxTokensByModelName('gpt-4-turbo') // returns 4096
// findMaxTokensByModelName('claude-3') // returns closest Claude-3 model's max_tokens
// findMaxTokensByModelName('completely-unknown-model') // returns 4096
export const findMaxTokensByModelName = (modelName: string): number => {
  // Default to a reasonable max_tokens value if no close match is found
  const DEFAULT_MAX_TOKENS = 4096;

  // If the model name is an exact match, return its max_tokens
  if (modelName in LLM_MAX_TOKENS) {
    return LLM_MAX_TOKENS[modelName as LLMMaxTokensKey].max_tokens;
  }

  // Find the closest match using Levenshtein distance
  let closestMatch = '';
  let minDistance = Infinity;

  Object.keys(LLM_MAX_TOKENS).forEach(key => {
    const distance = levenshtein(modelName.toLowerCase(), key.toLowerCase());

    // Update closest match if this distance is smaller
    if (distance < minDistance) {
      minDistance = distance;
      closestMatch = key;
    }
  });

  // If we found a reasonably close match (distance less than half the length of the model name)
  if (minDistance < modelName.length / 2) {
    return LLM_MAX_TOKENS[closestMatch as LLMMaxTokensKey].max_tokens;
  }

  // Return default if no close match found
  return DEFAULT_MAX_TOKENS;
};
