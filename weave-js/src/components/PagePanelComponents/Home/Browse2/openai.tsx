import {
  CallMade,
  CallReceived,
  Person,
  Settings,
  SmartToy,
} from '@mui/icons-material';
import {Box, Chip, Typography} from '@mui/material';
import React, {FC} from 'react';
import {Popup} from 'semantic-ui-react';
import styled from 'styled-components';

import {DisplayControlChars} from './CommonLib';

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

export const OpenAIChatFunctionCall: FC<{
  functionCall: ChatMessageFunctionCall;
}> = ({functionCall}) => {
  return (
    <div>
      <CallMade />
      {functionCall.name}
      {functionCall.arguments}
    </div>
  );
};

const ChatMessageEl = styled.div<{callResponse: 'call' | 'response'}>`
  border-radius: 4px;
  margin-bottom: 12px;
  background-color: ${props =>
    props.callResponse === 'call' ? '#f9f9f9' : 'fff'};
`;

const ChatMessageContentEl = styled.div`
  display: flex;
  align-items: top;
`;

export const OpenAIChatMessage: FC<{message: ChatMessage}> = ({message}) => {
  return (
    <ChatMessageEl
      callResponse={message.role === 'assistant' ? 'call' : 'response'}>
      <ChatMessageContentEl>
        <div style={{marginRight: 8}}>
          {message.role === 'assistant' ? (
            <SmartToy />
          ) : message.role === 'user' ? (
            <Person />
          ) : message.role === 'function' ? (
            <CallReceived />
          ) : message.role === 'system' ? (
            <Settings />
          ) : (
            <div>Role: {(message as any).role}</div>
          )}
        </div>
        <div>
          {message.content != null && (
            <div style={{whiteSpace: 'pre-line', marginBottom: 16}}>
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
      {messages.map((m, i) => (
        <OpenAIChatMessage key={i} message={m} />
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
      <Box mb={1}>
        <Typography variant="body1" component="span">
          Model: <Chip label={chatInput.model} />
        </Typography>
      </Box>
      {/* <div>Model: {chatInput.model}</div> */}
      {chatInput.functions != null && (
        <Popup
          on="click"
          trigger={
            <Box mb={8}>
              <div
                style={{
                  cursor: 'pointer',
                  textDecoration: 'underline',
                  textDecorationStyle: 'dotted',
                }}>
                <Typography>
                  {chatInput.functions.length} callable functions
                </Typography>
              </div>
            </Box>
          }
          content={<OpenAIFunctionSpecs functionSpecs={chatInput.functions} />}
        />
      )}
      <div>
        <Typography>Messages</Typography>
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
      <Box mb={1}>
        <Typography variant="body1" component="span">
          Model: <Chip label={chatOutput.model} />
        </Typography>
      </Box>
      <div>
        {chatOutput.choices?.length > 0 ? (
          <OpenAIChatMessage message={chatOutput.choices[0].message} />
        ) : (
          <div>No response</div>
        )}
      </div>
    </div>
  );
};

export const isOpenAIChatInput = (obj: any): obj is OpenAIChatInput => {
  return obj.model != null && obj.messages != null;
};

export const isOpenAIChatOutput = (obj: any): obj is OpenAIChatOutput => {
  return obj != null && obj.model != null && obj.choices != null;
};
