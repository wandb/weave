import {FC} from 'react';
import React from 'react';

export interface TurnAnchorProps {
  turnId: string;
}

export const TurnAnchor: FC<TurnAnchorProps> = ({turnId}) => {
  return (
    <div
      className={
        'flex justify-between rounded-lg bg-blue-300 py-12 pl-12 pr-16 text-blue-650'
      }>
      <span>
        <span className={'font-semibold'}>
          No chat view available for this turn.
        </span>{' '}
        You can inspect inputs and outputs in the trace view
      </span>
      <span className={'font-semibold'}>View trace</span>
    </div>
  );
};
