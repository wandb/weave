import {weaveImage} from '../media';
import {op} from '../op';
import {OpOptions} from '../opType';
import {addCJSInstrumentation, addESMInstrumentation} from './instrumentations';
import {getGlobalClient} from '../clientApi';
import {InternalCall} from '../call';
import {WeaveClient} from '../weaveClient';
import {warnOnce} from '../utils/warnOnce';
import {getCallStackFromOpenAIAgents} from './openai.agent';

/**
 * Wraps a function to run with OpenAI Agents call stack if available.
 * This ensures that OpenAI SDK calls are properly linked as children of OpenAI Agent calls.
 */
function runWithOpenAIAgentsContext<T>(fn: () => T): T {
  const client = getGlobalClient();
  // Only apply the agent stack as a fallback when Weave's own stack is empty.
  // If there's already an active Weave call (e.g. a user's op wrapping this
  // OpenAI call), preserve it so parent-child linking is correct.
  if (client && !client.getCallStack().peek()) {
    const agentStack = getCallStackFromOpenAIAgents();
    if (agentStack) {
      return client.runWithCallStack(agentStack, fn);
    }
  }
  return fn();
}

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

export function wrapOpenAIChatCompletionsCreate(
  originalCreate: any,
  name: string
) {
  const opRef = {
    __isOp: true as const,
    __name: name,
    __wrappedFunction: originalCreate,
  };
  const summarize = (result: any) => ({
    usage: {[result.model]: result.usage},
  });

  return function wrappedWithAgents(
    ...args: Parameters<typeof originalCreate>
  ) {
    const client = getGlobalClient();
    if (!client) return originalCreate(...args);

    const [originalParams]: any[] = args;
    // Streaming needs include_usage so the reducer sees token counts.
    // Spread into a new object so paramsToCallInputs still records
    // the caller's original args[0] for the trace.
    const callArgs: Parameters<typeof originalCreate> = originalParams?.stream
      ? ([
          {
            ...originalParams,
            stream_options: {
              ...originalParams.stream_options,
              include_usage: true,
            },
          },
        ] as Parameters<typeof originalCreate>)
      : args;

    return runWithOpenAIAgentsContext(() =>
      traceOpenAICall({
        client,
        opRef,
        userArgs: args,
        callArgs,
        originalCreate,
        summarize,
        streamReducer: openAIStreamReducer,
      })
    );
  };
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
    opKind: 'llm',
    summarize: result => ({
      usage: {
        'dall-e': {
          images_generated: result.data.length,
        },
      },
    }),
  };

  const weaveOp = op(wrapped, options);

  // Wrap with OpenAI Agents context if available
  return function wrappedWithAgents(...args: Parameters<typeof wrapped>) {
    return runWithOpenAIAgentsContext(() => weaveOp(...args));
  };
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

export function wrapOpenAIResponsesCreate(originalCreate: any) {
  const opRef = {
    __isOp: true as const,
    __name: 'create',
    __wrappedFunction: originalCreate,
  };

  return function wrappedWithAgents(
    this: any,
    ...args: Parameters<typeof originalCreate>
  ) {
    const client = getGlobalClient();
    if (!client) return originalCreate(...args);

    return runWithOpenAIAgentsContext(() =>
      traceOpenAICall({
        client,
        opRef,
        userArgs: args,
        callArgs: args,
        originalCreate,
        summarize: summarizer,
        streamReducer: openAIStreamAPIstreamReducer,
        // Forward `this` so paramsToCallInputs records it as `self`,
        // matching the old shouldAdoptThis behavior.
        thisArg: this,
      })
    );
  };
}

// Drives weave tracing directly using WeaveClient primitives, returning
// the SDK's native APIPromise (built via _thenUnwrap) so all helpers —
// .withResponse(), .asResponse(), .parse(), ._thenUnwrap(), and any
// future additions — flow through the SDK unchanged. For streaming,
// the parsed value is replaced with a Proxy whose Symbol.asyncIterator
// runs a reducer-tapping generator that fires finishCall in `finally`.
function traceOpenAICall(args: {
  client: WeaveClient;
  opRef: any;
  userArgs: any[];
  callArgs: any[];
  originalCreate: any;
  summarize: (result: any) => any;
  streamReducer: any;
  thisArg?: any;
}) {
  const {
    client,
    opRef,
    userArgs,
    callArgs,
    originalCreate,
    summarize,
    streamReducer,
    thisArg,
  } = args;

  const apiPromise = originalCreate(...callArgs);

  // Fail fast if the SDK's APIPromise shape is unfamiliar. We rely on
  // _thenUnwrap to install tracing in the parse chain; without it we
  // can't guarantee a stream is tapped or a non-streaming result is
  // finished. Rather than create a server-side call we can't close
  // cleanly, skip tracing for this invocation and hand the caller the
  // SDK's native APIPromise unchanged. Warn once so the cause is
  // discoverable (SDK version mismatch, non-OpenAI object, etc.).
  if (typeof apiPromise?._thenUnwrap !== 'function') {
    warnOnce(
      'weave-openai-no-thenUnwrap',
      '[weave] OpenAI SDK APIPromise._thenUnwrap is unavailable — tracing disabled for this call. Try upgrading weave to the latest version; if the issue persists, please file a bug report.'
    );
    return apiPromise;
  }

  const {currentCall, parentCall} = client.pushNewCall();
  const call = new InternalCall();
  const startTime = new Date();
  const startCallPromise = client.createCall(
    call,
    opRef,
    userArgs,
    'useParam0Object',
    thisArg,
    currentCall,
    parentCall,
    startTime,
    undefined,
    {kind: 'llm'}
  );

  const traced = apiPromise._thenUnwrap((value: any) => {
    if (value && typeof value === 'object' && Symbol.asyncIterator in value) {
      return wrapStreamForTracing({
        stream: value,
        streamReducer,
        client,
        call,
        currentCall,
        parentCall,
        summarize,
        startCallPromise,
      });
    }
    // Non-streaming: fire-and-forget finishCall so the returned promise
    // resolves without waiting on trace upload (matches batching).
    void client
      .finishCall(
        call,
        value,
        currentCall,
        parentCall,
        summarize,
        new Date(),
        startCallPromise
      )
      .catch(() => {});
    return value;
  });

  // Record SDK errors on the trace. Attaching this side handler also
  // marks the rejection as handled, so the caller's own await still
  // throws but Node doesn't additionally log an unhandled rejection.
  traced.catch(async (error: any) => {
    await client.finishCallWithException(
      call,
      error,
      currentCall,
      parentCall,
      new Date(),
      startCallPromise
    );
    await client.waitForBatchProcessing();
  });

  return traced;
}

function wrapStreamForTracing(args: {
  stream: AsyncIterable<any>;
  streamReducer: any;
  client: WeaveClient;
  call: InternalCall;
  currentCall: any;
  parentCall: any;
  summarize: (result: any) => any;
  startCallPromise: Promise<any>;
}) {
  const {
    stream,
    streamReducer,
    client,
    call,
    currentCall,
    parentCall,
    summarize,
    startCallPromise,
  } = args;
  const {initialStateFn, reduceFn, finalizeFn} = streamReducer;
  let state = initialStateFn();
  async function* WeaveIterator() {
    let iterationError: unknown;
    try {
      for await (const chunk of stream) {
        state = reduceFn(state, chunk);
        yield chunk;
      }
    } catch (e) {
      iterationError = e;
      throw e;
    } finally {
      // Route a mid-iteration failure (network error, server-sent
      // error event, caller throws inside the loop) to
      // finishCallWithException — recording it as a successful
      // completion with partial output would be a lie.
      if (iterationError !== undefined) {
        await client.finishCallWithException(
          call,
          iterationError,
          currentCall,
          parentCall,
          new Date(),
          startCallPromise
        );
      } else {
        finalizeFn(state);
        await client.finishCall(
          call,
          state,
          currentCall,
          parentCall,
          summarize,
          new Date(),
          startCallPromise
        );
      }
    }
  }
  return new Proxy(stream, {
    get(target, prop) {
      if (prop === Symbol.asyncIterator) return WeaveIterator;
      return Reflect.get(target, prop);
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
        return wrapOpenAIChatCompletionsCreate(
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
          return wrapOpenAIChatCompletionsCreate(
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
            return wrapOpenAIResponsesCreate(targetVal.bind(target));
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
