import {Callout} from '@wandb/weave/components/Callout';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React from 'react';

const DEFAULT_EMPTY_STATE_MESSAGE = 'How can I help you today?';
const DEFAULT_MESSAGES = [
  'Explain the difference between concurrency and parallelism with code examples.',
  'What are the best practices for optimizing SQL queries in a large database?',
  'Generate a regular expression to validate an email address.',
  'Create a REST API using Node.js and Express that handles user authentication.',
];
export const ChatEmptyStateCallout = () => {
  return (
    <Tailwind>
      <div className="mx-auto mt-32 flex max-w-[800px] flex-col items-center gap-8 rounded-lg bg-moon-200 p-64">
        <Callout color="purple" icon="buzz-bot10" size="large" />

        <p className="text-gray-500 text-2xl font-semibold">
          {DEFAULT_EMPTY_STATE_MESSAGE}
        </p>
        {DEFAULT_MESSAGES.map(message => (
          <div className="w-[600px] rounded-3xl bg-moon-100 p-12 text-center">
            <p className="text-gray-500">{message}</p>
          </div>
        ))}
      </div>
    </Tailwind>
  );
};
