export enum ChatFormat {
  None = 'None',
  OpenAI = 'OpenAI',
  Gemini = 'Gemini',
  Anthropic = 'Anthropic',
  Mistral = 'Mistral',
}

// Does this call look like a chat formatted object?
export const isCallChat = (call: CallSchema): boolean => {
  return getChatFormat(call) !== ChatFormat.None;
};

export const getChatFormat = (call: CallSchema): ChatFormat => {
  if (!('traceCall' in call) || !call.traceCall) {
    return ChatFormat.None;
  }
  if (isTraceCallChatFormatAnthropic(call.traceCall)) {
    return ChatFormat.Anthropic;
  }
  if (isTraceCallChatFormatMistral(call.traceCall)) {
    return ChatFormat.Mistral;
  }
  if (isTraceCallChatFormatOpenAI(call.traceCall)) {
    return ChatFormat.OpenAI;
  }
  if (isTraceCallChatFormatGemini(call.traceCall)) {
    return ChatFormat.Gemini;
  }
  return ChatFormat.None;
};

export const normalizeChatCompletion = (
  request: ChatRequest,
  completion: any
): ChatCompletion => {
  if (isGeminiCompletionFormat(completion)) {
    // We normalize to the OpenAI format as our standard representation
    // but the Gemini format does not have a direct mapping for some fields.
    // For now we leave empty placeholders for type checking purposes.
    return {
      id: '',
      choices: geminiCandidatesToChoices(completion.candidates),
      created: 0,
      model: request.model,
      system_fingerprint: '',
      usage: {
        prompt_tokens: completion.usage_metadata.prompt_token_count,
        completion_tokens: completion.usage_metadata.candidates_token_count,
        total_tokens: completion.usage_metadata.total_token_count,
      },
    };
  }
  if (isAnthropicCompletionFormat(completion)) {
    return {
      id: completion.id,
      choices: anthropicContentBlocksToChoices(
        completion.content,
        completion.stop_reason
      ),
      created: 0, // Anthropic doesn't provide `created`
      model: completion.model,
      system_fingerprint: '', // Anthropic doesn't provide `system_fingerprint`
      usage: {
        prompt_tokens: completion.usage.input_tokens,
        completion_tokens: completion.usage.output_tokens,
        total_tokens:
          completion.usage.input_tokens + completion.usage.output_tokens,
      },
    };
  }
  if (isMistralCompletionFormat(completion)) {
    if (completion === null) {
      // Handle cases where an SDK error or stream issue results in a null output
      // for a call that is otherwise identified as Mistral.
      return {
        id: request.model + '-' + Date.now(), // Generate a placeholder ID
        choices: [],
        created: Math.floor(Date.now() / 1000),
        model: request.model, // Use model from the request
        system_fingerprint: '',
        usage: {prompt_tokens: 0, completion_tokens: 0, total_tokens: 0},
      };
    }

    const choices: Choice[] = completion.choices.map((choicePart: any) => {
      let message: Message;
      if (choicePart.message) {
        message = choicePart.message as Message;
      } else if (choicePart.delta) {
        message = {
          role: choicePart.delta.role ?? 'assistant',
          content: choicePart.delta.content ?? '',
        };
        if (choicePart.delta.tool_calls) {
          message.tool_calls = choicePart.delta.tool_calls;
        }
      } else {
        message = {role: 'assistant', content: ''};
      }
      return {
        index: choicePart.index,
        message,
        finish_reason: choicePart.finish_reason ?? 'stop',
      };
    });

    return {
      id: completion.id,
      choices,
      created: completion.created,
      model: completion.model,
      system_fingerprint: completion.system_fingerprint ?? '',
      usage: completion.usage
        ? {
            prompt_tokens: completion.usage.prompt_tokens,
            completion_tokens: completion.usage.completion_tokens,
            total_tokens: completion.usage.total_tokens,
          }
        : {
            prompt_tokens: 0,
            completion_tokens: 0,
            total_tokens: 0,
          },
    };
  }
  return completion as ChatCompletion;
};


const isStructuredOutputCall = (call: TraceCallSchema): boolean => {
  const {response_format} = call.inputs;
  if (!response_format || !_.isPlainObject(response_format)) {
    return false;
  }
  if (response_format.type !== 'json_schema') {
    return false;
  }
  if (
    !response_format.json_schema ||
    !_.isPlainObject(response_format.json_schema)
  ) {
    return false;
  }
  return true;
};

// Traverse input and outputs looking for any ref strings.
const getRefs = (call: TraceCallSchema): string[] => {
  const refs = new Set<string>();
  traverse(call.inputs, (context: TraverseContext) => {
    if (isWeaveRef(context.value)) {
      refs.add(context.value);
    }
  });
  traverse(call.output, (context: TraverseContext) => {
    if (isWeaveRef(context.value)) {
      refs.add(context.value);
    }
  });
  return Array.from(refs);
};

// Replace all ref strings with the actual data.
const deref = (object: any, refsMap: Record<string, any>): any => {
  if (isWeaveRef(object)) {
    return refsMap[object] ?? object;
  }
  const mapper = (context: TraverseContext) => {
    if (context.valueType === 'string' && isWeaveRef(context.value)) {
      return refsMap[context.value] ?? context.value;
    }
    return context.value;
  };
  return mapObject(object, mapper);
};

export const normalizeChatRequest = (request: any): ChatRequest => {
  if (isGeminiRequestFormat(request)) {
    const modelIn = request.self.model_name;
    const model = modelIn.split('/').pop() ?? '';
    return {
      model,
      messages: [
        {
          role: 'system',
          content: request.contents,
        },
      ],
    };
  }
  // Anthropic has system message as a top-level request field
  if (hasStringProp(request, 'system')) {
    return {
      ...request,
      messages: [
        {
          role: 'system',
          content: request.system,
        },
        ...request.messages,
      ],
    };
  }
  return request as ChatRequest;
};


export const normalizeChatCompletion = (
  request: ChatRequest,
  completion: any
): ChatCompletion => {
  if (isGeminiCompletionFormat(completion)) {
    // We normalize to the OpenAI format as our standard representation
    // but the Gemini format does not have a direct mapping for some fields.
    // For now we leave empty placeholders for type checking purposes.
    return {
      id: '',
      choices: geminiCandidatesToChoices(completion.candidates),
      created: 0,
      model: request.model,
      system_fingerprint: '',
      usage: {
        prompt_tokens: completion.usage_metadata.prompt_token_count,
        completion_tokens: completion.usage_metadata.candidates_token_count,
        total_tokens: completion.usage_metadata.total_token_count,
      },
    };
  }
  if (isAnthropicCompletionFormat(completion)) {
    return {
      id: completion.id,
      choices: anthropicContentBlocksToChoices(
        completion.content,
        completion.stop_reason
      ),
      created: 0, // Anthropic doesn't provide `created`
      model: completion.model,
      system_fingerprint: '', // Anthropic doesn't provide `system_fingerprint`
      usage: {
        prompt_tokens: completion.usage.input_tokens,
        completion_tokens: completion.usage.output_tokens,
        total_tokens:
          completion.usage.input_tokens + completion.usage.output_tokens,
      },
    };
  }
  if (isMistralCompletionFormat(completion)) {
    if (completion === null) {
      // Handle cases where an SDK error or stream issue results in a null output
      // for a call that is otherwise identified as Mistral.
      return {
        id: request.model + '-' + Date.now(), // Generate a placeholder ID
        choices: [],
        created: Math.floor(Date.now() / 1000),
        model: request.model, // Use model from the request
        system_fingerprint: '',
        usage: {prompt_tokens: 0, completion_tokens: 0, total_tokens: 0},
      };
    }

    const choices: Choice[] = completion.choices.map((choicePart: any) => {
      let message: Message;
      if (choicePart.message) {
        message = choicePart.message as Message;
      } else if (choicePart.delta) {
        message = {
          role: choicePart.delta.role ?? 'assistant',
          content: choicePart.delta.content ?? '',
        };
        if (choicePart.delta.tool_calls) {
          message.tool_calls = choicePart.delta.tool_calls;
        }
      } else {
        message = {role: 'assistant', content: ''};
      }
      return {
        index: choicePart.index,
        message,
        finish_reason: choicePart.finish_reason ?? 'stop',
      };
    });

    return {
      id: completion.id,
      choices,
      created: completion.created,
      model: completion.model,
      system_fingerprint: completion.system_fingerprint ?? '',
      usage: completion.usage
        ? {
            prompt_tokens: completion.usage.prompt_tokens,
            completion_tokens: completion.usage.completion_tokens,
            total_tokens: completion.usage.total_tokens,
          }
        : {
            prompt_tokens: 0,
            completion_tokens: 0,
            total_tokens: 0,
          },
    };
  }
  return completion as ChatCompletion;
};

export const useCallAsChat = (
  call: TraceCallSchema
): {
  loading: boolean;
} & Chat => {
  // Traverse the data and find all ref URIs.
  const refs = getRefs(call);
  const {useRefsData} = useWFHooks();
  const refsData = useRefsData({refUris: refs});
  const refsMap = _.zipObject(refs, refsData.result ?? []);
  const request = normalizeChatRequest(deref(call.inputs, refsMap));
  const result = call.output
    ? normalizeChatCompletion(request, deref(call.output, refsMap))
    : null;

  // TODO: It is possible that all of the choices are refs again, handle this better.
  if (
    result &&
    result.choices &&
    result.choices.some(choice => isWeaveRef(choice))
  ) {
    result.choices = [];
  }

  return {
    loading: refsData.loading,
    isStructuredOutput: isStructuredOutputCall(call),
    request,
    result,
  };
};
