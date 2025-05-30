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
  Usage,
  ToolCall,
} from '../types';
import {hasStringProp, isMessage} from './utils';

const isOAIReponseRequest = (
  value: KeyedDictType
): value is OpenAIResponseRequest => {
  const hasAttributes = 'input' in value && 'model' in value;
  if (!hasAttributes) {
    return false;
  }

  const input = value['input'];
  return _.isString(value['input']) || _.isArray(input);
};

interface OpenAIResponseRequest {
  input: string | Message[];
  model: string;
  instructions?: string;
}

interface ResponseUserMessage {
  role: "user"
  content: string;
}
interface ResponseOutputText {
  annotations: any[];
  text: string;
  type: string;
}

interface ResponseMessage {
  id: string;
  content: ResponseOutputText[];
  role: string;
  type: "message";
}

interface ResponseFunctionCall {
  arguments: string,
  call_id: string,
  id: string,
  name: string
  status: string
  type: "function_call"
}

interface ResponseFunctionCallOutput {
  type: "function_call_output",
  call_id: string,
  output: any
};

type OpenAIResponseMessage = ResponseFunctionCall | ResponseMessage | ResponseFunctionCallOutput;

interface OpenAIResponseResult {
  id: string;
  model: string;
  output: ResponseFunctionCall[];
  tools: ResponseFunctionCall[]
  usage: Usage;
  created_at: number;
  instructions?: string;
}

const responseFunctionCallToToolCall = (
  functionCall: ResponseFunctionCall
): ToolCall => {
  return {
    id: functionCall.id,
    type: functionCall.type,
    function: {
      name: functionCall.name,
      arguments: functionCall.arguments,
    },
  }
};

export const responseMessageToMessage = (message: OpenAIResponseMessage): Message | undefined => {
  if (message['type'] == 'function_call') {
    return {
      role: 'assistant',
      tool_calls: [responseFunctionCallToToolCall(message)],
    }
  } else if (message['type'] == 'function_call_output') {
    return {
      role: 'assistant',
      content: message.output,
      tool_call_id: message.call_id
    }
  } else if (message['type'] == 'message') {
    const output =  message.content.find(msg => { return msg['type'] == 'output_text' })
    if (!output) {
      console.error("Failed to parse output_text from message");
      return undefined;
    }
    return {
      role: message.role,
      content: output.text
    }
  }
  return undefined
}
export const responseOutputMessagesToChoices = (
  messages: OpenAIResponseMessage[]
): Choice[] => {
  // Look for nested output text here
  return messages.map((message, index) => {
    return {
      index,
      finish_reason: 'stop',
      message: responseMessageToMessage(message) ?? { role: 'assistant', content: '' }
    }
  })
};

export const normalizeOAIReponsesResult = (
  result: OpenAIResponseResult
): ChatCompletion => {
  const choices = responseOutputMessagesToChoices(result.output);
  console.log(choices)
  return {
    id: result.id,
    model: result.model,
    created: result.created_at,
    usage: result.usage,
    choices,
    system_fingerprint: '',
  };
};
export const normalizeOAIResponsesRequest = (request: any): ChatRequest => {
  const messages: Message[] = request['input'].map((msg: ResponseUserMessage | OpenAIResponseMessage) => {
    if('type' in msg) { return responseMessageToMessage(msg) }
    return msg;
  });
  if ('instructions' in request) {
    return {
      messages: [
        {
          role: 'system',
          content: request['instructions'],
        },
        ...messages,
      ],
      model: request['model'],
    };
  }
  return {
    messages,
    model: request['model'],
  };
};
export const isTraceCallChatFormatOAIResponses = (
  call: TraceCallSchema
): boolean => {
  return isTraceCallChatFormatOAIResponsesRequest(call.inputs);
};

export const isTraceCallChatFormatOAIResponsesResult = (
  result: any
): boolean => {
  return 'object' in result && result['object'] == 'response';
};

export const isTraceCallChatFormatOAIResponsesRequest = (
  request: any
): boolean => {
  return isOAIReponseRequest(request);
};

export const isTraceCallChatFormatOpenAI = (call: TraceCallSchema): boolean => {
  // TODO: This is probably not a good enough check
  // We should do legitimate schema validation on this
  if (!('messages' in call.inputs || 'input' in call.inputs)) {
    return false;
  }
  const {messages} = call.inputs;
  if (!_.isArray(messages)) {
    return false;
  }
  if (
    hasStringProp(call.inputs, 'model') &&
    call.inputs.model.toLowerCase().includes('mistral')
  ) {
    return false;
  }
  return messages.every(isMessage);
};
