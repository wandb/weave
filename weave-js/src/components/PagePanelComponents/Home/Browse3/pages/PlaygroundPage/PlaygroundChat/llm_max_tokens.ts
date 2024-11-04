// This is a mapping of LLM names to their max token limits.
// Directly from the pycache model_providers.json in trace_server.
// Some are commented out because they are not supported when Josiah tried on Oct 30, 2024.
export const llmMaxTokens = {
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

  // These were all in our model_providers.json (but dont work)
  // Leaving them here for now, just in case someone asks why they arent in the list.
  // This seems like a dupe of claude-3-5-sonnet-20241022.
  // 'anthropic/claude-3-5-sonnet-20241022': 8192,

  // 422 Unprocessable Entity
  // 'claude-2.1': 8191,
  // 'claude-2': 8191,
  // 'claude-instant-1.2': 8191,
  // 'claude-instant-1': 8191,

  // error litellm.BadRequestError: OpenAIException - Error code: 400 - {'error': {'message': "[{'type': 'string_type', 'loc': ('body', 'stop', 'str'), 'msg': 'Input should be a valid string', 'input': []}, {'type': 'too_short', 'loc': ('body', 'stop', 'list[str]'), 'msg': 'List should have at least 1 item after validation, not 0', 'input': [], 'ctx': {'field_type': 'List', 'min_length': 1, 'actual_length': 0}}, {'type': 'too_short', 'loc': ('body', 'stop', 'list[list[int]]'), 'msg': 'List should have at least 1 item after validation, not 0', 'input': [], 'ctx': {'field_type': 'List', 'min_length': 1, 'actual_length': 0}}]", 'type': 'invalid_request_error', 'param': None, 'code': None}}
  // 'chatgpt-4o-latest': 4096,
  // 'gpt-4o-audio-preview-2024-10-01': 16384,
  // 'gpt-4o-audio-preview': 16384,

  // error litellm.NotFoundError: OpenAIException - Error code: 404 - {'error': {'message': 'The model `ft:gpt-3.5-turbo-0125` does not exist or you do not have access to it.', 'type': 'invalid_request_error', 'param': None, 'code': 'model_not_found'}}
  // 'ft:gpt-3.5-turbo-0125': 4096,
  // 'ft:gpt-3.5-turbo-0613': 4096,
  // 'ft:gpt-3.5-turbo-1106': 4096,
  // 'ft:gpt-3.5-turbo': 4096,
  // 'ft:gpt-4-0613': 4096,
  // 'ft:gpt-4o-2024-08-06': 16384,
  // 'ft:gpt-4o-mini-2024-07-18': 16384,
  // 'gpt-4-32k-0613': 4096,
  // 'gpt-4-32k': 4096,
  // 'groq/llama-3.1-405b-reasoning': 8192,
  // 'groq/llama2-70b-4096': 4096,

  // error litellm.NotFoundError: OpenAIException - Error code: 404 - {'error': {'message': 'The model `gpt-3.5-turbo-0301` has been deprecated, learn more here: https://platform.openai.com/docs/deprecations', 'type': 'invalid_request_error', 'param': None, 'code': 'model_not_found'}}
  // 'gpt-3.5-turbo-0301': 4096,
  // 'gpt-3.5-turbo-0613': 4096,
  // 'gpt-3.5-turbo-16k-0613': 4096,
  // 'gpt-4-1106-vision-preview': 4096,
  // 'gpt-4-vision-preview': 4096,

  // error litellm.NotFoundError: VertexAIException - {
  //   "error": {
  //     "code": 404,
  //     "message": "models/gemini-gemma-2-27b-it is not found for API version v1beta, or is not supported for generateContent. Call ListModels to see the list of available models and their supported methods.",
  //     "status": "NOT_FOUND"
  //   }
  // }
  // 'gemini/gemini-gemma-2-27b-it': 8192,
  // 'gemini/gemini-gemma-2-9b-it': 8192,

  // error litellm.NotFoundError: VertexAIException - {
  //   "error": {
  //     "code": 404,
  //     "message": "Gemini 1.0 Pro Vision has been deprecated on July 12, 2024. Consider switching to different model, for example gemini-1.5-flash.",
  //     "status": "NOT_FOUND"
  //   }
  // }
  //   'gemini/gemini-pro-vision': 2048,

  // These are 0 tokens, idk why we would want to use them.
  // "text-moderation-007": 0,
  // "text-moderation-latest": 0,
  // "text-moderation-stable": 0
};
