/**
 * Just a username to display
 */

import React from 'react';

import {useUsers} from './UserLink';

type UserNameProps = {
  userId: string | null;
  prefix?: string;
  field?: 'name' | 'username';
};

export const UserName = ({userId, prefix, field}: UserNameProps) => {
  const users = useUsers(userId ? [userId] : []);
  if (userId == null) {
    return null;
  }
  if (users === 'load' || users === 'loading') {
    return null;
  }
  if (users === 'error') {
    return null;
  }
  const user = users[0];
  const value = user[field ?? 'name'];
  if (!value) {
    return null;
  }

  return (
    <span>
      {prefix}
      {value}
    </span>
  );
};
