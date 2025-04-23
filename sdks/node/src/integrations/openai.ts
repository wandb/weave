import {weaveImage} from '../media';
import {op} from '../op';
import {OpOptions} from '../opType';

// exported just for testing
export const openAIStreamReducer = {
  initialStateFn: () => ({
    id: '',
    object: 'chat.completion',
    created: 0,
    model: '',
    choices: [
      {
        index: 0,
        message: {
          role: 'assistant',
          content: '',
          function_call: null,
        },
        finish_reason: null,
      },
    ],
    usage: null,
  }),
  reduceFn: (state: any, chunk: any) => {
    if (chunk.id) state.id = chunk.id;
    if (chunk.object) state.object = chunk.object;
    if (chunk.created) state.created = chunk.created;
    if (chunk.model) state.model = chunk.model;

    if (chunk.choices && chunk.choices.length > 0) {
      const choice = chunk.choices[0];
      if (choice.delta) {
        if (choice.delta.role) {
          state.choices[0].message.role = choice.delta.role;
        }
        if (choice.delta.content) {
          state.choices[0].message.content += choice.delta.content;
        }
        if (choice.delta.function_call) {
          if (!state.choices[0].message.function_call) {
            state.choices[0].message.function_call = {
              name: '',
              arguments: '',
            };
          }
          if (choice.delta.function_call.name) {
            state.choices[0].message.function_call.name =
              choice.delta.function_call.name;
          }
          if (choice.delta.function_call.arguments) {
            state.choices[0].message.function_call.arguments +=
              choice.delta.function_call.arguments;
          }
        }
      }
      if (choice.finish_reason) {
        state.choices[0].finish_reason = choice.finish_reason;
      }
    }

    if (chunk.usage) {
      state.usage = chunk.usage;
    }

    return state;
  },
};

export function makeOpenAIChatCompletionsOp(originalCreate: any, name: string) {
  function wrapped(...args: Parameters<typeof originalCreate>) {
    const [originalParams]: any[] = args;
    if (originalParams.stream) {
      return originalCreate({
        ...originalParams,
        stream_options: {...originalParams.stream_options, include_usage: true},
      });
    }

    return originalCreate(originalParams);
  }

  const options: OpOptions<typeof wrapped> = {
    name: name,
    parameterNames: 'useParam0Object',
    summarize: result => ({
      usage: {
        [result.model]: result.usage,
      },
    }),
    streamReducer: openAIStreamReducer,
  };

  return op(wrapped, options);
}

export function makeOpenAIImagesGenerateOp(originalGenerate: any) {
  async function wrapped(...args: Parameters<typeof originalGenerate>) {
    const result = await originalGenerate(...args);

    // Process the result to convert image data to WeaveImage
    if (result.data) {
      result.data = await Promise.all(
        result.data.map(async (item: any) => {
          if (item.b64_json) {
            const buffer = Buffer.from(item.b64_json, 'base64');
            return weaveImage({data: buffer, imageType: 'png'});
          }
          return item;
        })
      );
    }

    return result;
  }

  const options: OpOptions<typeof wrapped> = {
    name: 'openai.images.generate',
    summarize: result => ({
      usage: {
        'dall-e': {
          images_generated: result.data.length,
        },
      },
    }),
  };

  return op(wrapped, options);
}

interface OpenAIAPI {
  chat: {
    completions: {
      create: any;
    };
  };
  images: {
    generate: any;
  };
  beta: {
    chat: {
      completions: {
        parse: any;
      };
    };
  };
}

/**
 * Wraps the OpenAI API to enable function tracing for OpenAI calls.
 *
 * @example
 * const openai = wrapOpenAI(new OpenAI());
 * const result = await openai.chat.completions.create({
 *   model: 'gpt-3.5-turbo',
 *   messages: [{ role: 'user', content: 'Hello, world!' }]
 * });
 */
export function wrapOpenAI<T extends OpenAIAPI>(openai: T): T {
  const chatCompletionsProxy = new Proxy(openai.chat.completions, {
    get(target, p, receiver) {
      const targetVal = Reflect.get(target, p, receiver);
      if (p === 'create') {
        return makeOpenAIChatCompletionsOp(
          targetVal.bind(target),
          'openai.chat.completions.create'
        );
      }
      return targetVal;
    },
  });
  const chatProxy = new Proxy(openai.chat, {
    get(target, p, receiver) {
      const targetVal = Reflect.get(target, p, receiver);
      if (p === 'completions') {
        return chatCompletionsProxy;
      }
      return targetVal;
    },
  });

  const imagesProxy = new Proxy(openai.images, {
    get(target, p, receiver) {
      const targetVal = Reflect.get(target, p, receiver);
      if (p === 'generate') {
        return makeOpenAIImagesGenerateOp(targetVal.bind(target));
      }
      return targetVal;
    },
  });

  const betaChatCompletionsProxy = new Proxy(openai.beta.chat.completions, {
    get(target, p, receiver) {
      const targetVal = Reflect.get(target, p, receiver);
      if (p === 'parse') {
        return makeOpenAIChatCompletionsOp(
          targetVal.bind(target),
          'openai.beta.chat.completions.parse'
        );
      }
      return targetVal;
    },
  });
  const betaChatProxy = new Proxy(openai.beta.chat, {
    get(target, p, receiver) {
      const targetVal = Reflect.get(target, p, receiver);
      if (p === 'completions') {
        return betaChatCompletionsProxy;
      }
      return targetVal;
    },
  });
  const betaProxy = new Proxy(openai.beta, {
    get(target, p, receiver) {
      const targetVal = Reflect.get(target, p, receiver);
      if (p === 'chat') {
        return betaChatProxy;
      }
      return targetVal;
    },
  });

  return new Proxy(openai, {
    get(target, p, receiver) {
      const targetVal = Reflect.get(target, p, receiver);
      if (p === 'chat') {
        return chatProxy;
      }
      if (p === 'images') {
        return imagesProxy;
      }
      if (p === 'beta') {
        return betaProxy;
      }
      return targetVal;
    },
  });
}
