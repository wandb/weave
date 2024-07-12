import {gql, TypedDocumentNode} from '@apollo/client';
import {useIsAuthenticated} from '@wandb/weave/context/WeaveViewerContext';
import {opRootViewer, opUserUserInfo} from '@wandb/weave/core';
import {useNodeValue} from '@wandb/weave/react';
import {useEffect, useState} from 'react';

import {apolloClient} from '../../apollo';
import {useIsMounted} from './useIsMounted';

type UserInfo = Record<string, any>;
type UserInfoResponse = {
  loading: boolean;
  userInfo: UserInfo;
};

export const useViewerUserInfo = (): UserInfoResponse => {
  // Temp hack to avoid making authenticated queries without needing to
  // We should make the server handle this more gracefully
  const isAuthed = useIsAuthenticated();
  const viewerOp = opRootViewer({});
  const userInfoOp = opUserUserInfo({user: viewerOp});

  const {loading, result: viewerUserInfo} = useNodeValue(userInfoOp, {
    skip: !isAuthed,
  });

  if (!viewerUserInfo || !isAuthed) {
    return {loading, userInfo: {}};
  }
  return {
    loading,
    userInfo: JSON.parse(viewerUserInfo),
  };
};

const VIEWER_QUERY = gql`
  query Viewer2 {
    viewer {
      id
      username
    }
  }
`;

type UserInfo2 = {
  id: string;
  username: string;
};
type UserInfoResponseLoading = {
  loading: true;
  userInfo: {};
};
type UserInfoResponseSuccess = {
  loading: false;
  userInfo: UserInfo2;
};
type UserInfoResponse2 = UserInfoResponseLoading | UserInfoResponseSuccess;

// GraphQL version
export const useViewerUserInfo2 = (): UserInfoResponse2 => {
  const [userInfo, setUserInfo] = useState<UserInfo2 | null>(null);
  const isMounted = useIsMounted();
  useEffect(
    () => {
      apolloClient.query({query: VIEWER_QUERY as any}).then(result => {
        const info = result.data.viewer;
        if (isMounted()) {
          setUserInfo(info);
        }
      });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );
  if (userInfo === null) {
    return {loading: true, userInfo: {}};
  }
  return {
    loading: false,
    userInfo,
  };
};

export const getNightMode = (userInfo: UserInfo) => {
  const betaFeatures = userInfo?.betaFeatures ?? {};
  return betaFeatures.night ?? false;
};

export const UPDATE_USER_INFO = gql(`
  mutation UpdateUserInfo(
    $userInfo: JSONString
  ) {
    updateUser(
      input: {
        id: null
        userInfo: $userInfo
      }
    ) {
      user {
        id
      }
    }
  }
`) as TypedDocumentNode<any, {userInfo: string}>;

export const updateUserInfo = (userInfo: UserInfo) => {
  const variables = {
    userInfo: JSON.stringify(userInfo),
  };
  return apolloClient.mutate({
    mutation: UPDATE_USER_INFO,
    variables,
  });
};
