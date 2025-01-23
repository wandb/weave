/**
 * Given a user ID, query to display the user's name or username.
 */

import React from 'react';

import {useUsers} from './UserLink';

type UserNameProps = {
  // If the user ID is null, querying will be skipped and nothing will be displayed.
  userId: string | null;

  // Optional text to display before the user's name such as "from: "
  prefix?: string;

  // Can choose to display either the name or username fields for the user.
  field?: 'name' | 'username';
};

export const UserName = (props: UserNameProps) => {
  if (props.userId == null) {
    return null;
  }
  return <UserNameInner {...props} userId={props.userId} />;
};

type UserNameInnerProps = {
  userId: string;
  prefix?: string;
  field?: 'name' | 'username';
};

const UserNameInner = ({userId, prefix, field}: UserNameInnerProps) => {
  const users = useUsers([userId]);
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
