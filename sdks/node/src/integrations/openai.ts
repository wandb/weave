import {weaveImage} from '../media';
import {op} from '../op';
import {OpOptions} from '../opType';
import {addCJSInstrumentation, addESMInstrumentation} from './instrumentations';

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
  finalizeFn: () => {
    // no-op
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

import {StreamReducer} from '../opType';

export type Response = {
  id: string;
  object: string;
  created_at: number;
  status: string;
  background: boolean;
  error: any;
  incomplete_details: any;
  instructions: string;
  max_output_tokens: any;
  model: string;
  output: any;
  parallel_tool_calls: boolean;
  previous_response_id: string | null;
  reasoning: {effort: any; summary: any};
  service_tier: string;
  store: boolean;
  temperature: number;
  text: {format: any};
  tool_choice: string;
  tools: any[];
  top_p: number;
  truncation: string;
  usage: any;
  user: string | null;
  metadata: any;
};

type StreamChunk =
  | {type: 'response.created'; sequence_number: number; response: Response}
  | {
      type: 'response.in_progress';
      sequence_number: number;
      response: Response;
    }
  | {
      type: 'response.output_item.added';
      sequence_number: number;
      output_index: number;
      item: {
        id: string;
        type: string;
        status: string;
        content: any[];
        role: string;
      };
    }
  | {
      type: 'response.content_part.added';
      sequence_number: number;
      item_id: string;
      output_index: number;
      content_index: number;
      part: {
        type: string;
        annotations: any[];
        text: string;
      };
    }
  | {
      type: 'response.output_text.delta';
      sequence_number: number;
      item_id: string;
      output_index: number;
      content_index: number;
      delta: string;
    }
  | {
      type: 'response.output_text.done';
      sequence_number: number;
      item_id: string;
      output_index: 0;
      content_index: 0;
      text: string;
    }
  | {
      type: 'response.content_part.done';
      sequence_number: number;
      item_id: string;
      output_index: number;
      content_index: number;
      part: {
        type: string;
        annotations: any[];
        text: string;
      };
    }
  | {
      type: 'response.output_item.done';
      sequence_number: number;
      output_index: number;
      item: {
        id: string;
        type: string;
        status: string;
        content: any[];
        role: 'assistant';
      };
    }
  | {
      type: 'response.completed';
      sequence_number: number;
      response: Response;
    };

interface ResultState {
  responses: Array<Response>;
  _outputStaging?: Array<string>;
}

export const openAIStreamAPIstreamReducer: StreamReducer<
  StreamChunk,
  ResultState
> = {
  initialStateFn: () => ({
    responses: [],
    _outputStaging: [],
  }),
  reduceFn: (state, chunk) => {
    switch (chunk.type) {
      case 'response.created':
        // Initialize a new response when created
        state.responses.push({...chunk.response});
        break;

      case 'response.in_progress':
        // Update the response in progress
        if (state.responses.length > 0) {
          const lastResponse = state.responses[state.responses.length - 1];
          Object.assign(lastResponse, chunk.response);
        }
        break;

      case 'response.output_item.added':
        // Add a new output item to the response
        if (state.responses.length > 0) {
          const lastResponse = state.responses[state.responses.length - 1];
          if (!lastResponse.output) {
            lastResponse.output = [];
          }
          lastResponse.output[chunk.output_index] = chunk.item;
        }
        break;

      case 'response.content_part.added':
        // Add a new content part to the output item
        if (state.responses.length > 0) {
          const lastResponse = state.responses[state.responses.length - 1];
          if (lastResponse.output && lastResponse.output[chunk.output_index]) {
            const outputItem = lastResponse.output[chunk.output_index];
            if (!outputItem.content) {
              outputItem.content = [];
            }
            outputItem.content[chunk.content_index] = chunk.part;
          }
        }
        break;

      case 'response.output_text.delta':
        if (!state._outputStaging) {
          state._outputStaging = [];
        }
        // To prevent output stream interruption, we also temporarily store the delta in a staging area
        state._outputStaging.push(chunk.delta);
        break;

      case 'response.output_text.done':
        // Set the complete text from the done event
        if (state.responses.length > 0) {
          const lastResponse = state.responses[state.responses.length - 1];
          if (lastResponse.output && lastResponse.output[chunk.output_index]) {
            const outputItem = lastResponse.output[chunk.output_index];
            if (outputItem.content && outputItem.content[chunk.content_index]) {
              outputItem.content[chunk.content_index].text = chunk.text;
            }
          }
        }
        // Clear the staging area after the done event
        state._outputStaging = [];
        break;

      case 'response.content_part.done':
        // Update the content part when done
        if (state.responses.length > 0) {
          const lastResponse = state.responses[state.responses.length - 1];
          if (lastResponse.output && lastResponse.output[chunk.output_index]) {
            const outputItem = lastResponse.output[chunk.output_index];
            if (outputItem.content && outputItem.content[chunk.content_index]) {
              Object.assign(
                outputItem.content[chunk.content_index],
                chunk.part
              );
            }
          }
        }
        break;

      case 'response.output_item.done':
        // Update the output item when done
        if (state.responses.length > 0) {
          const lastResponse = state.responses[state.responses.length - 1];
          if (lastResponse.output && lastResponse.output[chunk.output_index]) {
            Object.assign(lastResponse.output[chunk.output_index], chunk.item);
          }
        }
        break;

      case 'response.completed':
        // Update the final response when completed
        if (state.responses.length > 0) {
          const lastResponse = state.responses[state.responses.length - 1];
          Object.assign(lastResponse, chunk.response);
        }
        break;
    }
    return state;
  },
  finalizeFn: state => {
    if (
      state._outputStaging &&
      state._outputStaging.length > 0 &&
      state.responses.length > 0
    ) {
      const lastResponse = state.responses[state.responses.length - 1];
      if (!lastResponse.output || lastResponse.output.length === 0) {
        lastResponse.output = [{} as any];
      }
      const lastOutputItem =
        lastResponse.output[lastResponse.output.length - 1];

      if (!lastOutputItem.content || lastOutputItem.content.length === 0) {
        lastOutputItem.content = [{} as any];
      }

      const lastOutputItemContent =
        lastOutputItem.content[lastOutputItem.content.length - 1];
      lastOutputItemContent.text = state._outputStaging.join('');
    }
    delete state._outputStaging;
  },
};

export function summarizer(result: any) {
  // Non-streaming mode
  if (result.usage != null && result.model != null) {
    return {
      usage: {
        [result.model]: result.usage,
      },
    };
  }

  // Streaming mode
  if (result.responses != null && result.responses.length > 0) {
    const usage: Record<string, {input_tokens: number; output_tokens: number}> =
      {};
    for (const message of result.responses) {
      const {usage: messageUsage, model} = message;
      if (model == undefined || messageUsage == undefined) {
        continue;
      }
      if (usage[model] == null) {
        usage[model] = {
          input_tokens: 0,
          output_tokens: 0,
        };
      }
      usage[model].input_tokens += messageUsage?.input_tokens ?? 0;
      usage[model].output_tokens += messageUsage?.output_tokens ?? 0;
    }

    return {
      usage,
    };
  }
  return {};
}

export function makeOpenAIResponsesCreateProxy(originalCreate: any) {
  return new Proxy(originalCreate, {
    apply: (target, thisArg, args) => {
      const [inputOptions] = args;
      const isStream = inputOptions.stream;
      const weaveOpOptions: OpOptions<typeof originalCreate> = {
        name: 'create',
        shouldAdoptThis: true,
        originalFunction: originalCreate,
        summarize: summarizer,
        ...(isStream ? {streamReducer: openAIStreamAPIstreamReducer} : null),
        parameterNames: 'useParam0Object',
      };

      let weaveOp = op(() => {
        return originalCreate.apply(thisArg, args);
      }, weaveOpOptions);

      return weaveOp.apply(thisArg, args);
    },
  });
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
  responses: {
    create: any;
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

  const hasBetaChatApis = openai.beta.chat != null;
  let betaProxy: any = null;

  if (hasBetaChatApis) {
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
    betaProxy = new Proxy(openai.beta, {
      get(target, p, receiver) {
        const targetVal = Reflect.get(target, p, receiver);
        if (p === 'chat') {
          return betaChatProxy;
        }
        return targetVal;
      },
    });
  }

  // Only create responses proxy if responses property exists
  const responsesProxy = openai.responses
    ? new Proxy(openai.responses, {
        get(target, p, receiver) {
          const targetVal = Reflect.get(target, p, receiver);

          if (p === 'create') {
            return makeOpenAIResponsesCreateProxy(targetVal);
          }
          return targetVal;
        },
      })
    : null;

  return new Proxy(openai, {
    get(target, p, receiver) {
      const targetVal = Reflect.get(target, p, receiver);
      if (p === 'chat') {
        return chatProxy;
      }
      if (p === 'images') {
        return imagesProxy;
      }
      if (hasBetaChatApis && p === 'beta') {
        return betaProxy;
      }
      if (p === 'responses' && responsesProxy) {
        return responsesProxy;
      }
      return targetVal;
    },
  });
}

function commonProxy(exports: any) {
  const OriginalOpenAIClass = exports.OpenAI;

  return new Proxy(OriginalOpenAIClass, {
    construct(target, args, newTarget) {
      const instance = new target(...args);
      return wrapOpenAI(instance);
    },
  });
}
function cjsPatchOpenAI(exports: any) {
  const OpenAIProxy = commonProxy(exports);

  // Patch named export (must use defineProperty to override read-only getter)
  Object.defineProperty(exports, 'OpenAI', {
    value: OpenAIProxy,
    writable: true,
    enumerable: true,
    configurable: true,
  });

  // Patch default export (must use defineProperty to override read-only getter)
  if (exports.default) {
    Object.defineProperty(exports, 'default', {
      value: OpenAIProxy,
      writable: true,
      enumerable: true,
      configurable: true,
    });
  }

  return exports;
}

function esmPatchOpenAI(exports: any) {
  const OpenAIProxy = commonProxy(exports);

  // Patch named export (must use defineProperty to override read-only getter)
  Object.defineProperty(exports, 'OpenAI', {
    value: OpenAIProxy,
    writable: true,
    enumerable: true,
    configurable: true,
  });

  // Patch default export (must use defineProperty to override read-only getter)
  Object.defineProperty(exports, 'default', {
    value: OpenAIProxy,
    writable: true,
    enumerable: true,
    configurable: true,
  });

  return exports;
}

export function instrumentOpenAI() {
  addCJSInstrumentation({
    moduleName: 'openai',
    subPath: 'index.js',
    // 4.0.0 is the prevalently used version of openai at the time of writing
    // if we want to support other versions with different implementations,
    // we can add a call of `addInstrumentation()` for each version.
    version: '>= 4.0.0',
    hook: cjsPatchOpenAI,
  });
  addESMInstrumentation({
    moduleName: 'openai',
    version: '>= 4.0.0',
    hook: esmPatchOpenAI,
  });
}
