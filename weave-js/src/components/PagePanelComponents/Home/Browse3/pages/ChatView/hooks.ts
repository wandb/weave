import _ from 'lodash';

import {isWeaveRef} from '../../filters/common';
import {mapObject, traverse, TraverseContext} from '../CallPage/traverse';
import {useWFHooks} from '../wfReactInterface/context';
import {TraceCallSchema} from '../wfReactInterface/traceServerClientTypes';
import {ChatCompletion, ChatRequest} from './types';
import {is} from 'immer/dist/internal';

const isStructuredOutputCall = (call: TraceCallSchema): boolean => {
  const {response_format} = call.inputs;
  if (!response_format || !_.isPlainObject(response_format)) {
    return false;
  }
  if (response_format.type !== 'json_schema') {
    return false;
  }
  if (
    !response_format.json_schema ||
    !_.isPlainObject(response_format.json_schema)
  ) {
    return false;
  }
  return true;
};

// Traverse input and outputs looking for any ref strings.
const getRefs = (call: TraceCallSchema): string[] => {
  const refs = new Set<string>();
  traverse(call.inputs, (context: TraverseContext) => {
    if (isWeaveRef(context.value)) {
      refs.add(context.value);
    }
  });
  traverse(call.output, (context: TraverseContext) => {
    if (isWeaveRef(context.value)) {
      refs.add(context.value);
    }
  });
  return Array.from(refs);
};

// Replace all ref strings with the actual data.
const deref = (object: any, refsMap: Record<string, any>): any => {
  if (isWeaveRef(object)) {
    return refsMap[object] ?? object;
  }
  const mapper = (context: TraverseContext) => {
    if (context.valueType === 'string' && isWeaveRef(context.value)) {
      return refsMap[context.value] ?? context.value;
    }
    return context.value;
  };
  return mapObject(object, mapper);
};

// Memoize the call as chat
export const useCallAsChat = (
  call: TraceCallSchema
): {
  loading: boolean;
  isStructuredOutput: boolean;
  request: ChatRequest;
  result: ChatCompletion | null;
  values: Record<string, any>;
} => {
  // Traverse the data and find all ref URIs.
  const refs = getRefs(call);
  const {useRefsData} = useWFHooks();
  const refsData = useRefsData(refs);
  const refsMap = _.zipObject(refs, refsData.result ?? []);
  const dereffed = deref(call.inputs, refsMap);
  // TODO: Might be better if lower levels could handle the prompt
  if (dereffed.messages._class_name === 'Prompt') {
    dereffed.messages = dereffed.messages.data;
  }
  const request = dereffed as ChatRequest;
  const result = call.output
    ? (deref(call.output, refsMap) as ChatCompletion)
    : null;

  // TODO: It is possible that all of the choices are refs again, handle this better.
  if (
    result &&
    result.choices &&
    result.choices.some(choice => isWeaveRef(choice))
  ) {
    result.choices = [];
  }

  const values = call.attributes?.weave?.prompt_values ?? {};

  return {
    loading: refsData.loading,
    isStructuredOutput: isStructuredOutputCall(call),
    request,
    result,
    values,
  };
};
