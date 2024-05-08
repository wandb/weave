/**
 * Display a large version of the emoji and details about who reacted with it.
 */
import _ from 'lodash';
import React from 'react';

import {Tailwind} from '../../../../Tailwind';
import {Feedback} from '../pages/wfReactInterface/traceServerClient';

type EmojiDetailsProps = {
  viewer: string; // Username
  reactions: Feedback[];
  maxNames?: number;
};

function moveToFront<T>(list: T[], item: T): T[] {
  const index = list.indexOf(item);
  if (index !== -1) {
    list.splice(index, 1); // Remove the item from its current position
    list.unshift(item); // Add the item to the front
  }
  return list;
}

const englishJoiner = (list: string[]): string => {
  if (list.length === 0) {
    return '';
  }
  if (list.length === 1) {
    return list[0];
  }
  if (list.length === 2) {
    return list.join(' and ');
  }
  return `${list.slice(0, -1).join(', ')}, and ${list[list.length - 1]}`;
};

export const EmojiDetails = ({
  viewer,
  reactions,
  maxNames = 20,
}: EmojiDetailsProps) => {
  const emojis = reactions.map(r => r.payload.emoji);
  const emoji = _.uniq(emojis).join('');
  const groupedByAlias = _.groupBy(reactions, r => r.payload.alias);

  return (
    <Tailwind>
      <div className="max-w-xs">
        <div className="text-center text-7xl">{emoji}</div>
        {Object.entries(groupedByAlias).map(([alias, reactions]) => {
          const names = reactions.map(r => r.creator ?? r.wb_user_id);
          moveToFront(names, viewer);
          if (names.length > maxNames) {
            names.splice(maxNames);
            names.push('others');
          }
          if (names[0] === viewer) {
            names[0] = 'You (click to remove)';
          }
          const joined = englishJoiner(names);
          return (
            <div key={alias}>
              <b>{joined}</b> reacted with {alias}
            </div>
          );
        })}
      </div>
    </Tailwind>
  );
};
