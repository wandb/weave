import React, {FC} from 'react';
import * as globals from '@wandb/weave/common/css/globals.styles';
import styled from 'styled-components';
import {Popup} from 'semantic-ui-react';

interface ChatMessageSystem {
  role: 'system';
  content: string;
}

interface ChatMessageUser {
  role: 'user';
  content: string;
}

interface ChatMessageFunctionCall {
  name: string;
  arguments: string;
}

interface ChatMessageAssistant {
  role: 'assistant';
  content?: string;
  function_call?: ChatMessageFunctionCall;
}

interface ChatMessageFunctionResponse {
  role: 'function';
  name: string;
  content: string;
}

type ChatMessage =
  | ChatMessageSystem
  | ChatMessageUser
  | ChatMessageAssistant
  | ChatMessageFunctionResponse;

interface FunctionSpec {
  name: string;
  description: string;
  parameters: any;
  returns: any;
}

interface OpenAIChatInput {
  model: string;
  functions?: FunctionSpec[];
  messages: ChatMessage[];
}

interface OpenAIChatOutputChoice {
  message: ChatMessage;
  finish_reason: string;
  index: number;
}

interface OpenAIChatOutput {
  model: string;
  choices: OpenAIChatOutputChoice[];
}

const escapeAndRenderControlChars = (str: string) => {
  const controlCharMap: {[key: string]: string | undefined} = {
    '\n': '\\n',
    '\t': '\\t',
    '\r': '\\r',
  };

  return str.split('').map((char, index) => {
    if (controlCharMap[char]) {
      return (
        <span key={index}>
          <span style={{color: globals.darkRed}}>{controlCharMap[char]}</span>
          {char === '\n' ? (
            <br />
          ) : (
            <span style={{width: '2em', display: 'inline-block'}}></span>
          )}
        </span>
      );
    }
    return char;
  });
};

const DisplayControlChars = ({text}: {text: string}) => {
  return <div>{escapeAndRenderControlChars(text)}</div>;
};

export const OpenAIChatFunctionCall: FC<{
  functionCall: ChatMessageFunctionCall;
}> = ({functionCall}) => {
  return (
    <div style={{marginTop: 16}}>
      ➡️{functionCall.name}
      {functionCall.arguments}
    </div>
  );
};

const ChatMessageEl = styled.div`
  border: 1px solid #aaa;
  padding: 4px;
  border-radius: 4px;
  margin-bottom: 12px;
`;

const ChatMessageContentEl = styled.div`
  display: flex;
  align-items: top;
`;

export const OpenAIChatMessage: FC<{message: ChatMessage}> = ({message}) => {
  return (
    <ChatMessageEl>
      <ChatMessageContentEl>
        <div style={{marginRight: 8}}>
          {message.role === 'assistant' ? (
            '🤖'
          ) : message.role === 'user' ? (
            '👤'
          ) : message.role === 'function' ? (
            '⬅️'
          ) : message.role === 'system' ? (
            '⚙'
          ) : (
            <div>Role: {message.role}</div>
          )}
        </div>
        <div>
          {message.content != null && (
            <div style={{whiteSpace: 'pre-line'}}>
              <DisplayControlChars text={message.content} />
            </div>
          )}
          {message.role === 'assistant' && message.function_call && (
            <OpenAIChatFunctionCall functionCall={message.function_call} />
          )}
        </div>
      </ChatMessageContentEl>
    </ChatMessageEl>
  );
};

export const OpenAIChatMessages: FC<{messages: ChatMessage[]}> = ({
  messages,
}) => {
  return (
    <div>
      {messages.map(m => (
        <OpenAIChatMessage message={m} />
      ))}
    </div>
  );
};

export const OpenAIFunctionSpec: FC<{functionSpec: FunctionSpec}> = ({
  functionSpec,
}) => {
  return <div>{functionSpec.name}</div>;
};

export const OpenAIFunctionSpecs: FC<{functionSpecs: FunctionSpec[]}> = ({
  functionSpecs,
}) => {
  return (
    <div>
      {functionSpecs.map(f => (
        <OpenAIFunctionSpec functionSpec={f} />
      ))}
    </div>
  );
};

export const OpenAIChatInputView: FC<{chatInput: OpenAIChatInput}> = ({
  chatInput,
}) => {
  return (
    <div>
      <div>Model: {chatInput.model}</div>
      {chatInput.functions != null && (
        <Popup
          on="click"
          trigger={
            <div
              style={{
                cursor: 'pointer',
                textDecoration: 'underline',
                textDecorationStyle: 'dotted',
              }}>
              {chatInput.functions.length} callable functions
            </div>
          }
          content={<OpenAIFunctionSpecs functionSpecs={chatInput.functions} />}
        />
      )}
      <div>
        <OpenAIChatMessages messages={chatInput.messages} />
      </div>
    </div>
  );
};

export const OpenAIChatOutputView: FC<{chatOutput: OpenAIChatOutput}> = ({
  chatOutput,
}) => {
  return (
    <div>
      <div>Model: {chatOutput.model}</div>
      <div>
        <OpenAIChatMessage message={chatOutput.choices[0].message} />
      </div>
    </div>
  );
};

export const isOpenAIChatInput = (obj: any): obj is OpenAIChatInput => {
  return obj.model !== undefined && obj.messages !== undefined;
};

export const isOpenAIChatOutput = (obj: any): obj is OpenAIChatOutput => {
  return obj.model !== undefined && obj.choices !== undefined;
};
