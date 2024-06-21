/**
 * This is a GraphQL approach to querying viewer information.
 * There is a query engine based approach in useViewerUserInfo.ts.
 */

import {gql} from '@apollo/client';
import {useEffect, useState} from 'react';

import {apolloClient} from '../../apollo';

const VIEWER_QUERY = gql`
  query Viewer {
    viewer {
      id
      username
    }
  }
`;

type UserInfo = {
  id: string;
  username: string;
};
type UserInfoResponseLoading = {
  loading: true;
  userInfo: {};
};
type UserInfoResponseSuccess = {
  loading: false;
  userInfo: UserInfo;
};
type UserInfoResponse = UserInfoResponseLoading | UserInfoResponseSuccess;

export const useViewerInfo = (): UserInfoResponse => {
  const [response, setResponse] = useState<UserInfoResponse>({
    loading: true,
    userInfo: {},
  });

  useEffect(() => {
    apolloClient.query({query: VIEWER_QUERY as any}).then(result => {
      const userInfo = result.data.viewer;
      setResponse({
        loading: false,
        userInfo,
      });
    });
  }, []);

  return response;
};
