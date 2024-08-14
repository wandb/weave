import {gql} from '@apollo/client';
import {Avatar, Popover, TooltipProps} from '@mui/material';
import {apolloClient} from '@wandb/weave/apollo';
import * as Colors from '@wandb/weave/common/css/color.styles';
import {NotApplicable} from '@wandb/weave/components/PagePanelComponents/Home/Browse2/NotApplicable';
import React, {useEffect, useRef, useState} from 'react';
import styled from 'styled-components';

import {useDeepMemo} from '../hookUtils';
import {Button} from './Button';
import {
  DraggableGrow,
  DraggableHandle,
  Popped,
  StyledTooltip,
  TooltipHint,
} from './DraggablePopups';
import {LoadingDots} from './LoadingDots';
import {A, Link} from './PagePanelComponents/Home/Browse3/pages/common/Links';

const FIND_USER_QUERY = gql`
  query FindUser($userId: ID!) {
    user(id: $userId) {
      id
      name
      email
      photoUrl
      deletedAt
      username
    }
  }
`;

const UserTrigger = styled.div`
  display: flex;
  align-items: center;
  cursor: pointer;
  &:hover {
    & a {
      color: ${Colors.TEAL_500};
    }

`;
UserTrigger.displayName = 'S.UserTrigger';

const UserContentHeader = styled.div`
  display: flex;
  align-items: center;
  padding: 2px 2px 2px 8px;
  background-color: ${Colors.MOON_100};
`;
UserContentHeader.displayName = 'S.UserContentHeader';

const UserName = styled.div`
  font-weight: 600;
  flex: 1 1 auto;
`;
UserName.displayName = 'S.UserName';

const UserContentBody = styled.div`
  padding: 4px;
  display: flex;
  align-items: flex-start;
  gap: 4px;
`;
UserContentBody.displayName = 'S.UserContentBody';

const Grid = styled.div`
  display: grid;
  grid-template-columns: auto auto;
  column-gap: 8px;
`;
Grid.displayName = 'S.Grid';

const Label = styled.div`
  text-align: right;
  font-weight: 600;
`;
Label.displayName = 'S.Label';

type UserInfo = {
  id: string;
  // We might not have permission to read these fields
  name?: string;
  email?: string;
  username?: string;
  photoUrl?: string;
};

type UserResult = 'load' | 'loading' | 'error' | UserInfo[];

const onClickDoNothing = (e: React.MouseEvent) => {
  e.preventDefault();
};

type UserContentProps = {
  user: UserInfo;
  mode: 'tooltip' | 'popover';
  onClose?: () => void;
  hasPopover?: boolean;
};
const UserContent = ({user, mode, onClose, hasPopover}: UserContentProps) => {
  const isPopover = mode === 'popover';
  const imgSize = isPopover ? 100 : 50;
  const username = isPopover ? (
    <Link to={`/${user.username}`}>{user.username}</Link>
  ) : (
    user.username
  );
  const email = isPopover ? (
    <A href={`mailto:${user.email}`}>{user.email}</A>
  ) : (
    user.email
  );
  const bodyStyle = isPopover ? {fontSize: '0.9em'} : undefined;
  const onCloseClick = onClose ? () => onClose() : undefined;
  return (
    <>
      <DraggableHandle>
        <UserContentHeader>
          <UserName>{user.name}</UserName>
          {isPopover && (
            <Button
              size="small"
              variant="ghost"
              icon="close"
              tooltip="Close"
              onClick={onCloseClick}
            />
          )}
        </UserContentHeader>
      </DraggableHandle>
      <UserContentBody style={bodyStyle}>
        <Avatar src={user.photoUrl} sx={{width: imgSize, height: imgSize}} />
        <Grid>
          <Label>Username</Label>
          <div>{username}</div>
          <Label>Email</Label>
          <div>{email}</div>
        </Grid>
      </UserContentBody>
      {hasPopover && !isPopover && (
        <TooltipHint>Click to open card</TooltipHint>
      )}
    </>
  );
};

type UserInnerProps = {
  user: UserInfo;
  includeName?: boolean;
  placement?: TooltipProps['placement'];
  hasPopover?: boolean;
};
const UserInner = ({
  user,
  includeName,
  placement,
  hasPopover,
}: UserInnerProps) => {
  const ref = useRef<HTMLDivElement>(null);
  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);
  const showPopover = hasPopover ?? true;
  const onClick = showPopover
    ? (event: React.MouseEvent<HTMLElement>) => {
        setAnchorEl(anchorEl ? null : ref.current);
      }
    : undefined;
  const onClose = () => setAnchorEl(null);

  const open = Boolean(anchorEl);
  const id = open ? 'simple-popper' : undefined;

  const title = open ? (
    '' // Suppress tooltip when popper is open.
  ) : (
    <UserContent user={user} mode="tooltip" hasPopover={hasPopover} />
  );

  // Unfortunate but necessary to get appear on top of peek drawer.
  const stylePopper = {zIndex: 1};

  const size = 22; // Chosen to match SmallRef circle.
  return (
    <>
      <StyledTooltip
        enterDelay={500}
        title={title}
        placement={placement ?? 'right'}
        padding={0}>
        <UserTrigger ref={ref} onClick={onClick}>
          <Avatar
            src={user.photoUrl}
            sx={{width: size, height: size, marginRight: '4px'}}
          />
          {includeName && (
            <Link
              to={`/${user.username}`}
              onClick={onClickDoNothing}
              $variant="secondary">
              {user.name}
            </Link>
          )}
        </UserTrigger>
      </StyledTooltip>
      <Popover
        id={id}
        open={open}
        anchorEl={anchorEl}
        style={stylePopper}
        anchorOrigin={{
          vertical: 'top',
          horizontal: 'center',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'center',
        }}
        onClose={onClose}
        TransitionComponent={DraggableGrow}>
        <Popped>
          <UserContent user={user} mode="popover" onClose={onClose} />
        </Popped>
      </Popover>
    </>
  );
};

type UserLinkProps = {
  userId: string | null;
  includeName?: boolean; // Default is to show avatar image only.
  placement?: TooltipProps['placement'];
  hasPopover?: boolean; // Can you click to open more a popup
};

const fetchUser = (userId: string) => {
  return apolloClient
    .query({
      query: FIND_USER_QUERY as any,
      variables: {
        userId,
      },
    })
    .then(result => {
      return result.data.user as UserInfo;
    });
};

const fetchUsers = (userIds: string[]) => {
  // This is not great, gorilla does not allow multi-user-lookup by id :(
  return Promise.all(userIds.map(fetchUser));
};

export const useUsers = (userIds: string[]) => {
  const memoedUserIds = useDeepMemo(userIds);

  const [users, setUsers] = useState<UserResult>('load');
  useEffect(() => {
    let mounted = true;
    setUsers('loading');
    fetchUsers(memoedUserIds)
      .then(userRes => {
        if (!mounted) {
          return;
        }
        setUsers(userRes);
      })
      .catch(err => {
        if (!mounted) {
          return;
        }
        setUsers('error');
      });
    return () => {
      mounted = false;
    };
  }, [memoedUserIds]);

  return users;
};

export const UserLink = ({
  userId,
  includeName,
  placement,
  hasPopover = true,
}: UserLinkProps) => {
  const users = useUsers(userId ? [userId] : []);
  if (userId == null) {
    return <NotApplicable />;
  }
  if (users === 'load' || users === 'loading') {
    return <LoadingDots />;
  }
  if (users === 'error') {
    return <NotApplicable />;
  }
  const user = users[0];
  return (
    <UserInner
      user={user}
      placement={placement}
      includeName={includeName}
      hasPopover={hasPopover}
    />
  );
};
