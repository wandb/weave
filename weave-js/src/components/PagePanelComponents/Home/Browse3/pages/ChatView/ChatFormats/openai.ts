import _ from 'lodash';
import { isArray } from 'util';

import {KeyedDictType, TraceCallSchema} from '../../wfReactInterface/traceServerClientTypes';
import { Message, Usage, ChatCompletion, Choice } from '../types';
import {hasStringProp, isMessage} from './utils';

const isOAIReponseRequest = (value: KeyedDictType): value is OpenAIResponseRequest => {
  const hasAttributes = 'input' in value && 'model' in value;
  if (!hasAttributes) { return false }

  const input = value['input'];
  return _.isString(value['input']) || (_.isArray(input) && input.every(isMessage));
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
  type: "message";
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
  // const choice = messages[0]
  // return [{
  //   index: 0,
  //   message: {
  //     role: choice.role,
  //     tool
  //   },
  //   finish_reason: 'stop'
  // }]
}
export const normalizeOAIReponsesResult = (result: OpenAIResponseResult): ChatCompletion => {
  const {id, model, created_at: created, usage} = result;
  const choices = responseOutputMessagesToChoices(result.output)
  return {
    id,
    model,
    created,
    usage,
    choices,
    system_fingerprint: "",
  }
}
export const isTraceCallChatFormatOAIResponses = (call: TraceCallSchema): boolean => {
  const result = isOAIReponseRequest(call.inputs) && isMessage(call.output)
  return result
};

export const isTraceCallChatFormatOpenAI = (call: TraceCallSchema): boolean => {
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
