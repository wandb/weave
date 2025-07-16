import React from 'react';
import {Link} from 'react-router-dom';

export interface UserLinkItemProps {
  user: {
    username: string;
    name: string;
    photoUrl: string | null;
  };
}

const UserLinkItem: React.FC<UserLinkItemProps> = ({user}) => {
  const {username, photoUrl, name} = user;
  const content = (
    <div className="flex items-center gap-2">
      <img
        src={photoUrl ?? '/default-profile-picture.png'}
        className="h-24 w-24 rounded-full"
        alt={name}
      />
      <span>{name}</span>
    </div>
  );

  return (
    <Link className="user-link" to={`/${username}`}>
      {content}
    </Link>
  );
};

export default UserLinkItem;
