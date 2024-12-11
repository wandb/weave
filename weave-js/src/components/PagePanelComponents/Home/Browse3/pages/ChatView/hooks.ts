import _ from 'lodash';

import {isWeaveRef} from '../../filters/common';
import {mapObject, traverse, TraverseContext} from '../CallPage/traverse';
import {useWFHooks} from '../wfReactInterface/context';
import {
  KeyedDictType,
  TraceCallSchema,
} from '../wfReactInterface/traceServerClientTypes';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {Chat, ChatCompletion, ChatRequest, Choice} from './types';

export enum ChatFormat {
  None = 'None',
  OpenAI = 'OpenAI',
  Gemini = 'Gemini',
}

export const hasStringProp = (obj: any, prop: string): boolean => {
  if (!(prop in obj)) {
    return false;
  }
  if (!_.isString(obj[prop])) {
    return false;
  }
  return true;
};

export const hasNumberProp = (obj: any, prop: string): boolean => {
  if (!(prop in obj)) {
    return false;
  }
  if (!_.isNumber(obj[prop])) {
    return false;
  }
  return true;
};

export const isToolCall = (toolCall: any): boolean => {
  if (!_.isPlainObject(toolCall)) {
    return false;
  }
  if (!hasStringProp(toolCall, 'id')) {
    return false;
  }
  if (!hasStringProp(toolCall, 'type')) {
    return false;
  }
  if (!_.isPlainObject(toolCall.function)) {
    return false;
  }
  if (
    !hasStringProp(toolCall.function, 'name') ||
    !hasStringProp(toolCall.function, 'arguments')
  ) {
    return false;
  }
  return true;
};

export const isToolCalls = (toolCalls: any): boolean => {
  if (toolCalls === null) {
    // Some llms return null for tool calls
    // before the chat view was hidden for those calls
    return true;
  }

  if (!_.isArray(toolCalls)) {
    return false;
  }
  return toolCalls.every((tc: any) => isToolCall(tc));
};

export const isPlaceholder = (part: any): boolean => {
  if (!_.isPlainObject(part)) {
    return false;
  }
  if (!hasStringProp(part, 'name')) {
    return false;
  }
  if (!hasStringProp(part, 'type')) {
    return false;
  }
  if ('default' in part && !_.isString(part.default)) {
    return false;
  }
  return true;
};

export const isInternalMessage = (part: any): boolean => {
  if (!_.isPlainObject(part)) {
    return false;
  }
  if (!hasStringProp(part, 'type')) {
    return false;
  }
  if (part.type === 'text') {
    if ('text' in part && !_.isString(part.text)) {
      return false;
    }
    return true;
  }
  if (part.type === 'image_url') {
    if ('image_url' in part && !_.isPlainObject(part.image_url)) {
      return false;
    }
    if (!hasStringProp(part.image_url, 'url')) {
      return false;
    }
    return true;
  }
  return false;
};

export const isMessagePart = (part: any): boolean => {
  if (_.isString(part)) {
    return true;
  }
  if (_.isPlainObject(part)) {
    if (isPlaceholder(part) || isInternalMessage(part)) {
      return true;
    }
  }
  return false;
};

export const isMessageContent = (content: any): boolean => {
  if (_.isString(content)) {
    return true;
  }
  if (_.isArray(content) && content.every((part: any) => isMessagePart(part))) {
    return true;
  }
  return false;
};

// Does this look like a message object?
export const isMessage = (message: any): boolean => {
  if (!_.isPlainObject(message)) {
    return false;
  }
  if (!hasStringProp(message, 'role')) {
    return false;
  }
  if (!('content' in message) && !('tool_calls' in message)) {
    return false;
  }
  if (
    'content' in message &&
    message.content !== null &&
    !isMessageContent(message.content)
  ) {
    return false;
  }
  if ('tool_calls' in message && !isToolCalls(message.tool_calls)) {
    return false;
  }
  return true;
};

export const isGeminiRequestFormat = (inputs: KeyedDictType): boolean => {
  if (!hasStringProp(inputs, 'contents')) {
    return false;
  }
  if (
    !_.isPlainObject(inputs.self) ||
    !_.isPlainObject(inputs.self.__class__)
  ) {
    return false;
  }
  if (
    inputs.self.__class__.module !== 'google.generativeai.generative_models'
  ) {
    return false;
  }
  return true;
};

export const isGeminiCandidate = (candidate: any): boolean => {
  if (!_.isPlainObject(candidate)) {
    return false;
  }
  if (!_.isPlainObject(candidate.content)) {
    return false;
  }
  // TODO: Check parts
  if (!hasStringProp(candidate.content, 'role')) {
    return false;
  }
  // TODO: Check any other fields?
  return true;
};

export const geminiCandidatesToChoices = (candidates: any[]): Choice[] => {
  const choices: Choice[] = [];
  for (let i = 0; i < candidates.length; i++) {
    const candidate = candidates[i];
    choices.push({
      index: i,
      message: {
        // TODO: Map role?
        role: candidate.content.role,
        content: candidate.content.parts.map((part: any) => {
          return {
            type: 'text',
            text: part.text,
          };
        }),
      },
      finish_reason: candidate.finish_reason.toString(),
    });
  }
  return choices;
};

export const isGeminiUsageMetadata = (metadata: any): boolean => {
  if (!_.isPlainObject(metadata)) {
    return false;
  }
  return (
    hasNumberProp(metadata, 'cached_content_token_count') &&
    hasNumberProp(metadata, 'prompt_token_count') &&
    hasNumberProp(metadata, 'candidates_token_count') &&
    hasNumberProp(metadata, 'total_token_count')
  );
};

export const isGeminiCompletionFormat = (output: any): boolean => {
  if (output !== null) {
    if (
      _.isPlainObject(output) &&
      _.isArray(output.candidates) &&
      output.candidates.every((c: any) => isGeminiCandidate(c)) &&
      isGeminiUsageMetadata(output.usage_metadata)
    ) {
      return true;
    }
    return false;
  }
  return true;
};

export const isTraceCallChatFormatGemini = (call: TraceCallSchema): boolean => {
  return (
    isGeminiRequestFormat(call.inputs) && isGeminiCompletionFormat(call.output)
  );
};

export const isAnthropicContentBlock = (block: any): boolean => {
  if (!_.isPlainObject(block)) {
    return false;
  }
  // TODO: Are there other types?
  if (block.type !== 'text') {
    return false;
  }
  if (!hasStringProp(block, 'text')) {
    return false;
  }
  return true;
};

export const isAnthropicCompletionFormat = (output: any): boolean => {
  if (output !== null) {
    // TODO: Could have additional checks here on things like usage
    if (
      _.isPlainObject(output) &&
      output.type === 'message' &&
      output.role === 'assistant' &&
      hasStringProp(output, 'model') &&
      _.isArray(output.content) &&
      output.content.every((c: any) => isAnthropicContentBlock(c))
    ) {
      return true;
    }
    return false;
  }
  return true;
};

type AnthropicContentBlock = {
  type: 'text';
  text: string;
};

export const anthropicContentBlocksToChoices = (
  blocks: AnthropicContentBlock[],
  stopReason: string
): Choice[] => {
  const choices: Choice[] = [];
  for (let i = 0; i < blocks.length; i++) {
    const block = blocks[i];
    choices.push({
      index: i,
      message: {
        role: 'assistant',
        content: block.text,
      },
      // TODO: What is correct way to map this?
      finish_reason: stopReason,
    });
  }
  return choices;
};

export const isTraceCallChatFormatOpenAI = (call: TraceCallSchema): boolean => {
  if (!('messages' in call.inputs)) {
    return false;
  }
  const {messages} = call.inputs;
  if (!_.isArray(messages)) {
    return false;
  }
  return messages.every(isMessage);
};

// Does this call look like a chat formatted object?
export const isCallChat = (call: CallSchema): boolean => {
  return getChatFormat(call) !== ChatFormat.None;
};

export const getChatFormat = (call: CallSchema): ChatFormat => {
  if (!('traceCall' in call) || !call.traceCall) {
    return ChatFormat.None;
  }
  if (isTraceCallChatFormatOpenAI(call.traceCall)) {
    return ChatFormat.OpenAI;
  }
  if (isTraceCallChatFormatGemini(call.traceCall)) {
    return ChatFormat.Gemini;
  }
  return ChatFormat.None;
};

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

export const normalizeChatRequest = (request: any): ChatRequest => {
  if (isGeminiRequestFormat(request)) {
    const modelIn = request.self.model_name;
    const model = modelIn.split('/').pop() ?? '';
    return {
      model,
      messages: [
        {
          role: 'system',
          content: request.contents,
        },
      ],
    };
  }
  // Anthropic has system message as a top-level request field
  if (hasStringProp(request, 'system')) {
    return {
      ...request,
      messages: [
        {
          role: 'system',
          content: request.system,
        },
        ...request.messages,
      ],
    };
  }
  return request as ChatRequest;
};

export const normalizeChatCompletion = (
  request: ChatRequest,
  completion: any
): ChatCompletion => {
  if (isGeminiCompletionFormat(completion)) {
    // We normalize to the OpenAI format as our standard representation
    // but the Gemini format does not have a direct mapping for some fields.
    // For now we leave empty placeholders for type checking purposes.
    return {
      id: '',
      choices: geminiCandidatesToChoices(completion.candidates),
      created: 0,
      model: request.model,
      system_fingerprint: '',
      usage: {
        prompt_tokens: completion.usage_metadata.prompt_token_count,
        completion_tokens: completion.usage_metadata.candidates_token_count,
        total_tokens: completion.usage_metadata.total_token_count,
      },
    };
  }
  if (isAnthropicCompletionFormat(completion)) {
    return {
      id: completion.id,
      choices: anthropicContentBlocksToChoices(
        completion.content,
        completion.stop_reason
      ),
      created: 0,
      model: completion.model,
      system_fingerprint: '',
      usage: {
        prompt_tokens: completion.usage.input_tokens,
        completion_tokens: completion.usage.output_tokens,
        total_tokens:
          completion.usage.input_tokens + completion.usage.output_tokens,
      },
    };
  }
  return completion as ChatCompletion;
};

export const useCallAsChat = (
  call: TraceCallSchema
): {
  loading: boolean;
} & Chat => {
  // Traverse the data and find all ref URIs.
  const refs = getRefs(call);
  const {useRefsData} = useWFHooks();
  const refsData = useRefsData(refs);
  const refsMap = _.zipObject(refs, refsData.result ?? []);
  const request = normalizeChatRequest(deref(call.inputs, refsMap));
  const result = call.output
    ? normalizeChatCompletion(request, deref(call.output, refsMap))
    : null;

  // TODO: It is possible that all of the choices are refs again, handle this better.
  if (
    result &&
    result.choices &&
    result.choices.some(choice => isWeaveRef(choice))
  ) {
    result.choices = [];
  }

  return {
    loading: refsData.loading,
    isStructuredOutput: isStructuredOutputCall(call),
    request,
    result,
  };
};
