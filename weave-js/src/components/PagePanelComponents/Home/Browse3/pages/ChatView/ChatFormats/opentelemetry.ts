import _ from 'lodash';

import {OptionalTraceCallSchema} from '../../PlaygroundPage/types';
import {ChatCompletion, ChatRequest, Choice, Message} from '../types';

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

// Find a prompt/completion value from OTEL attributes using the specified keys
const findOTELValue = (obj: any, searchKeys: string[]): any | null => {
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
const processOTELContent = (content: any, defaultRole: string): Message[] => {
  if (_.isString(content)) {
    return [
      {
        role: defaultRole,
        content: content,
      },
    ];
  } else if (_.isPlainObject(content) && 'role' in content) {
    if ('content' in content && _.isArray(content.content)) {
      return content.content.flatMap((item: any) =>
        processOTELContent(item.text, content.role)
      );
    }
    return content;
  } else if (_.isPlainObject(content) && 'prompt' in content) {
    const text = _.isString(content.prompt)
      ? content.prompt
      : JSON.stringify(content.prompt);
    return [
      {
        role: defaultRole,
        content: text,
      },
    ];
  } else if (_.isArray(content)) {
    return content.flatMap(item => processOTELContent(item, defaultRole));
  }
  // Fallback to prevent empty display for unhandled types/schemas
  return [
    {
      role: defaultRole,
      content: JSON.stringify(content),
    },
  ];
};

// Detect OTEL span format based on presence of 'otel_span' attribute
export const isTraceCallChatFormatOTEL = (
  call: OptionalTraceCallSchema
): boolean => {
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

// Normalize an OTEL span's input to a ChatRequest
export const normalizeOTELChatRequest = (
  call: OptionalTraceCallSchema
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

  let modelName = call.attributes?.model || 'unknown';
  if (
    _.isPlainObject(promptValue) &&
    'messages' in promptValue &&
    _.isArray(promptValue.messages)
  ) {
    // If the prompt has an OpenAI-like messages array, use it directly
    if (promptValue.model) {
      modelName = promptValue.model;
    }

    const anthropicSystemPrompt = call.attributes?.model_parameters?.system;

    const messages = promptValue.messages;
    if (
      anthropicSystemPrompt !== undefined &&
      !messages.some((msg: any) => {
        return msg.role === 'system';
      })
    ) {
      const systemMsg = {
        role: 'system',
        content: anthropicSystemPrompt,
      };
      return {
        model: modelName,
        messages: [systemMsg, ...messages],
      };
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
    };
  } else {
    return {
      model: modelName,
      messages: content,
    };
  }
};

// Normalize an OTEL span's output to a ChatCompletion
export const normalizeOTELChatCompletion = (
  call: OptionalTraceCallSchema,
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
    const modelName = call.attributes?.model ?? 'unknown';
    return {
      id: completionValue.id || `${request.model}-${Date.now()}`,
      choices: completionValue.choices,
      created: completionValue.created || Math.floor(Date.now() / 1000),
      model: modelName,
      system_fingerprint: completionValue.system_fingerprint || '',
      usage: completionValue.usage || usage,
    };
  }

  if (
    _.isPlainObject(completionValue) &&
    'text' in completionValue &&
    _.isString(completionValue.text)
  ) {
    return {
      id: completionValue.id || `${request.model}-${Date.now()}`,
      choices: [
        {
          index: 0,
          message: {
            role: completionValue.role || 'assistant',
            content: completionValue.text,
          },
          finish_reason: completionValue.finish_reason || 'stop',
        },
      ],
      created: Math.floor(Date.now() / 1000),
      model: request.model || 'unknown',
      system_fingerprint: '',
      usage,
    };
  }

  // Process the content from the completion value
  const messages = processOTELContent(completionValue, 'assistant');
  const choices: Choice[] = messages.map((message, index) => {
    return {
      index,
      message,
      finish_reason: 'stop',
    };
  });

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
