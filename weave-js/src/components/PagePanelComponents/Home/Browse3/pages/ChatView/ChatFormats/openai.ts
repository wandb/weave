import _ from 'lodash';
import { isArray } from 'util';

import {KeyedDictType, TraceCallSchema} from '../../wfReactInterface/traceServerClientTypes';
import { Message, Usage, ChatCompletion, Choice, InternalMessage, ChatRequest } from '../types';
import {hasStringProp, isMessage} from './utils';

const isOAIReponseRequest = (value: KeyedDictType): value is OpenAIResponseRequest => {
  const hasAttributes = 'input' in value && 'model' in value;
  if (!hasAttributes) { return false }

  const input = value['input'];
  return _.isString(value['input']) || (_.isArray(input));
}

interface OpenAIResponseRequest {
  input: string | Message[]
  model: string
  instructions?: string
}
interface ResponseOutputText {
  annotations: any[];
  text: string;
  type: string;
}

interface ResponseOutputMessage {
  id: string;
  content: ResponseOutputText[];
  role: string;
  type: string;
}

interface OpenAIResponseResult {
  id: string
  model: string
  output: ResponseOutputMessage[];
  usage: Usage
  created_at: number
  instructions?: string
}

export const responseOutputMessagesToChoices = (messages: ResponseOutputMessage[]): Choice[] => {
  let message = messages[0];
  // TODO: We need a real mapping here. output_text is fine to assign to text but others may not be
  message.content = message.content.map(content => {
    let vals = content
    vals['type'] = 'text'
    return vals
  })
  return [{
    index: 0,
    message: message,
    finish_reason: 'stop'
  }]
}

export const normalizeOAIReponsesResult = (result: OpenAIResponseResult): ChatCompletion => {
  const choices = responseOutputMessagesToChoices(result.output)
  return {
    id: result.id,
    model: result.model,
    created: result.created_at,
    usage: result.usage,
    choices,
    system_fingerprint: "",
  }
}
export const normalizeOAIResponsesRequest = (request: any): ChatRequest => {
  const messages: Message[] = request['input']
  if ('instructions' in request) {
    return {
      messages: [
        {
          role: 'system',
          content: request['instructions']
        },
        ...messages
      ],
      model: request['model'],
    }
  }
  return {
    messages,
    model: request['model'],
  }
}
export const isTraceCallChatFormatOAIResponses = (call: TraceCallSchema): boolean => {

  return isTraceCallChatFormatOAIResponsesRequest(call.inputs);
};

export const isTraceCallChatFormatOAIResponsesResult= (result: any): boolean => {
  return ('object' in result && result['object'] == 'response')
};

export const isTraceCallChatFormatOAIResponsesRequest= (request: any): boolean => {
  return isOAIReponseRequest(request)
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
