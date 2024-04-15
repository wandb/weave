import {gql} from '@apollo/client';
import {Avatar, Popover, TooltipProps} from '@mui/material';
import {apolloClient} from '@wandb/weave/apollo';
import * as Colors from '@wandb/weave/common/css/color.styles';
import {NotApplicable} from '@wandb/weave/components/PagePanelComponents/Home/Browse2/NotApplicable';
import React, {useEffect, useRef, useState} from 'react';
import styled from 'styled-components';

import {Button} from './Button';
import {
  DraggableGrow,
  Popped,
  StyledTooltip,
  TooltipHint,
} from './DraggablePopups';
import {LoadingDots} from './LoadingDots';
import {A, Link} from './PagePanelComponents/Home/Browse3/pages/common/Links';

const FIND_USER_QUERY = gql`
  query FindUser($username: String!) {
    users(usernames: [$username], first: 1) {
      edges {
        node {
          id
          name
          email
          photoUrl
          deletedAt
        }
      }
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

const Th = styled.th`
  text-align: right;
`;
Th.displayName = 'S.Th';

type UserInfo = {
  id: string;
  name: string;
  email: string;
  username: string;
  photoUrl: string;
};

type UserResult = 'NA' | 'load' | 'loading' | 'error' | UserInfo;

const onClickDoNothing = (e: React.MouseEvent) => {
  e.preventDefault();
};

type UserContentProps = {
  user: UserInfo;
  mode: 'tooltip' | 'popover';
  onClose?: () => void;
};
const UserContent = ({user, mode, onClose}: UserContentProps) => {
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
      <UserContentHeader className="handle">
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
      <UserContentBody style={bodyStyle}>
        <Avatar src={user.photoUrl} sx={{width: imgSize, height: imgSize}} />
        <Grid>
          <Th>Username</Th>
          <div>{username}</div>
          <Th>Email</Th>
          <div>{email}</div>
        </Grid>
      </UserContentBody>
      {!isPopover && <TooltipHint>Click to open card</TooltipHint>}
    </>
  );
};

type UserInnerProps = {
  user: UserInfo;
  includeName?: boolean;
  placement?: TooltipProps['placement'];
};
const UserInner = ({user, includeName, placement}: UserInnerProps) => {
  const ref = useRef<HTMLDivElement>(null);
  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);
  const onClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(anchorEl ? null : ref.current);
  };
  const onClose = () => setAnchorEl(null);

  const open = Boolean(anchorEl);
  const id = open ? 'simple-popper' : undefined;

  const title = open ? (
    '' // Suppress tooltip when popper is open.
  ) : (
    <UserContent user={user} mode="tooltip" />
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
          <Avatar src={user.photoUrl} sx={{width: size, height: size}} />
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
  username: string | null;
  includeName?: boolean; // Default is to show avatar image only.
  placement?: TooltipProps['placement'];
};

export const UserLink = ({username, includeName, placement}: UserLinkProps) => {
  const [user, setUser] = useState<UserResult>(username ? 'load' : 'NA');
  useEffect(
    () => {
      if (user !== 'load') {
        return;
      }
      setUser('loading');
      apolloClient
        .query({
          query: FIND_USER_QUERY as any,
          variables: {
            username,
          },
        })
        .then(result => {
          const {edges} = result.data.users;
          console.log('result', result);
          if (edges.length > 0) {
            const u = edges[0].node;
            setUser({
              ...u,
              username,
            });
          } else {
            setUser('error');
          }
        })
        .catch(err => {
          setUser('error');
        });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );
  if (user === 'NA') {
    return <NotApplicable />;
  }
  if (user === 'load' || user === 'loading') {
    return <LoadingDots />;
  }
  if (user === 'error') {
    return <div>{username}</div>;
  }
  return (
    <UserInner user={user} placement={placement} includeName={includeName} />
  );
};
