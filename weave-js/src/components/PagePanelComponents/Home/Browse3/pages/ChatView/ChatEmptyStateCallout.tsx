import {Callout} from '@wandb/weave/components/Callout';
import {Icon, IconName} from '@wandb/weave/components/Icon';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React from 'react';

import {usePlaygroundContext} from '../PlaygroundPage/PlaygroundChat/PlaygroundContext';

const DEFAULT_EMPTY_STATE_MESSAGE = 'How can I help you today?';
const DEFAULT_MESSAGES: Array<{message: string; icon: IconName}> = [
  {
    message:
      'Explain the difference between concurrency and parallelism with code examples.',
    icon: 'settings',
  },
  {
    message:
      'What are the best practices for optimizing SQL queries in a large database?',
    icon: 'miller-columns',
  },
  {
    message: 'Generate a regular expression to validate an email address.',
    icon: 'email-envelope',
  },
  {
    message:
      'Create a REST API using Node.js and Express that handles user authentication.',
    icon: 'lock-closed',
  },
];
export const ChatEmptyStateCallout = () => {
  const {sendMessage} = usePlaygroundContext();
  return (
    <Tailwind>
      <div className="flex justify-center">
        <div className="mt-32 flex flex-col items-center gap-8 rounded-lg bg-moon-100 p-32">
          <Callout color="magenta" icon="buzz-bot10" size="large" />
          <p className="text-gray-500 mb-8 text-2xl font-semibold">
            {DEFAULT_EMPTY_STATE_MESSAGE}
          </p>
          {DEFAULT_MESSAGES.map(message => (
            <div
              key={message.message}
              onClick={() => sendMessage?.('user', message.message)}
              className="flex min-w-[600px] max-w-[700px] cursor-pointer items-center gap-4 rounded-full border border-moon-300 bg-white p-2">
              <div className="flex items-center justify-center rounded-full bg-moon-100 p-6">
                <Icon name={message.icon} />
              </div>
              <p className="text-gray-500 flex w-full justify-center">
                {message.message}
              </p>
            </div>
          ))}
        </div>
      </div>
    </Tailwind>
  );
};
