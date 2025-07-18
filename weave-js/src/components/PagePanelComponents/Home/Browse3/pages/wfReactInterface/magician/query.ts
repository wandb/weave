import _ from 'lodash';
import {useCallback, useMemo} from 'react';
import z from 'zod';
import {zodToJsonSchema} from 'zod-to-json-schema';

import {TraceServerClient} from '../traceServerClient';
import {useGetTraceServerClientContext} from '../traceServerClientContext';
import {useMagicContext} from './context';
import {dangerouslyLogCallToWeave} from './magicianWeaveLogger';
import {
  ChatCompletionParams,
  Chunk,
  Completion,
  CompletionResponseFormat,
  EntityProject,
  Message,
  SingleShotMessageRequest,
} from './types';
import {extractChunkContent, filterUndefined, isResponseFormat} from './utils';

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
 *
 * @param responseFormat The desired response format
 * @returns Formatted response configuration
 */
const prepareResponseFormat = (
  responseFormat?: CompletionResponseFormat
): any => {
  if (!responseFormat) {
    return undefined;
  }

  if (isResponseFormat(responseFormat)) {
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

  const contentParts: string[] = [];

  for (const chunk of chunks) {
    const content = extractChunkContent(chunk);
    if (content) {
      contentParts.push(content);
    }
  }

  return contentParts.join('');
};

/**
 * Prepare single-shot messages from a request object using a standard convention.
 *
 * This utility creates a properly formatted messages array for LLM completions
 * following a consistent pattern: system prompt → context → user message.
 */
export const prepareSingleShotMessages = (
  request: SingleShotMessageRequest
): Message[] => {
  const messages: Message[] = [];
  if (request.staticSystemPrompt) {
    messages.push({
      role: 'system',
      content: request.staticSystemPrompt,
    });
  }
  if (request.generationSpecificContext) {
    const filteredContext = filterUndefined(request.generationSpecificContext);
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
 * @param signal Optional AbortSignal for cancellation
 * @returns The complete response as a string
 */
const chatCompleteStream = async (
  client: TraceServerClient,
  entity: string,
  project: string,
  params: ChatCompletionParams,
  onChunk: (chunk: Chunk) => void,
  _dangerousExtraAttributesToLog?: Record<string, any>,
  signal?: AbortSignal
): Promise<Completion> => {
  // Process raw chunks to extract content
  const processedChunks: unknown[] = [];

  const processChunk = (rawChunk: unknown) => {
    // Check for cancellation
    if (signal?.aborted) {
      return;
    }

    processedChunks.push(rawChunk);

    const content = extractChunkContent(rawChunk);
    if (content) {
      onChunk({content});
    }
  };

  const args = {
    project_id: `${entity}/${project}`,
    inputs: {
      model: params.weavePlaygroundModelId,
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
      isResponseFormat(params.responseFormat) &&
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
    'magic' +
      (_dangerousExtraAttributesToLog?.feature
        ? `_${_dangerousExtraAttributesToLog.feature}`
        : ''),
    args,
    res,
    _dangerousExtraAttributesToLog
  );

  return res;
};

/**
 * Hook for making streaming chat completion requests.
 *
 * Returns a function that can be used to make streaming chat completion requests.
 * Uses the selected model from context unless overridden in params.
 * ```
 */
export const useChatCompletionStream = (entityProject?: EntityProject) => {
  const {entity, project, selectedModel} = useMagicContext();
  const {entity: finalEntity, project: finalProject} = useMemo(() => {
    if (entityProject) {
      return entityProject;
    }
    return {
      entity,
      project,
    };
  }, [entityProject, entity, project]);
  const getClient = useGetTraceServerClientContext();

  return useCallback(
    (
      params: Omit<ChatCompletionParams, 'weavePlaygroundModelId'> & {
        weavePlaygroundModelId?: string;
      },
      onChunk: (chunk: Chunk) => void,
      _dangerousExtraAttributesToLog?: Record<string, any>,
      signal?: AbortSignal
    ) => {
      const client = getClient();
      // Use selected model from context if not specified in params
      const weavePlaygroundModelId =
        params.weavePlaygroundModelId || selectedModel;
      return chatCompleteStream(
        client,
        finalEntity,
        finalProject,
        {...params, weavePlaygroundModelId: weavePlaygroundModelId},
        onChunk,
        _dangerousExtraAttributesToLog,
        signal
      );
    },
    [finalEntity, finalProject, getClient, selectedModel]
  );
};
