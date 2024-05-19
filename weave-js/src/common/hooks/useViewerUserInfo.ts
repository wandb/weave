import {gql} from '@apollo/client';
import {useIsAuthenticated} from '@wandb/weave/context/WeaveViewerContext';
import {opRootViewer, opUserUserInfo} from '@wandb/weave/core';
import {useNodeValue} from '@wandb/weave/react';

import {apolloClient} from '../../apollo';

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
`);

export const updateUserInfo = (userInfo: UserInfo) => {
  const variables = {
    userInfo: JSON.stringify(userInfo),
  };
  return apolloClient.mutate({
    mutation: UPDATE_USER_INFO,
    variables,
  });
};
