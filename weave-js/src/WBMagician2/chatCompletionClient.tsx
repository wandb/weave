import {JSONSchema7} from 'json-schema';
import React, {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from 'react';

import {TraceServerClient} from '../components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/traceServerClient';
import {useGetTraceServerClientContext} from '../components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/traceServerClientContext';

const DEFAULT_MODEL = 'coreweave/moonshotai/Kimi-K2-Instruct';

export type Message = {
  role: 'user' | 'assistant' | 'system';
  content: string;
};

export type EntityProject = {
  entity: string;
  project: string;
};

export type Completion = string;

export type Chunk = {
  content: string;
};

export type ResponseFormat =
  | JsonSchemaResponseFormat
  | JsonObjectResponseFormat
  | TextResponseFormat;

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

export type JsonObjectResponseFormat = {
  type: 'json_object';
};
export type TextResponseFormat = {
  type: 'text';
};
export type JsonSchemaResponseFormat = {
  type: 'json_schema';
  json_schema: {
    name: string;
    strict?: boolean;
    schema: JSONSchema7;
  };
};

export type ChatCompletionParams = {
  // `modelId` is a string identifier for the model to use.
  //
  // A special case is a ref (a special weave/wandb URI) which
  // can refer to a specific version of a finetuned / saved model.
  modelId: string;
  // `modelProvider` refers to the provider of the model.
  // for example: `openai`, `anthropic`, etc...
  // Model provider is optional since many models
  // have unique providers (eg. `gpt-4o-mini` is provided by `openai`)
  //
  // Note: a special provider is `coreweave` which maps to the CoreWeave API.
  modelProvider?: string;
  // Prompts coming soon!
  // `promptId` is the id (ref) of a prompt to use
  // promptId?: string
  // `prompt` is the prompt to use
  // promptVariables?: Record<string, any>
  // `messages` is the messages to be sent to the model.
  messages: string | Array<Message>;
  // `responseFormat` is the format of the response.
  responseFormat?: ResponseFormat;
  // `temperature` is the temperature of the model.
  temperature?: number;
  // `tools` is the tools to use.
  tools?: Array<Tool>;
};

/**
 * Prepare the model identifier, handling provider-specific formatting.
 *
 * @param modelId The model identifier
 * @param modelProvider Optional provider name
 * @returns Formatted model string
 */
const prepareModel = (modelId: string, modelProvider?: string) => {
  if (modelProvider) {
    return `${modelProvider}/${modelId}`;
  }
  return modelId;
};

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
 * Extract the message content from various LLM provider response formats.
 *
 * @param response Raw response from the completion API
 * @returns The extracted message content as a string
 */
const extractMessageContent = (response: unknown): string => {
  // Type guard to check if response has expected OpenAI-like structure
  const isOpenAIResponse = (
    r: unknown
  ): r is {
    choices: Array<{
      message: {
        content: string;
        role: string;
      };
    }>;
  } => {
    return (
      typeof r === 'object' &&
      r !== null &&
      'choices' in r &&
      Array.isArray((r as any).choices) &&
      (r as any).choices.length > 0 &&
      'message' in (r as any).choices[0] &&
      'content' in (r as any).choices[0].message
    );
  };

  // Type guard for Anthropic-like response format
  const isAnthropicResponse = (
    r: unknown
  ): r is {
    content: Array<{
      type: string;
      text: string;
    }>;
  } => {
    return (
      typeof r === 'object' &&
      r !== null &&
      'content' in r &&
      Array.isArray((r as any).content) &&
      (r as any).content.length > 0 &&
      'text' in (r as any).content[0]
    );
  };

  // Type guard for simple content response
  const isSimpleContentResponse = (
    r: unknown
  ): r is {
    content: string;
  } => {
    return (
      typeof r === 'object' &&
      r !== null &&
      'content' in r &&
      typeof (r as any).content === 'string'
    );
  };

  // Try different response formats
  if (isOpenAIResponse(response)) {
    return response.choices[0].message.content;
  } else if (isAnthropicResponse(response)) {
    // Concatenate all text blocks for Anthropic
    return response.content
      .filter(block => block.type === 'text')
      .map(block => block.text)
      .join('');
  } else if (isSimpleContentResponse(response)) {
    return response.content;
  } else if (typeof response === 'string') {
    return response;
  }

  // Log the unknown format for debugging
  console.warn('Unknown completion response format:', response);

  // Last resort: try to stringify the response
  return JSON.stringify(response, null, 2);
};

/**
 * Prepare response format configuration for the API.
 * Currently not implemented as it depends on provider-specific requirements.
 *
 * @param responseFormat The desired response format
 * @returns Formatted response configuration
 */
const prepareResponseFormat = (
  responseFormat?: ResponseFormat
): {type: string} | undefined => {
  if (!responseFormat) {
    return undefined;
  }

  // For now, just pass through the response format
  // Different providers may need different formatting
  return responseFormat;
};

/**
 * Combine streaming chunks into a single completion response.
 *
 * @param chunks Array of streaming chunks
 * @returns Combined completion string
 */
const combineChunks = (chunks: unknown[]): Completion => {
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

/**
 * Make a chat completion request to the trace server.
 *
 * @param client The trace server client instance
 * @param entity The entity (organization) name
 * @param project The project name
 * @param params Chat completion parameters
 * @returns The completion response as a string
 */
const chatComplete = async (
  client: TraceServerClient,
  entity: string,
  project: string,
  params: ChatCompletionParams
): Promise<Completion> => {
  const res = await client.completionsCreate({
    project_id: `${entity}/${project}`,
    inputs: {
      model: prepareModel(params.modelId, params.modelProvider),
      messages: prepareMessages(params.messages),
      temperature: params.temperature || 0.7,
      response_format: prepareResponseFormat(params.responseFormat),
      tools: params.tools,
    },
    track_llm_call: false,
  });

  // Extract the message content from the response
  return extractMessageContent(res.response);
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
  onChunk: (chunk: Chunk) => void
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

  await client.completionsCreateStream(
    {
      project_id: `${entity}/${project}`,
      inputs: {
        model: prepareModel(params.modelId, params.modelProvider),
        messages: prepareMessages(params.messages),
        temperature: params.temperature || 0.7,
        response_format: prepareResponseFormat(params.responseFormat),
        tools: params.tools,
      },
      track_llm_call: false,
    },
    processChunk
  );

  return combineChunks(processedChunks);
};

const EntityProjectContext = createContext<EntityProject | undefined>(
  undefined
);

const SelectedModelContext = createContext<
  | {
      selectedModel: string;
      setSelectedModel: (model: string) => void;
    }
  | undefined
>(undefined);

const useEntityProjectContext = () => {
  return useContext(EntityProjectContext);
};

const useSelectedModelContext = () => {
  const context = useContext(SelectedModelContext);
  if (!context) {
    throw new Error(
      'useSelectedModelContext must be used within ChatClientProvider'
    );
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

  return (
    <EntityProjectContext.Provider value={value}>
      <SelectedModelContext.Provider value={{selectedModel, setSelectedModel}}>
        {children}
      </SelectedModelContext.Provider>
    </EntityProjectContext.Provider>
  );
};

export const useSelectedModel = () => {
  const {selectedModel, setSelectedModel} = useSelectedModelContext();
  return {selectedModel, setSelectedModel};
};

export const useChatCompletion = (entityProject?: EntityProject) => {
  const entityProjectContext = useEntityProjectContext();
  const {selectedModel} = useSelectedModelContext();
  const {entity, project} = useMemo(() => {
    if (entityProject) {
      return entityProject;
    }
    if (entityProjectContext) {
      return entityProjectContext;
    }
    throw new Error('No entity project found');
  }, [entityProject, entityProjectContext]);
  const getClient = useGetTraceServerClientContext();
  return useCallback(
    (params: ChatCompletionParams) => {
      const client = getClient();
      // Use selected model from context if not specified in params
      const modelId = params.modelId || selectedModel;
      return chatComplete(client, entity, project, {...params, modelId});
    },
    [entity, project, getClient, selectedModel]
  );
};

export const useChatCompletionStream = (entityProject?: EntityProject) => {
  const entityProjectContext = useEntityProjectContext();
  const {selectedModel} = useSelectedModelContext();
  const {entity, project} = useMemo(() => {
    if (entityProject) {
      return entityProject;
    }
    if (entityProjectContext) {
      return entityProjectContext;
    }
    throw new Error('No entity project found');
  }, [entityProject, entityProjectContext]);
  const getClient = useGetTraceServerClientContext();
  return useCallback(
    (params: ChatCompletionParams, onChunk: (chunk: Chunk) => void) => {
      const client = getClient();
      // Use selected model from context if not specified in params
      const modelId = params.modelId || selectedModel;
      return chatCompleteStream(
        client,
        entity,
        project,
        {...params, modelId},
        onChunk
      );
    },
    [entity, project, getClient, selectedModel]
  );
};

// NOT CURRENTLY USED
// import {useLLMDropdownOptions} from '../components/PagePanelComponents/Home/Browse3/pages/PlaygroundPage/PlaygroundChat/LLMDropdownOptions';
// import {useConfiguredProviders} from '../components/PagePanelComponents/Home/Browse3/pages/PlaygroundPage/useConfiguredProviders';
// import {useBaseObjectInstances} from '../components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/objectClassQuery';
// /**
//  * Hook to get available models for the current entity/project.
//  * Returns a list of model options that can be used for completions.
//  *
//  * @param entityProject Optional entity/project override
//  * @returns List of available models
//  */
// export const useAvailableModels = (
//   entityProject?: EntityProject
// ): Array<{id: string; name: string; provider: string}> => {
//   const entityProjectContext = useEntityProjectContext();
//   const {entity, project} = useMemo(() => {
//     if (entityProject) {
//       return entityProject;
//     }
//     if (entityProjectContext) {
//       return entityProjectContext;
//     }
//     return {entity: '', project: ''};
//   }, [entityProject, entityProjectContext]);

//   const projectId = entity && project ? `${entity}/${project}` : null;

//   // Get configured providers
//   const {result: configuredProviders, loading: configuredProvidersLoading} =
//     useConfiguredProviders(entity);

//   // Get custom providers and models
//   const {result: customProvidersResult, loading: customProvidersLoading} =
//     useBaseObjectInstances('Provider', {
//       project_id: projectId || '',
//       filter: {
//         latest_only: true,
//       },
//     });

//   const {
//     result: customProviderModelsResult,
//     loading: customProviderModelsLoading,
//   } = useBaseObjectInstances('ProviderModel', {
//     project_id: projectId || '',
//     filter: {
//       latest_only: true,
//     },
//   });

//   // Get saved models
//   // Disallow saved models for now here
//   // const {result: savedModelsResult, loading: savedModelsLoading} =
//   //   useLeafObjectInstances('LLMStructuredCompletionModel', {
//   //     project_id: projectId || '',
//   //   });

//   // Get dropdown options
//   const llmDropdownOptions = useLLMDropdownOptions(
//     configuredProviders || {},
//     configuredProvidersLoading,
//     customProvidersResult || [],
//     customProviderModelsResult || [],
//     customProvidersLoading || customProviderModelsLoading,
//     [],
//     false
//     // savedModelsResult || [],
//     // savedModelsLoading
//   );

//   // Transform dropdown options to our simpler format
//   return useMemo(() => {
//     const models: Array<{id: string; name: string; provider: string}> = [];

//     llmDropdownOptions.forEach(providerOption => {
//       if (providerOption.llms) {
//         providerOption.llms.forEach(llm => {
//           models.push({
//             id: llm.value,
//             name: llm.label as string,
//             provider: providerOption.label as string,
//           });
//         });
//       }

//       // Handle nested providers (for saved models)
//       if (providerOption.providers) {
//         providerOption.providers.forEach(nestedProvider => {
//           if (nestedProvider.llms) {
//             nestedProvider.llms.forEach(llm => {
//               models.push({
//                 id: llm.value,
//                 name: llm.label as string,
//                 provider: nestedProvider.label as string,
//               });
//             });
//           }
//         });
//       }
//     });

//     console.log('models', models);

//     return models;
//   }, [llmDropdownOptions]);
// };
