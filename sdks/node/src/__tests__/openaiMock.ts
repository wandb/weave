function generateId() {
  return 'chatcmpl-' + Math.random().toString(36).substr(2, 9);
}

function generateSystemFingerprint() {
  return 'fp_' + Math.random().toString(36).substr(2, 9);
}

type FunctionCall = {
  name: string;
  arguments: Record<string, any>;
};

type ResponseFn = (messages: any[]) => {
  content: string;
  functionCalls?: FunctionCall[];
};

// Simple function to estimate token count
function estimateTokenCount(text: string): number {
  return Math.ceil(text.split(/\s+/).length); // 1 token per word for testing
}

export function makeMockOpenAIChat(responseFn: ResponseFn) {
  return function openaiChatCompletionsCreate({
    messages,
    stream = false,
    model = 'gpt-4o-2024-05-13',
    stream_options,
    ...otherOptions
  }: {
    messages: any[];
    stream?: boolean;
    model?: string;
    stream_options?: {include_usage?: boolean};
    [key: string]: any;
  }) {
    const response = responseFn(messages);
    const {content, functionCalls = []} = response;

    const promptTokens = messages.reduce(
      (acc, msg) => acc + estimateTokenCount(msg.content),
      0
    );
    const completionTokens =
      estimateTokenCount(content) +
      functionCalls.reduce(
        (acc, fc) =>
          acc +
          estimateTokenCount(fc.name) +
          estimateTokenCount(JSON.stringify(fc.arguments)),
        0
      );
    const totalTokens = promptTokens + completionTokens;

    if (stream) {
      return {
        [Symbol.asyncIterator]: async function* () {
          yield* generateChunks(
            content,
            functionCalls,
            model,
            promptTokens,
            completionTokens,
            totalTokens,
            stream_options
          );
        },
      };
    } else {
      return {
        id: generateId(),
        object: 'chat.completion',
        created: Math.floor(Date.now() / 1000),
        model: model,
        choices: [
          {
            index: 0,
            message: {
              role: 'assistant',
              content: content,
              function_call: functionCalls[0]
                ? {
                    name: functionCalls[0].name,
                    arguments: JSON.stringify(functionCalls[0].arguments),
                  }
                : null,
              refusal: null,
            },
            logprobs: null,
            finish_reason: functionCalls.length > 0 ? 'function_call' : 'stop',
          },
        ],
        usage: {
          prompt_tokens: promptTokens,
          completion_tokens: completionTokens,
          total_tokens: totalTokens,
        },
        system_fingerprint: generateSystemFingerprint(),
      };
    }
  };
}

function* generateChunks(
  content: string,
  functionCalls: FunctionCall[],
  model: string,
  promptTokens: number,
  completionTokens: number,
  totalTokens: number,
  stream_options?: {include_usage?: boolean}
) {
  const id = generateId();
  const systemFingerprint = generateSystemFingerprint();
  const created = Math.floor(Date.now() / 1000);

  const baseChunk = {
    id,
    object: 'chat.completion.chunk',
    created,
    model,
    system_fingerprint: systemFingerprint,
  };

  const includeUsage = stream_options?.include_usage;

  // Initial chunk
  yield {
    ...baseChunk,
    choices: [
      {
        index: 0,
        delta: {role: 'assistant', content: '', refusal: null},
        logprobs: null,
        finish_reason: null,
      },
    ],
    ...(includeUsage && {usage: null}),
  };

  // Content chunks
  const words = content.split(' ');
  for (let i = 0; i < words.length; i++) {
    yield {
      ...baseChunk,
      choices: [
        {
          index: 0,
          delta: {content: words[i] + (i < words.length - 1 ? ' ' : '')},
          logprobs: null,
          finish_reason: null,
        },
      ],
      ...(includeUsage && {usage: null}),
    };
  }

  // Function call chunks
  for (const functionCall of functionCalls) {
    yield {
      ...baseChunk,
      choices: [
        {
          index: 0,
          delta: {function_call: {name: functionCall.name, arguments: ''}},
          logprobs: null,
          finish_reason: null,
        },
      ],
      ...(includeUsage && {usage: null}),
    };

    const args = JSON.stringify(functionCall.arguments);
    for (let i = 0; i < args.length; i += 10) {
      yield {
        ...baseChunk,
        choices: [
          {
            index: 0,
            delta: {function_call: {arguments: args.slice(i, i + 10)}},
            logprobs: null,
            finish_reason: null,
          },
        ],
        ...(includeUsage && {usage: null}),
      };
    }
  }

  // Second to last chunk (finish_reason)
  yield {
    ...baseChunk,
    choices: [
      {
        index: 0,
        delta: {},
        logprobs: null,
        finish_reason: functionCalls.length > 0 ? 'function_call' : 'stop',
      },
    ],
    ...(includeUsage && {usage: null}),
  };

  // Final chunk with usage information (only if include_usage is true)
  if (includeUsage) {
    yield {
      ...baseChunk,
      choices: [],
      usage: {
        prompt_tokens: promptTokens,
        completion_tokens: completionTokens,
        total_tokens: totalTokens,
      },
    };
  }
}
