import {addCJSInstrumentation, addESMInstrumentation} from './instrumentations';
import {op} from '../op';
import {OpOptions, StreamReducer} from '../opType';

type Message = {
  id: string;
  role: string;
  type: string;
  model: string;
  content: Array<{type: string; text: string}>;
  stop_reason: string;
  stop_sequence: any;
  usage?: any;
};

type StreamChunk =
  | {type: 'message_start'; message: Message}
  | {
      type: 'message_delta';
      delta: {stop_reason: string; stop_sequence: any};
      usage: {output_tokens: number};
    }
  | {type: 'message_stop'}
  | {
      type: 'content_block_start';
      index: number;
      content_block: {type: string; text: string};
    }
  | {
      type: 'content_block_delta';
      delta: {type: string; text: string};
      usage: {output_tokens: number};
    }
  | {type: 'content_block_stop'; index: number};

interface ResultState {
  messages: Array<Message>;
}

const streamReducer: StreamReducer<StreamChunk, ResultState> = {
  initialStateFn: () => ({
    messages: [],
  }),
  reduceFn: (state, chunk) => {
    let lastMessage: Message;
    switch (chunk.type) {
      case 'message_start':
        state.messages.push({...chunk.message, content: []});
        break;
      case 'message_delta':
        lastMessage = state.messages[state.messages.length - 1];
        Object.assign(lastMessage, chunk.delta);
        Object.assign(lastMessage.usage ?? {}, chunk.usage);
        break;
      case 'content_block_start':
        lastMessage = state.messages[state.messages.length - 1];
        lastMessage.content.push(chunk.content_block);
        break;
      case 'content_block_delta':
        lastMessage = state.messages[state.messages.length - 1];
        lastMessage.content.push(chunk.delta);
        break;
    }
    return state;
  },
};

function summarizer(result: any) {
  // Non-streaming mode
  if (result.usage != null && result.usage != null) {
    return {
      usage: {
        [result.model]: result.usage,
      },
    };
  }
  // Streaming mode
  if (result.messages != null && result.messages.length > 0) {
    const usage: Record<string, {input_tokens: number; output_tokens: number}> =
      {};
    for (const message of result.messages) {
      const {usage: messageUsage, model} = message;
      if (model == undefined || usage == undefined) {
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

function patchAnthropicMessagesCreate(exports: any) {
  const originalCreate = exports.Anthropic.Messages.prototype.create;

  exports.Anthropic.Messages.prototype.create = new Proxy(originalCreate, {
    apply: (target, thisArg, args) => {
      const [inputOptions] = args;
      const isStream = inputOptions.stream;
      const weaveOpOptions: OpOptions<typeof originalCreate> = {
        name: 'create',
        shouldAdoptThis: true,
        originalFunction: originalCreate,
        summarize: summarizer,
        ...(isStream ? {streamReducer} : null),
      };

      let result: any;

      let weaveOp = op(() => {
        result = originalCreate.apply(thisArg, args);
        return result;
      }, weaveOpOptions);

      const weaveResult = weaveOp.apply(thisArg, args);
      result.then = (
        onFulfilled: (...args: any[]) => any,
        onRejected: (...args: any[]) => any
      ) => {
        // weaveResult is going to carry the patched iterator, override the original result with it
        return weaveResult.then(onFulfilled, onRejected);
      };
      return result;
    },
  });
}

type ResultBoxing = {
  result: any;
};

function patchStreamHelper(exports: any) {
  const originalStream = exports.Anthropic.Messages.prototype.stream;

  async function StreamWrapper(
    this: any,
    context: ResultBoxing,
    ...args: any[]
  ) {
    const stream = originalStream.apply(this, args);
    context.result = stream;

    return new Promise((resolve, reject) => {
      stream.on('end', () => {
        resolve({messages: stream.messages});
      });
      stream.on('error', reject);
    });
  }

  const options: OpOptions<typeof originalStream> = {
    name: 'stream',
    shouldAdoptThis: true,
    summarize: summarizer,
    originalFunction: originalStream,
  };

  const weaveOp = op(StreamWrapper, options);

  exports.Anthropic.Messages.prototype.stream = new Proxy(originalStream, {
    apply: (target, thisArg, args) => {
      const box = {result: null};
      weaveOp.apply(thisArg, [box, ...args]);
      return box.result;
    },
  });
}

type BatchChunk = {
  type: undefined;
  custom_id: string;
  result: {type: string; message: Message};
};

const batchStreamReducer: StreamReducer<BatchChunk, ResultState> = {
  initialStateFn: streamReducer.initialStateFn,
  reduceFn: (state, chunk) => {
    // batch message type
    if (typeof chunk.result == 'object' && chunk.result != null) {
      state.messages.push(chunk.result.message);
    }
    return state;
  },
};

function patchBatchApi(exports: any) {
  // patch create
  const originalBatchCreate =
    exports.Anthropic.Messages.Batches.prototype.create;

  const weaveOp = op<typeof originalBatchCreate>(originalBatchCreate, {
    name: 'create',
    shouldAdoptThis: true,
    originalFunction: originalBatchCreate,
  });

  exports.Anthropic.Messages.Batches.prototype.create = weaveOp;

  // patch retrieve
  const originalBatchRetrieve =
    exports.Anthropic.Messages.Batches.prototype.retrieve;
  const weaveOpRetrieve = op<typeof originalBatchRetrieve>(
    originalBatchRetrieve,
    {
      name: 'retrieve',
      shouldAdoptThis: true,
      originalFunction: originalBatchRetrieve,
    }
  );

  exports.Anthropic.Messages.Batches.prototype.retrieve = weaveOpRetrieve;

  // patch results
  const originalBatchResults =
    exports.Anthropic.Messages.Batches.prototype.results;

  const weaveOpResults = op<typeof originalBatchResults>(originalBatchResults, {
    name: 'results',
    shouldAdoptThis: true,
    summarize: summarizer,
    originalFunction: originalBatchResults,
    streamReducer: batchStreamReducer,
  });

  exports.Anthropic.Messages.Batches.prototype.results = weaveOpResults;
}

export function commonPatchAnthropic(exports: any) {
  patchAnthropicMessagesCreate(exports);
  patchStreamHelper(exports);
  patchBatchApi(exports);
  return exports;
}

export function instrumentAnthropic() {
  addCJSInstrumentation({
    moduleName: '@anthropic-ai/sdk',
    subPath: 'index.js',
    version: '>= 0.52.0',
    hook: commonPatchAnthropic,
  });
  addESMInstrumentation({
    moduleName: '@anthropic-ai/sdk',
    version: '>= 0.52.0',
    hook: commonPatchAnthropic,
  });
}
