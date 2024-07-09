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
      teams {
        edges {
          node {
            id
            name
          }
        }
      }
    }
  }
`;

// TODO: Would be useful to add admin mode flags
type UserInfo = {
  id: string;
  username: string;
  teams: string[];
};
type UserInfoResponseLoading = {
  loading: true;
  userInfo: {};
};
type UserInfoResponseSuccess = {
  loading: false;
  userInfo: UserInfo | null;
};
type UserInfoResponse = UserInfoResponseLoading | UserInfoResponseSuccess;

export const useViewerInfo = (): UserInfoResponse => {
  const [response, setResponse] = useState<UserInfoResponse>({
    loading: true,
    userInfo: {},
  });

  useEffect(() => {
    let mounted = true;
    apolloClient.query({query: VIEWER_QUERY as any}).then(result => {
      if (!mounted) {
        return;
      }
      const userInfo = result.data.viewer;
      if (!userInfo) {
        // User is not logged in
        setResponse({
          loading: false,
          userInfo: null,
        });
        return;
      }
      const {id, username} = userInfo;
      const teamEdges = userInfo?.teams?.edges ?? [];
      const teams = teamEdges.map((edge: any) => edge.node.name).sort();
      setResponse({
        loading: false,
        userInfo: {
          id,
          username,
          teams,
        },
      });
    });
    return () => {
      mounted = false;
    };
  }, []);

  return response;
};
