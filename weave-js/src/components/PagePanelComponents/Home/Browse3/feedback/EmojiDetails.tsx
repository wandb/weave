/**
 * Display a large version of the emoji and details about who reacted with it.
 */
import _ from 'lodash';
import React, {useMemo} from 'react';

import {Tailwind} from '../../../../Tailwind';
import {useUsers} from '../../../../UserLink';
import {Feedback} from '../pages/wfReactInterface/traceServerClientTypes';

type EmojiDetailsProps = {
  currentViewerId: string | null;
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
  // After discussing with design, keeping the Oxford comma
  return `${list.slice(0, -1).join(', ')}, and ${list[list.length - 1]}`;
};

export const EmojiDetails = ({
  currentViewerId,
  reactions,
  maxNames = 20,
}: EmojiDetailsProps) => {
  const emojis = reactions.map(r => r.payload.emoji);
  const emoji = _.uniq(emojis).join('');
  const groupedByAlias = _.groupBy(reactions, r => r.payload.alias);
  const neededUsers = useMemo(() => {
    const reactionIds = reactions.map(r => r.wb_user_id);
    if (currentViewerId) {
      reactionIds.push(currentViewerId);
    }
    return _.uniq(reactionIds);
  }, [currentViewerId, reactions]);
  const users = useUsers(neededUsers);
  const userMap = useMemo(() => {
    if (users === 'load' || users === 'loading' || users === 'error') {
      return {};
    }
    return _.keyBy(users, 'id');
  }, [users]);

  return (
    <Tailwind>
      <div className="max-w-xs">
        <div className="text-center text-7xl">{emoji}</div>
        {Object.entries(groupedByAlias).map(([alias, aliasReactions]) => {
          // TODO (Tim): After https://github.com/wandb/core/pull/22947 is deployed,
          // change the fallback from `r.wb_user_id` to `null`-like (this means no access)
          const names = aliasReactions.map(
            r => r.creator ?? userMap[r.wb_user_id]?.username ?? r.wb_user_id
          );
          const currentViewerName = currentViewerId
            ? userMap[currentViewerId]?.username ?? currentViewerId
            : null;
          moveToFront(names, currentViewerName);
          if (names.length > maxNames) {
            names.splice(maxNames);
            names.push('others');
          }
          if (names[0] === currentViewerName) {
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
