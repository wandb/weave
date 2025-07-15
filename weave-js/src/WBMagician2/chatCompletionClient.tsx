import {JSONSchema7} from 'json-schema';
import React, {createContext, useCallback, useContext, useMemo} from 'react';

import {TraceServerClient} from '../components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/traceServerClient';
import {useGetTraceServerClientContext} from '../components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/traceServerClientContext';

export type Message = {
  role: 'user' | 'assistant' | 'system';
  content: string;
};

type JsonSchemaResponseFormat = {
  type: 'json_schema';
  jsonSchema: JSONSchema7;
};

type JsonObjectResponseFormat = {
  type: 'json_object';
};

type TextResponseFormat = {
  type: 'text';
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

type Chunk = unknown;

type Completion = unknown;

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

const prepareModel = (modelId: string, modelProvider?: string) => {
  if (modelProvider) {
    return `${modelProvider}/${modelId}`;
  }
  return modelId;
};

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

const prepareResponse = (response: Completion): unknown => {
  return response.choices[0].message.content;
};

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
      response_format: params.responseFormat,
      tools: params.tools,
    },
    track_llm_call: false,
  });

  return prepareResponse(res.response);
};

const combineChunks = (chunks: Array<Chunk>): Completion => {
  console.log('chunks', chunks);

  throw new Error('Not implemented');
};

const chatCompleteStream = async (
  client: TraceServerClient,
  entity: string,
  project: string,
  params: ChatCompletionParams,
  onChunk: (chunk: Chunk) => void
): Promise<Completion> => {
  const res = await client.completionsCreateStream(
    {
      project_id: `${entity}/${project}`,
      inputs: {
        model: prepareModel(params.modelId, params.modelProvider),
        messages: prepareMessages(params.messages),
        temperature: params.temperature || 0.7,
        response_format: params.responseFormat,
        tools: params.tools,
      },
      track_llm_call: false,
    },
    onChunk
  );

  return combineChunks(res.chunks);
};

export type EntityProject = {
  entity: string;
  project: string;
};

const EntityProjectContext = createContext<EntityProject | undefined>(
  undefined
);

const useEntityProjectContext = () => {
  return useContext(EntityProjectContext);
};

export const ChatClientProvider: React.FC<{
  value: EntityProject;
  children: React.ReactNode;
}> = ({value, children}) => {
  const client = useGetTraceServerClientContext()();
  if (!client) {
    throw new Error('No trace server client found');
  }
  return (
    <EntityProjectContext.Provider value={value}>
      {children}
    </EntityProjectContext.Provider>
  );
};

export const useChatCompletion = (entityProject?: EntityProject) => {
  const entityProjectContext = useEntityProjectContext();
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
      return chatComplete(client, entity, project, params);
    },
    [entity, project, getClient]
  );
};

export const useChatCompletionStream = (entity: string, project: string) => {
  const getClient = useGetTraceServerClientContext();
  return useCallback(
    (params: ChatCompletionParams, onChunk: (chunk: Chunk) => void) => {
      const client = getClient();
      return chatCompleteStream(client, entity, project, params, onChunk);
    },
    [entity, project, getClient]
  );
};
