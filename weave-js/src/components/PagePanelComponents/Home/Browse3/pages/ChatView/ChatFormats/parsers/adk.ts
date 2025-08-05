import _ from 'lodash';
import {v4 as uuidv4} from 'uuid';

import {
  ChatCompletion,
  ChatRequest,
  Message,
  MessagePart,
  ToolCall,
} from '../../types';
import {Content, OtelLlmRequest, OtelLlmResponse} from '../schemas/adk';

function convertRole(role: string | undefined): string {
  if (role === 'model') {
    return 'assistant';
  }
  return role || 'user';
}

function convertContent(content: Content): Message[] {
  const messages: Message[] = [];
  const role = convertRole(content.role);

  if (!content.parts || content.parts.length === 0) {
    messages.push({role, content: ''});
    return messages;
  }

  // Collect text parts and tool calls for the main message
  const textParts: string[] = [];
  const toolCalls: ToolCall[] = [];

  for (const part of content.parts) {
    if (part.text) {
      textParts.push(part.text);
    } else if (part.function_call) {
      const id = part.function_call.id || uuidv4();
      const toolCall: ToolCall = {
        id,
        type: 'function',
        function: {
          name: part.function_call.name || '',
          arguments: JSON.stringify(part.function_call.args || {}),
        },
      };
      toolCalls.push(toolCall);
    } else if (
      part.function_response &&
      part.function_response.response &&
      _.isPlainObject(part.function_response.response) &&
      'message' in part.function_response.response &&
      _.isString(part.function_response.response.message)
    ) {
      messages.push({
        role: 'user',
        content: part.function_response.response.message,
      });
    }
  }

  // Add the main message if it has content or tool calls
  if (textParts.length > 0 || toolCalls.length > 0) {
    const message: Message = {role};

    const textContent = textParts.join('');
    if (textContent) {
      message.content = textContent;
    }

    if (toolCalls.length > 0) {
      message.tool_calls = toolCalls;
    }

    messages.push(message);
  }

  return messages;
}

export function parseOtelADKRequest(request: OtelLlmRequest): ChatRequest {
  const messages: Message[] = [];
  if (request.config?.system_instruction) {
    messages.push({
      role: 'system',
      content: request.config.system_instruction,
    });
  }

  if (request.contents) {
    for (const content of request.contents) {
      messages.push(...convertContent(content));
    }
  }

  return {
    model: request.model || 'unknown',
    messages,
  };
}

export function parseOtelADKResponse(
  response: OtelLlmResponse
): ChatCompletion | null {
  let message: Message;

  if (!response.content) {
    message = {
      role: 'assistant',
      content: '',
    };
  } else {
    const convertedMessages = convertContent(response.content);

    if (convertedMessages.length === 0) {
      return null;
    } else if (convertedMessages.length === 1) {
      message = convertedMessages[0];
    } else {
      const combinedMessage: Message = {
        role: 'assistant',
        content: [],
        tool_calls: [],
      };

      for (const msg of convertedMessages) {
        if (msg.content) {
          if (typeof msg.content === 'string') {
            (combinedMessage.content as MessagePart[]).push(msg.content);
          } else if (Array.isArray(msg.content)) {
            (combinedMessage.content as MessagePart[]).push(...msg.content);
          }
        }
        if (msg.tool_calls) {
          combinedMessage.tool_calls!.push(...msg.tool_calls);
        }
      }
      if (combinedMessage.tool_calls!.length === 0) {
        delete combinedMessage.tool_calls;
      }
      if (
        (combinedMessage.content as MessagePart[]).length === 1 &&
        typeof (combinedMessage.content as MessagePart[])[0] === 'string'
      ) {
        combinedMessage.content = (
          combinedMessage.content as MessagePart[]
        )[0] as string;
      }
      message = combinedMessage;
    }
  }
  const completion: ChatCompletion = {
    id: uuidv4(),
    choices: [
      {
        index: 0,
        message,
        finish_reason: 'stop',
      },
    ],
    created: Math.floor(Date.now() / 1000),
    model: 'unknown',
    system_fingerprint: '',
    usage: {
      prompt_tokens: response.usage_metadata?.prompt_token_count || 0,
      completion_tokens: response.usage_metadata?.candidates_token_count || 0,
      total_tokens: response.usage_metadata?.total_token_count || 0,
    },
  };
  return completion;
}
