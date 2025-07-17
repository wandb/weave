import {JSONSchema7} from 'json-schema';
import _ from 'lodash';
import React, {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from 'react';
import z from 'zod';
import {zodToJsonSchema} from 'zod-to-json-schema';

import {TraceServerClient} from '../traceServerClient';
import {useGetTraceServerClientContext} from '../traceServerClientContext';
import {ResponseFormat} from '../traceServerClientTypes';
import {dangerouslyLogCallToWeave} from './magicianWeaveLogger';

const DEFAULT_MODEL = 'coreweave/moonshotai/Kimi-K2-Instruct';

export type Message = {
  role: 'user' | 'assistant' | 'system';
  content: string;
};

export type EntityProject = {
  entity: string;
  project: string;
};

export type Completion = string | Record<string, unknown>;

export type Chunk = {
  content: string;
};

export type CompletionResponseFormat = ResponseFormat | z.ZodType;

export type Tool = {
  type: 'function';
  function: {
    name: string;
    description: string;
    parameters: {
      type: 'object';
      properties: JSONSchema7['properties'];
    };
    required: string[];
  };
};

export type ChatCompletionParams = {
  // `weavePlaygroundModelId` is a string identifier for the model to use.
  weavePlaygroundModelId: string;
  // // `modelProvider` refers to the provider of the model.
  // // for example: `openai`, `anthropic`, etc...
  // // Model provider is optional since many models
  // // have unique providers (eg. `gpt-4o-mini` is provided by `openai`)
  // //
  // // Note: a special provider is `coreweave` which maps to the CoreWeave API.
  // modelProvider?: string;
  // Prompts coming soon!
  // `promptId` is the id (ref) of a prompt to use
  // promptId?: string
  // `prompt` is the prompt to use
  // promptVariables?: Record<string, any>
  // `messages` is the messages to be sent to the model.
  messages: string | Array<Message>;
  // `responseFormat` is the format of the response.
  responseFormat?: CompletionResponseFormat;
  // `temperature` is the temperature of the model.
  temperature?: number;
  // `tools` is the tools to use.
  tools?: Array<Tool>;
};

// /**
//  * Prepare the model identifier, handling provider-specific formatting.
//  *
//  * @param modelId The model identifier
//  * @param modelProvider Optional provider name
//  * @returns Formatted model string
//  */
// const prepareModel = (modelId: string, modelProvider?: string) => {
//   if (modelProvider) {
//     return `${modelProvider}/${modelId}`;
//   }
//   return modelId;
// };

/**
 * Convert messages to the expected format for the API.
 *
 * @param messages String or array of Message objects
 * @returns Array of Message objects
 */
const prepareMessages = (messages: string | Array<Message>) => {
  if (typeof messages === 'string') {
    return [
      {
        role: 'user',
        content: messages,
      },
    ];
  } else {
    return messages;
  }
};

/**
 * Prepare response format configuration for the API.
 * Currently not implemented as it depends on provider-specific requirements.
 *
 * @param responseFormat The desired response format
 * @returns Formatted response configuration
 */
const prepareResponseFormat = (
  responseFormat?: CompletionResponseFormat
): ResponseFormat | undefined => {
  if (!responseFormat) {
    return undefined;
  }

  if (typeof responseFormat === 'object' && 'type' in responseFormat) {
    return responseFormat;
  }

  return {
    type: 'json_schema',
    json_schema: {
      name: 'response',
      strict: true,
      schema: _.omit(zodToJsonSchema(responseFormat), [
        '$schema',
        'definitions',
      ]),
    },
  };
};

/**
 * Combine streaming chunks into a single completion response.
 *
 * @param chunks Array of streaming chunks
 * @returns Combined completion string
 */
const combineChunks = (chunks: unknown[]): string => {
  if (!Array.isArray(chunks) || chunks.length === 0) {
    return '';
  }

  // Type guard for OpenAI-style chunks
  const isOpenAIChunk = (
    chunk: unknown
  ): chunk is {
    choices: Array<{
      delta: {
        content?: string;
      };
    }>;
  } => {
    return (
      typeof chunk === 'object' &&
      chunk !== null &&
      'choices' in chunk &&
      Array.isArray((chunk as any).choices) &&
      (chunk as any).choices.length > 0 &&
      'delta' in (chunk as any).choices[0]
    );
  };

  // Type guard for simple content chunks
  const isContentChunk = (
    chunk: unknown
  ): chunk is {
    content: string;
  } => {
    return (
      typeof chunk === 'object' &&
      chunk !== null &&
      'content' in chunk &&
      typeof (chunk as any).content === 'string'
    );
  };

  const contentParts: string[] = [];

  for (const chunk of chunks) {
    if (isOpenAIChunk(chunk)) {
      const content = chunk.choices[0]?.delta?.content;
      if (content) {
        contentParts.push(content);
      }
    } else if (isContentChunk(chunk)) {
      contentParts.push(chunk.content);
    } else if (typeof chunk === 'string') {
      contentParts.push(chunk);
    }
  }

  return contentParts.join('');
};

type SingleShotMessageRequest = {
  staticSystemPrompt?: string;
  generationSpecificContext?: Record<string, any>;
  additionalUserPrompt?: string;
};
export const prepareSingleShotMessages = (
  request: SingleShotMessageRequest
) => {
  const messages: Message[] = [];
  if (request.staticSystemPrompt) {
    messages.push({
      role: 'system',
      content: request.staticSystemPrompt,
    });
  }
  if (request.generationSpecificContext) {
    // drop undefined values
    const filteredContext = Object.fromEntries(
      Object.entries(request.generationSpecificContext).filter(
        ([_, value]) => value !== undefined
      )
    );
    messages.push({
      role: 'user',
      content: JSON.stringify(filteredContext),
    });
  }
  if (request.additionalUserPrompt) {
    messages.push({
      role: 'user',
      content: request.additionalUserPrompt,
    });
  }
  return messages;
};

/**
 * Make a streaming chat completion request to the trace server.
 *
 * @param client The trace server client instance
 * @param entity The entity (organization) name
 * @param project The project name
 * @param params Chat completion parameters
 * @param onChunk Callback for each streaming chunk
 * @returns The complete response as a string
 */
const chatCompleteStream = async (
  client: TraceServerClient,
  entity: string,
  project: string,
  params: ChatCompletionParams,
  onChunk: (chunk: Chunk) => void,
  _dangerousExtraAttributesToLog?: Record<string, any>
): Promise<Completion> => {
  // Process raw chunks to extract content
  const processedChunks: unknown[] = [];

  const processChunk = (rawChunk: unknown) => {
    processedChunks.push(rawChunk);

    // Type guard for OpenAI-style chunks
    const isOpenAIChunk = (
      chunk: unknown
    ): chunk is {
      choices: Array<{
        delta: {
          content?: string;
        };
      }>;
    } => {
      return (
        typeof chunk === 'object' &&
        chunk !== null &&
        'choices' in chunk &&
        Array.isArray((chunk as any).choices) &&
        (chunk as any).choices.length > 0 &&
        'delta' in (chunk as any).choices[0]
      );
    };

    if (isOpenAIChunk(rawChunk)) {
      const content = rawChunk.choices[0]?.delta?.content;
      if (content) {
        onChunk({content});
      }
    } else if (
      typeof rawChunk === 'object' &&
      rawChunk !== null &&
      'content' in rawChunk
    ) {
      const content = (rawChunk as any).content;
      if (typeof content === 'string') {
        onChunk({content});
      }
    }
  };

  const args = {
    project_id: `${entity}/${project}`,
    inputs: {
      model: params.weavePlaygroundModelId, // prepareModel(params.weavePlaygroundModelId, params.modelProvider),
      messages: prepareMessages(params.messages),
      temperature: params.temperature || 0.7,
      response_format: prepareResponseFormat(params.responseFormat),
      tools: params.tools,
    },
  };
  await client.completionsCreateStream(
    {
      ...args,
      track_llm_call: false,
    },
    processChunk
  );

  const rawRes = combineChunks(processedChunks);
  let res: Completion;
  if (params.responseFormat) {
    if (
      'type' in params.responseFormat &&
      params.responseFormat.type === 'text'
    ) {
      res = rawRes;
    } else {
      res = JSON.parse(rawRes);
      if ('parse' in params.responseFormat && params.responseFormat.parse) {
        res = params.responseFormat.parse(res);
      }
    }
  } else {
    res = rawRes;
  }

  await dangerouslyLogCallToWeave(
    'chatCompletionStream',
    args,
    res,
    _dangerousExtraAttributesToLog
  );

  return res;
};

// Combined Magic Context
type MagicContextValue = {
  entity: string;
  project: string;
  selectedModel: string;
  setSelectedModel: (model: string) => void;
};

const MagicContext = createContext<MagicContextValue | undefined>(undefined);

export const useMagicContext = () => {
  const context = useContext(MagicContext);
  if (!context) {
    throw new Error('useMagicContext must be used within ChatClientProvider');
  }
  return context;
};

export const ChatClientProvider: React.FC<{
  value: EntityProject;
  children: React.ReactNode;
}> = ({value, children}) => {
  const client = useGetTraceServerClientContext()();
  const [selectedModel, setSelectedModel] = useState(DEFAULT_MODEL);

  if (!client) {
    throw new Error('No trace server client found');
  }

  const magicContextValue = useMemo(
    () => ({
      entity: value.entity,
      project: value.project,
      selectedModel,
      setSelectedModel,
    }),
    [value.entity, value.project, selectedModel]
  );

  return (
    <MagicContext.Provider value={magicContextValue}>
      {children}
    </MagicContext.Provider>
  );
};

export const useChatCompletionStream = (entityProject?: EntityProject) => {
  const magicContext = useMagicContext();
  const {entity, project} = useMemo(() => {
    if (entityProject) {
      return entityProject;
    }
    return {
      entity: magicContext.entity,
      project: magicContext.project,
    };
  }, [entityProject, magicContext]);
  const getClient = useGetTraceServerClientContext();
  return useCallback(
    (
      params: Omit<ChatCompletionParams, 'weavePlaygroundModelId'> & {
        weavePlaygroundModelId?: string;
      },
      onChunk: (chunk: Chunk) => void,
      _dangerousExtraAttributesToLog?: Record<string, any>
    ) => {
      const client = getClient();
      // Use selected model from context if not specified in params
      const weavePlaygroundModelId =
        params.weavePlaygroundModelId || magicContext.selectedModel;
      return chatCompleteStream(
        client,
        entity,
        project,
        {...params, weavePlaygroundModelId: weavePlaygroundModelId},
        onChunk,
        _dangerousExtraAttributesToLog
      );
    },
    [entity, project, getClient, magicContext.selectedModel]
  );
};
