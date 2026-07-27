import {op} from '../op';
import {type OpOptions, type StreamReducer} from '../opType';
import {addCJSInstrumentation, addESMInstrumentation} from './instrumentations';
import {asAttributes, libraryIntegration} from './integrationMetadata';

// Integration provenance stamped onto every call this integration produces.
const GOOGLE_GENAI_INTEGRATION = libraryIntegration('google_genai', {
  packageName: '@google/genai',
});

const weaveGeminiModelHint = Symbol.for('_weave_gemini_model_hint');
const weaveGeminiModelsWrapped = Symbol.for('_weave_gemini_models_wrapped');

// Marker found in the `x-goog-api-client` header of GoogleGenAI clients that
// the Google ADK (`@google/adk`) constructs internally (its `trackingHeaders`).
// Those clients are excluded from wrapping: the ADK integration (WeaveAdkPlugin)
// already records each model call as a `chat` agent span with usage, so
// wrapping here would double-count tokens and emit orphan root traces.
const ADK_INTERNAL_CLIENT_HEADER = 'x-goog-api-client';
const ADK_INTERNAL_CLIENT_MARKER = 'google-adk/';

type GeminiUsageMetadata = {
  promptTokenCount?: number;
  candidatesTokenCount?: number;
  totalTokenCount?: number;
  thoughtsTokenCount?: number;
};

type GeminiUsageSummary = {
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
  thoughts_tokens?: number;
};

interface GeminiStreamState {
  model?: string;
  lastChunk?: any;
}

interface GoogleGenAIModelsAPI {
  generateContent: (...args: any[]) => Promise<any>;
  generateContentStream: (...args: any[]) => Promise<AsyncIterable<any>>;
  [key: string]: any;
}

interface GoogleGenAIAPI {
  models?: GoogleGenAIModelsAPI;
  chats?: {
    modelsModule?: GoogleGenAIModelsAPI;
    [key: string]: any;
  };
  [key: string]: any;
}

function maybeSetModelHint(target: any, model: string | undefined): void {
  if (!model || target == null || typeof target !== 'object') {
    return;
  }

  Object.defineProperty(target, weaveGeminiModelHint, {
    value: model,
    enumerable: false,
    configurable: true,
  });
}

function maybeGetModelHint(target: any): string | undefined {
  if (target == null || typeof target !== 'object') {
    return undefined;
  }
  return target[weaveGeminiModelHint];
}

function usageFromGeminiMetadata(
  usageMetadata: GeminiUsageMetadata | undefined
): GeminiUsageSummary | null {
  if (usageMetadata == null) {
    return null;
  }

  const usage: GeminiUsageSummary = {};
  if (usageMetadata.promptTokenCount != null) {
    usage.prompt_tokens = usageMetadata.promptTokenCount;
  }
  if (usageMetadata.candidatesTokenCount != null) {
    usage.completion_tokens = usageMetadata.candidatesTokenCount;
  }
  if (usageMetadata.totalTokenCount != null) {
    usage.total_tokens = usageMetadata.totalTokenCount;
  }
  if (usageMetadata.thoughtsTokenCount != null) {
    usage.thoughts_tokens = usageMetadata.thoughtsTokenCount;
  }

  if (Object.keys(usage).length === 0) {
    return null;
  }

  return usage;
}

function resolveModelName(result: any, source: any): string | undefined {
  return (
    result?.model ??
    result?.modelVersion ??
    maybeGetModelHint(result) ??
    source?.model ??
    source?.modelVersion ??
    maybeGetModelHint(source)
  );
}

export function geminiSummarizer(result: any) {
  // Non-streaming calls return a GenerateContentResponse-like object.
  // Streaming calls return the stream reducer state, where we store `lastChunk`.
  const source = result?.lastChunk ?? result;
  const usage = usageFromGeminiMetadata(source?.usageMetadata);
  const model = resolveModelName(result, source);

  if (!usage || !model) {
    return {};
  }

  return {
    usage: {
      [model]: usage,
    },
  };
}

const geminiStreamReducer: StreamReducer<any, GeminiStreamState> = {
  initialStateFn: () => ({
    model: undefined,
    lastChunk: undefined,
  }),
  reduceFn: (state, chunk) => {
    state.lastChunk = chunk;
    if (state.model == null) {
      state.model = maybeGetModelHint(chunk) ?? chunk?.modelVersion;
    }
    return state;
  },
  finalizeFn: () => {
    // no-op
  },
};

function makeGenerateContentOp(originalGenerateContent: any) {
  async function wrapped(...args: any[]) {
    const [params] = args;
    const result = await originalGenerateContent(...args);
    maybeSetModelHint(result, params?.model);
    return result;
  }

  const options: OpOptions<typeof wrapped> = {
    name: 'google.genai.models.generateContent',
    opKind: 'llm',
    attributes: asAttributes(GOOGLE_GENAI_INTEGRATION),
    parameterNames: 'useParam0Object',
    summarize: geminiSummarizer,
    originalFunction: originalGenerateContent,
  };

  return op(wrapped, options);
}

function makeGenerateContentStreamOp(originalGenerateContentStream: any) {
  async function wrapped(...args: any[]) {
    const [params] = args;
    const stream = await originalGenerateContentStream(...args);

    async function* taggedStream() {
      for await (const chunk of stream) {
        maybeSetModelHint(chunk, params?.model);
        yield chunk;
      }
    }

    return taggedStream();
  }

  const options: OpOptions<typeof wrapped> = {
    name: 'google.genai.models.generateContentStream',
    opKind: 'llm',
    attributes: asAttributes(GOOGLE_GENAI_INTEGRATION),
    parameterNames: 'useParam0Object',
    summarize: geminiSummarizer,
    streamReducer: geminiStreamReducer,
    originalFunction: originalGenerateContentStream,
  };

  return op(wrapped, options);
}

function wrapGoogleGenAIModels<T extends GoogleGenAIModelsAPI>(models: T): T {
  if (
    models == null ||
    typeof models !== 'object' ||
    !models.generateContent ||
    !models.generateContentStream
  ) {
    return models;
  }

  if ((models as any)[weaveGeminiModelsWrapped]) {
    return models;
  }

  const wrappedGenerateContent = makeGenerateContentOp(
    models.generateContent.bind(models)
  );
  const wrappedGenerateContentStream = makeGenerateContentStreamOp(
    models.generateContentStream.bind(models)
  );

  const wrappedModels = new Proxy(models, {
    get(target, prop, receiver) {
      if (prop === 'generateContent') {
        return wrappedGenerateContent;
      }
      if (prop === 'generateContentStream') {
        return wrappedGenerateContentStream;
      }
      return Reflect.get(target, prop, receiver);
    },
  });

  Object.defineProperty(wrappedModels, weaveGeminiModelsWrapped, {
    value: true,
    enumerable: false,
    configurable: false,
  });

  return wrappedModels;
}

export function wrapGoogleGenAI<T extends GoogleGenAIAPI>(googleGenAI: T): T {
  if (!googleGenAI || !googleGenAI.models) {
    return googleGenAI;
  }

  const wrappedModels = wrapGoogleGenAIModels(googleGenAI.models);
  googleGenAI.models = wrappedModels;

  // The Chat helper keeps a direct reference to models internally.
  // Keep it in sync so chat.sendMessage/sendMessageStream hit wrapped models.
  if (googleGenAI.chats && 'modelsModule' in googleGenAI.chats) {
    googleGenAI.chats.modelsModule = wrappedModels;
  }

  return googleGenAI;
}

/** True for clients constructed by `@google/adk` internally (see marker above). */
function isAdkInternalClientOptions(options: any): boolean {
  const headers = options?.httpOptions?.headers;
  if (headers == null || typeof headers !== 'object') {
    return false;
  }
  for (const [key, value] of Object.entries(headers)) {
    if (
      key.toLowerCase() === ADK_INTERNAL_CLIENT_HEADER &&
      typeof value === 'string' &&
      value.includes(ADK_INTERNAL_CLIENT_MARKER)
    ) {
      return true;
    }
  }
  return false;
}

function commonProxy(exports: any) {
  const OriginalGoogleGenAIClass = exports.GoogleGenAI;

  return new Proxy(OriginalGoogleGenAIClass, {
    construct(target, args, newTarget) {
      const instance = Reflect.construct(target, args, newTarget);
      if (isAdkInternalClientOptions(args[0])) {
        return instance;
      }
      // The user is using GoogleGenAI directly, not through ADK: wrap it.
      return wrapGoogleGenAI(instance);
    },
  });
}

export function commonPatchGoogleGenAI(exports: any) {
  if (!exports?.GoogleGenAI) {
    return exports;
  }

  const GoogleGenAIProxy = commonProxy(exports);

  Object.defineProperty(exports, 'GoogleGenAI', {
    value: GoogleGenAIProxy,
    writable: true,
    enumerable: true,
    configurable: true,
  });

  if (exports.default != null && typeof exports.default === 'function') {
    Object.defineProperty(exports, 'default', {
      value: GoogleGenAIProxy,
      writable: true,
      enumerable: true,
      configurable: true,
    });
  }

  return exports;
}

export function instrumentGoogleGenAI() {
  const cjsSubPaths = [
    'dist/node/index.cjs',
    'dist/node/index.js',
    'dist/index.cjs',
    'dist/index.js',
  ];

  for (const subPath of cjsSubPaths) {
    addCJSInstrumentation({
      moduleName: '@google/genai',
      subPath,
      version: '>= 0.2.0',
      hook: commonPatchGoogleGenAI,
    });
  }

  addESMInstrumentation({
    moduleName: '@google/genai',
    version: '>= 0.2.0',
    hook: commonPatchGoogleGenAI,
  });
}
