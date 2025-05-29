import _ from 'lodash';

import {TraceCallSchema} from '../../wfReactInterface/traceServerClientTypes';
import {hasStringProp, isMessage} from './utils';

export const isTraceCallChatFormatOpenAI = (call: TraceCallSchema): boolean => {
  if (!('messages' in call.inputs)) {
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
