import _ from 'lodash';

import {TraceCallSchema} from '../../wfReactInterface/traceServerClientTypes';
import {
  ChatCompletion,
  ChatRequest,
  Choice,
  Message,
  ToolCall,
  Usage,
} from '../types';
import {hasStringProp} from './utils';

interface LangchainMessage {
  lc: number;
  type: 'constructor';
  id: string[];
  kwargs: {
    content:
      | string
      | Array<{
          type: string;
          text?: string;
          id?: string;
          input?: any;
          name?: string;
        }>;
    type: string;
    tool_call_id?: string;
    status?: string;
    additional_kwargs?: {
      tool_calls?: Array<{
        id: string;
        function: {
          arguments: string;
          name: string;
        };
        type: string;
      }>;
      refusal?: null;
    };
    response_metadata?: {
      token_usage?: {
        completion_tokens: number;
        prompt_tokens: number;
        total_tokens: number;
        completion_tokens_details?: any;
        prompt_tokens_details?: any;
      };
      model_name?: string;
      system_fingerprint?: string;
      id?: string;
      service_tier?: string;
      finish_reason?: string;
      logprobs?: null;
    };
    tool_calls?: Array<{
      name: string;
      args: any;
      id: string;
      type: string;
    }>;
    usage_metadata?: {
      input_tokens: number;
      output_tokens: number;
      total_tokens: number;
      input_token_details?: any;
      output_token_details?: any;
    };
    invalid_tool_calls?: any[];
  };
}

interface LangchainOutput {
  id: string;
  name: string;
  start_time: string;
  run_type: string;
  end_time: string;
  extra: {
    invocation_params: any;
    options: any;
    batch_size: number;
    metadata: any;
  };
  outputs: Array<{
    generations: Array<
      Array<{
        text: string;
        generation_info?: {
          finish_reason: string;
          logprobs: null;
        };
        type: string;
        message: LangchainMessage;
      }>
    >;
    llm_output: {
      token_usage: {
        completion_tokens: number;
        prompt_tokens: number;
        total_tokens: number;
        completion_tokens_details?: any;
        prompt_tokens_details?: any;
      };
      model_name: string;
      system_fingerprint: string;
      id: string;
      service_tier: string;
    };
    run: null;
    type: string;
  }>;
}

const langchainMessageToMessage = (lcMessage: LangchainMessage): Message => {
  const role = getLangchainMessageRole(lcMessage);
  let content: string | undefined = undefined;

  // Handle Anthropic's array content format
  if (Array.isArray(lcMessage.kwargs.content)) {
    // Extract only the text content, ignoring tool_use blocks
    const textContent = lcMessage.kwargs.content
      .filter((item: any) => item.type === 'text')
      .map((item: any) => item.text)
      .join('');
    content = textContent || undefined;
  } else if (typeof lcMessage.kwargs.content === 'string') {
    content = lcMessage.kwargs.content;
  }

  if (lcMessage.kwargs.tool_call_id) {
    return {
      role: 'tool',
      content,
      tool_call_id: lcMessage.kwargs.tool_call_id,
    };
  }

  if (lcMessage.kwargs.tool_calls && lcMessage.kwargs.tool_calls.length > 0) {
    const toolCalls: ToolCall[] = lcMessage.kwargs.tool_calls.map(tc => ({
      id: tc.id,
      type: tc.type || 'function',
      function: {
        name: tc.name,
        arguments: JSON.stringify(tc.args),
      },
    }));

    return {
      role,
      content,
      tool_calls: toolCalls,
    };
  }

  return {
    role,
    content,
  };
};

const getLangchainMessageRole = (lcMessage: LangchainMessage): string => {
  const messageType = lcMessage.id[lcMessage.id.length - 1];

  if (messageType === 'SystemMessage') {
    return 'system';
  } else if (messageType === 'HumanMessage') {
    return 'user';
  } else if (messageType === 'AIMessage') {
    return 'assistant';
  } else if (messageType === 'ToolMessage') {
    return 'tool';
  }

  return lcMessage.kwargs.type || 'assistant';
};

export const isChatRequestFormatLangchain = (request: any) => {
  if (!request || !('messages' in request)) {
    return false;
  }

  const {messages} = request;
  if (!_.isArray(messages) || messages.length === 0) {
    return false;
  }

  const firstMessages = messages[0];
  if (!_.isArray(firstMessages)) {
    return false;
  }

  return firstMessages.every(isLangchainMessage);
};
export const isTraceCallChatFormatLangchain = (
  call: TraceCallSchema
): boolean => {
  if (!call.inputs) {
    return false;
  }
  const validInput = isChatRequestFormatLangchain(call.inputs);
  const validOutput = isLangchainOutput(call.output);
  return validInput && validOutput;
};

const isLangchainMessage = (message: any): boolean => {
  if (!_.isPlainObject(message)) {
    return false;
  }

  if (!('lc' in message) || !_.isNumber(message.lc)) {
    return false;
  }

  if (!hasStringProp(message, 'type') || message.type !== 'constructor') {
    return false;
  }

  if (!('id' in message) || !_.isArray(message.id)) {
    return false;
  }

  if (!('kwargs' in message) || !_.isPlainObject(message.kwargs)) {
    return false;
  }

  return true;
};

export const normalizeLangchainChatRequest = (request: any): ChatRequest => {
  if (
    !request.messages ||
    !_.isArray(request.messages) ||
    request.messages.length === 0
  ) {
    throw new Error(
      'Error: Input Messages missing or empty. ChatView will be hidden'
    );
  }

  const firstMessages = request.messages[0];
  if (!_.isArray(firstMessages)) {
    return {
      model: 'unknown',
      messages: [],
    };
  }

  const messages: Message[] = firstMessages.map(langchainMessageToMessage);

  const model = extractModelFromRequest(request);

  return {
    model,
    messages,
  };
};

const extractModelFromRequest = (request: any): string => {
  if (request.model && _.isString(request.model)) {
    return request.model;
  }

  if (
    request.messages &&
    _.isArray(request.messages) &&
    request.messages.length > 0
  ) {
    const firstMessages = request.messages[0];
    if (_.isArray(firstMessages)) {
      for (const msg of firstMessages) {
        if (msg.kwargs?.response_metadata?.model_name) {
          return msg.kwargs.response_metadata.model_name;
        }
      }
    }
  }

  return 'unknown';
};

export const normalizeLangchainChatCompletion = (
  output: any
): ChatCompletion => {
  if (!isLangchainOutput(output)) {
    return {
      id: 'unknown',
      choices: [],
      created: 0,
      model: 'unknown',
      system_fingerprint: '',
      usage: {
        completion_tokens: 0,
        prompt_tokens: 0,
        total_tokens: 0,
      },
    };
  }

  const langchainOutput = output as LangchainOutput;
  const firstOutput = langchainOutput.outputs[0];
  const firstGeneration = firstOutput.generations[0][0];
  const message = langchainMessageToMessage(firstGeneration.message);

  const choice: Choice = {
    index: 0,
    message,
    finish_reason: firstGeneration?.generation_info?.finish_reason ?? '',
  };

  let usage: Usage = {
    completion_tokens: 0,
    prompt_tokens: 0,
    total_tokens: 0,
  };

  // Handle standard format (OpenAI-like)
  if (firstOutput.llm_output?.token_usage) {
    usage = firstOutput.llm_output.token_usage;
  }
  // Handle VertexAI format
  else if (firstGeneration.message?.kwargs?.usage_metadata) {
    const usageMetadata = firstGeneration.message.kwargs.usage_metadata;
    usage = {
      completion_tokens: usageMetadata.output_tokens || 0,
      prompt_tokens: usageMetadata.input_tokens || 0,
      total_tokens: usageMetadata.total_tokens || 0,
    };
  }

  // Extract model name from multiple possible locations
  const modelName =
    firstOutput.llm_output?.model_name ||
    firstGeneration.message?.kwargs?.response_metadata?.model_name ||
    'unknown';

  // Extract ID from multiple possible locations
  const id =
    firstOutput.llm_output?.id ||
    firstGeneration.message?.kwargs?.response_metadata?.id ||
    langchainOutput.id;

  // Extract system fingerprint if available
  const systemFingerprint =
    firstOutput.llm_output?.system_fingerprint ||
    firstGeneration.message?.kwargs?.response_metadata?.system_fingerprint ||
    '';

  return {
    id,
    choices: [choice],
    created: new Date(langchainOutput.start_time).getTime() / 1000,
    model: modelName,
    system_fingerprint: systemFingerprint,
    usage,
  };
};

const isLangchainOutput = (output: any): boolean => {
  if (!_.isPlainObject(output)) {
    return false;
  }

  if (!hasStringProp(output, 'id')) {
    return false;
  }

  if (!hasStringProp(output, 'name')) {
    return false;
  }

  if (!hasStringProp(output, 'run_type')) {
    return false;
  }

  if (!('outputs' in output) || !_.isArray(output.outputs)) {
    return false;
  }

  return true;
};
