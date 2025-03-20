/**
 * This is a GraphQL approach to querying viewer information.
 * There is a query engine based approach in useViewerUserInfo.ts.
 */

import {gql, useApolloClient} from '@apollo/client';
import {useEffect, useState} from 'react';

const VIEWER_QUERY = gql`
  query Viewer {
    viewer {
      id
      username
      admin
      teams {
        edges {
          node {
            id
            name
            members {
              id
              username
              role
            }
          }
        }
      }
    }
  }
`;

// TODO: Would be useful to add admin mode flags
export type UserInfo = {
  id: string;
  username: string;
  teams: string[];
  admin: boolean;
  roles: {[team: string]: string};
};
export type MaybeUserInfo = UserInfo | null;

type UserInfoResponseLoading = {
  loading: true;
  userInfo: {};
};
type UserInfoResponseSuccess = {
  loading: false;
  userInfo: MaybeUserInfo;
};
type UserInfoResponse = UserInfoResponseLoading | UserInfoResponseSuccess;

export const useViewerInfo = (): UserInfoResponse => {
  const [response, setResponse] = useState<UserInfoResponse>({
    loading: true,
    userInfo: {},
  });

  const apolloClient = useApolloClient();

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
      const roles: {[team: string]: string} = {};
      teamEdges.forEach((edge: any) => {
        const teamName = edge.node.name;
        const userMember = edge.node.members.find(
          (member: any) => member.username === username
        );
        if (userMember) {
          roles[teamName] = userMember.role;
        }
      });
      setResponse({
        loading: false,
        userInfo: {
          id,
          username,
          teams,
          admin: userInfo.admin,
          roles,
        },
      });
    });
    return () => {
      mounted = false;
    };
  }, [apolloClient]);

  return response;
};
