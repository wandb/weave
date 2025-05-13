import _ from 'lodash';

import {isWeaveRef} from '../../filters/common';
import {mapObject, traverse, TraverseContext} from '../CallPage/traverse';
import {useWFHooks} from '../wfReactInterface/context';
import {
  KeyedDictType,
  TraceCallSchema,
} from '../wfReactInterface/traceServerClientTypes';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {
  Chat,
  ChatCompletion,
  ChatRequest,
  Choice,
  Message,
  ToolCall,
} from './types';

export enum ChatFormat {
  None = 'None',
  OpenAI = 'OpenAI',
  Gemini = 'Gemini',
  Mistral = 'Mistral',
  OTEL = 'OTEL',
}

// OTEL specific keys for finding prompts
// Must be kept in sync with backend
export const OTEL_INPUT_KEYS = [
  'ai.prompt',
  'gen_ai.prompt',
  'input.value',
  'mlflow.spanInputs',
  'traceloop.entity.input',
  'gcp.vertex.agent.tool_call_args',
  'gcp.vertex.agent.llm_request',
  'input',
];

// OTEL specific keys for finding completions
export const OTEL_OUTPUT_KEYS = [
  'ai.response',
  'gen_ai.completion',
  'output.value',
  'mlflow.spanOutputs',
  'gen_ai.content.completion',
  'traceloop.entity.output',
  'gcp.vertex.agent.tool_response',
  'gcp.vertex.agent.llm_response',
  'output',
];

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

  // Anthropic tool result
  if (part.type === 'tool_result') {
    if (!hasStringProp(part, 'tool_use_id')) {
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
  if (
    hasStringProp(call.inputs, 'model') &&
    call.inputs.model.toLowerCase().includes('mistral')
  ) {
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
  if (isTraceCallChatFormatMistral(call.traceCall)) {
    return ChatFormat.Mistral;
  }
  if (isTraceCallChatFormatOpenAI(call.traceCall)) {
    return ChatFormat.OpenAI;
  }
  if (isTraceCallChatFormatGemini(call.traceCall)) {
    return ChatFormat.Gemini;
  }
  if (isTraceCallChatFormatOTEL(call.traceCall)) {
    return ChatFormat.OTEL;
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

// Normalize an OTEL span's input to a ChatRequest
export const normalizeOTELChatRequest = (
  call: TraceCallSchema
): ChatRequest => {
  // Find prompt value from any of the expected OTEL input keys
  const promptValue = findOTELValue(call.inputs, OTEL_INPUT_KEYS);

  if (!promptValue) {
    // Fallback with an empty request if no prompt found
    return {
      model: 'unknown',
      messages: [],
    };
  }

  let modelName = call.attributes['model'] || 'unknown';
  if (
    _.isPlainObject(promptValue) &&
    'messages' in promptValue &&
    _.isArray(promptValue.messages)
  ) {

    // If the prompt has an OpenAI-like messages array, use it directly
    if (promptValue.model) {
      modelName = promptValue.model;
    }

    const anthropicSystemPrompt = call.attributes?.model_parameters?.system

    const messages = promptValue.messages
    if (anthropicSystemPrompt !== undefined && !messages.some((msg: any) => { return msg.role == 'system' })) {
      const systemMsg = {
        role: 'system',
        content: anthropicSystemPrompt
      }
      return {
        model: modelName,
        messages: [systemMsg,...messages]
      }
    }

    return {
      model: modelName,
      messages: promptValue.messages,
    };
  }

  // Process the content from the prompt value
  let content = processOTELContent(promptValue, 'user');

  if (_.isString(content)) {
    return {
      model: modelName,
      messages: [
        {
          role: 'user',
          content,
        },
      ],
    }
  }
  else {
    return {
      model: modelName,
      messages: content
    }
  }
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

// Define Delta type and type guard for Mistral streaming chunks
export type MistralDelta = {
  role?: string;
  content?: string;
  tool_calls?: ToolCall[]; // Based on OpenAI, Mistral might stream tool calls this way
};

export const isMistralDelta = (delta: any): boolean => {
  if (!_.isPlainObject(delta)) {
    return false;
  }
  if ('role' in delta && !hasStringProp(delta, 'role')) {
    return false;
  }
  if ('content' in delta && !hasStringProp(delta, 'content')) {
    return false;
  }
  if ('tool_calls' in delta && !isToolCalls(delta.tool_calls)) {
    return false;
  }
  return true;
};

// Normalize an OTEL span's output to a ChatCompletion
export const normalizeOTELChatCompletion = (
  call: TraceCallSchema,
  request: ChatRequest
): ChatCompletion => {
  // Find completion value from any of the expected OTEL output keys
  const completionValue = findOTELValue(call.output, OTEL_OUTPUT_KEYS);

  if (!completionValue) {
    // Return empty completion if no output is found
    return {
      id: `${request.model}-${Date.now()}`,
      choices: [],
      created: Math.floor(Date.now() / 1000),
      model: request.model,
      system_fingerprint: '',
      usage: {prompt_tokens: 0, completion_tokens: 0, total_tokens: 0},
    };
  }

  // Try to extract token usage information
  let usage = {
    prompt_tokens: 0,
    completion_tokens: 0,
    total_tokens: 0,
  };

  // Look for token usage in various locations and formats
  if (call.summary?.weave?.costs) {
    // Try to get from costs in summary
    const modelCosts = Object.values(call.summary.weave.costs)[0];
    if (modelCosts) {
      usage.prompt_tokens =
        modelCosts.prompt_tokens || modelCosts.input_tokens || 0;
      usage.completion_tokens =
        modelCosts.completion_tokens || modelCosts.output_tokens || 0;
      usage.total_tokens =
        modelCosts.total_tokens ||
        usage.prompt_tokens + usage.completion_tokens;
    }
  }

  // If completion is already in OpenAI-like format, use it directly
  if (
    _.isPlainObject(completionValue) &&
    'choices' in completionValue &&
    _.isArray(completionValue.choices)
  ) {
    const modelName = call.attributes['model'] ?? "unknown";
    return {
      id: completionValue.id || `${request.model}-${Date.now()}`,
      choices: completionValue.choices,
      created: completionValue.created || Math.floor(Date.now() / 1000),
      model: modelName,
      system_fingerprint: completionValue.system_fingerprint || '',
      usage: completionValue.usage || usage,
    };
  }

  // Process the content from the completion value
  const messages = processOTELContent(completionValue, 'assistant');
  const choices: Choice[] = messages.map((message, index) => {
    return {
      index,
      message,
      finish_reason: "stop"
    }
  })

  // Create a standardized choice from the processed content

  return {
    id: `${request.model}-${Date.now()}`,
    choices: [choices[0]],
    created: Math.floor(Date.now() / 1000),
    model: request.model,
    system_fingerprint: '',
    usage,
  };
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
      created: 0, // Anthropic doesn't provide `created`
      model: completion.model,
      system_fingerprint: '', // Anthropic doesn't provide `system_fingerprint`
      usage: {
        prompt_tokens: completion.usage.input_tokens,
        completion_tokens: completion.usage.output_tokens,
        total_tokens:
          completion.usage.input_tokens + completion.usage.output_tokens,
      },
    };
  }
  if (isMistralCompletionFormat(completion)) {
    if (completion === null) {
      // Handle cases where an SDK error or stream issue results in a null output
      // for a call that is otherwise identified as Mistral.
      return {
        id: request.model + '-' + Date.now(), // Generate a placeholder ID
        choices: [],
        created: Math.floor(Date.now() / 1000),
        model: request.model, // Use model from the request
        system_fingerprint: '',
        usage: {prompt_tokens: 0, completion_tokens: 0, total_tokens: 0},
      };
    }

    const choices: Choice[] = completion.choices.map((choicePart: any) => {
      let message: Message;
      if (choicePart.message) {
        message = choicePart.message as Message;
      } else if (choicePart.delta) {
        message = {
          role: choicePart.delta.role ?? 'assistant',
          content: choicePart.delta.content ?? '',
        };
        if (choicePart.delta.tool_calls) {
          message.tool_calls = choicePart.delta.tool_calls;
        }
      } else {
        message = {role: 'assistant', content: ''};
      }
      return {
        index: choicePart.index,
        message,
        finish_reason: choicePart.finish_reason ?? 'stop',
      };
    });

    return {
      id: completion.id,
      choices,
      created: completion.created,
      model: completion.model,
      system_fingerprint: completion.system_fingerprint ?? '',
      usage: completion.usage
        ? {
            prompt_tokens: completion.usage.prompt_tokens,
            completion_tokens: completion.usage.completion_tokens,
            total_tokens: completion.usage.total_tokens,
          }
        : {
            prompt_tokens: 0,
            completion_tokens: 0,
            total_tokens: 0,
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
  const refsData = useRefsData({refUris: refs});
  const refsMap = _.zipObject(refs, refsData.result ?? []);

  // Handle OTEL span format differently
  let request: ChatRequest;
  let result: ChatCompletion | null = null;

  // Check if this is an OTEL span
  if (call.attributes && 'otel_span' in call.attributes) {
    // Use specialized OTEL handlers
    request = normalizeOTELChatRequest(call);
    result = call.output ? normalizeOTELChatCompletion(call, request) : null;
  } else {
    // Use standard handlers
    request = normalizeChatRequest(deref(call.inputs, refsMap));
    result = call.output
      ? normalizeChatCompletion(request, deref(call.output, refsMap))
      : null;
  }

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

export const isMistralChatCompletionChoice = (choice: any): boolean => {
  if (!_.isPlainObject(choice)) {
    return false;
  }
  if (!hasNumberProp(choice, 'index')) {
    return false;
  }

  const hasMessage = 'message' in choice;
  const hasDelta = 'delta' in choice;

  if (hasMessage && !isMessage(choice.message)) {
    return false;
  }
  if (hasDelta && !isMistralDelta(choice.delta)) {
    return false;
  }
  if (!hasMessage && !hasDelta) {
    // Must have one or the other
    return false;
  }

  // finish_reason can be null (for streaming chunks) or a string
  if (!('finish_reason' in choice)) {
    return false;
  }
  if (
    choice.finish_reason !== null &&
    !hasStringProp(choice, 'finish_reason')
  ) {
    return false;
  }
  return true;
};

export const isMistralUsage = (usage: any): boolean => {
  if (!_.isPlainObject(usage)) {
    return false;
  }
  return (
    hasNumberProp(usage, 'prompt_tokens') &&
    hasNumberProp(usage, 'completion_tokens') &&
    hasNumberProp(usage, 'total_tokens')
  );
};

export const isMistralRequestFormat = (inputs: KeyedDictType): boolean => {
  if (!('messages' in inputs)) {
    return false;
  }
  const {messages} = inputs;
  if (!_.isArray(messages) || !messages.every(isMessage)) {
    return false;
  }
  if (
    !hasStringProp(inputs, 'model') ||
    !inputs.model.toLowerCase().includes('mistral')
  ) {
    return false;
  }
  return true;
};

export const isMistralCompletionFormat = (output: any): boolean => {
  if (output === null) {
    return true;
  }
  if (!_.isPlainObject(output)) {
    return false;
  }
  if (!hasStringProp(output, 'id')) {
    return false;
  }
  if (
    !hasStringProp(output, 'object') ||
    !output.object.startsWith('chat.completion') // Allows 'chat.completion' & 'chat.completion.chunk'
  ) {
    return false;
  }
  if (!hasNumberProp(output, 'created')) {
    return false;
  }
  if (
    !hasStringProp(output, 'model') ||
    !output.model.toLowerCase().includes('mistral')
  ) {
    return false;
  }
  if (!_.isArray(output.choices)) {
    return false;
  }
  // isMistralChatCompletionChoice now handles delta within choices
  if (!output.choices.every((c: any) => isMistralChatCompletionChoice(c))) {
    return false;
  }

  // Usage is expected for full "chat.completion" objects, but not for "chat.completion.chunk"
  if (output.object === 'chat.completion' && !isMistralUsage(output.usage)) {
    return false;
  }
  // Allow chunks that may not have usage

  return true;
};

export const isTraceCallChatFormatMistral = (
  call: TraceCallSchema
): boolean => {
  return (
    isMistralRequestFormat(call.inputs) &&
    isMistralCompletionFormat(call.output)
  );
};

// Find a prompt/completion value from OTEL attributes using the specified keys
export const findOTELValue = (obj: any, searchKeys: string[]): any | null => {
  if (!obj || !_.isPlainObject(obj)) {
    return null;
  }

  // Direct check in the object
  for (const key of searchKeys) {
    if (key in obj) {
      return obj[key];
    }
  }

  return null;
};

// Process OTEL chat data to find content
export const processOTELContent = (content: any, defaultRole: string): Message[] => {
  if (_.isString(content)) {
    return [
      {
        role: defaultRole,
        content: content
      }
    ]
  }
  else if (_.isPlainObject(content) && 'role' in content) {
    if ('content' in content && _.isArray(content.content)) {
      return content.content.flatMap((item: any) => processOTELContent(item.text, content.role))
    }
    return content
  }

  else if (_.isArray(content)) {
    return content.flatMap(item => processOTELContent(item, defaultRole))
  }
  return []
  //
  // if (_.isPlainObject(content)) {
  //   // Handle common patterns in OTEL traces
  //   if ('messages' in content && _.isArray(content.messages)) {
  //     // Extract text from OpenAI-like message format
  //     const messages = content.messages.map((msg: any) => {
  //       if (_.isString(msg)) {
  //         return msg;
  //       }
  //       if (_.isPlainObject(msg) && 'content' in msg) {
  //         return msg.content;
  //       }
  //       return JSON.stringify(msg);
  //     });
  //     return messages;
  //   }
  //
  //   if ('prompt' in content && _.isString(content.prompt)) {
  //     return content.prompt;
  //   }
  //
  //   if ('text' in content && _.isString(content.text)) {
  //     return content.text;
  //   }
  //
  //   // Fallback to JSON string
  //   return JSON.stringify(content);
  // }
  //
  // if (_.isArray(content)) {
  //   // If it's an array of messages, try to extract content from each
  //   if (content.some(item => _.isPlainObject(item) && 'role' in item)) {
  //     return content
  //   }
  // }
  //
  // // Fallback for other types
  // return JSON.stringify(content);
};

// Detect OTEL span format based on presence of 'otel_span' attribute
export const isTraceCallChatFormatOTEL = (call: TraceCallSchema): boolean => {
  // Check if this is an OTEL span
  if (!call.attributes || !('otel_span' in call.attributes)) {
    return false;
  }
  // Look for a prompt/input in the expected locations
  const promptValue = findOTELValue(call.inputs, OTEL_INPUT_KEYS);

  // Look for a completion/output in the expected locations
  const completionValue = findOTELValue(call.output, OTEL_OUTPUT_KEYS);

  // If we found either prompt or completion data, consider it valid
  return promptValue !== null || completionValue !== null;
};
