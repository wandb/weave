import _ from 'lodash';

import {
  KeyedDictType,
  TraceCallSchema,
} from '../../wfReactInterface/traceServerClientTypes';
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
    content: string;
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
    generations: Array<Array<{
      text: string;
      generation_info: {
        finish_reason: string;
        logprobs: null;
      };
      type: string;
      message: LangchainMessage;
    }>>;
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
  const content = lcMessage.kwargs.content;

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
      content: content || undefined,
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

export const isTraceCallChatFormatLangchain = (
  call: TraceCallSchema
): boolean => {
  if (!call.inputs || !('messages' in call.inputs)) {
    return false;
  }

  const {messages} = call.inputs;
  if (!_.isArray(messages) || messages.length === 0) {
    return false;
  }

  const firstMessages = messages[0];
  if (!_.isArray(firstMessages)) {
    return false;
  }

  return firstMessages.every(isLangchainMessage);
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
  if (!request.messages || !_.isArray(request.messages) || request.messages.length === 0) {
    return {
      model: 'unknown',
      messages: [],
    };
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

  if (request.messages && _.isArray(request.messages) && request.messages.length > 0) {
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
    finish_reason: firstGeneration.generation_info.finish_reason,
  };

  const usage: Usage = firstOutput.llm_output.token_usage || {
    completion_tokens: 0,
    prompt_tokens: 0,
    total_tokens: 0,
  };

  return {
    id: firstOutput.llm_output.id || langchainOutput.id,
    choices: [choice],
    created: new Date(langchainOutput.start_time).getTime() / 1000,
    model: firstOutput.llm_output.model_name || 'unknown',
    system_fingerprint: firstOutput.llm_output.system_fingerprint || '',
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
