import {gql, TypedDocumentNode, useApolloClient} from '@apollo/client';
import {useEffect, useState} from 'react';

import {useViewerInfo} from './useViewerInfo';

interface EntityMemberRolesData {
  entity: {
    id: string;
    members: Array<{
      id: string;
      username: string;
      role: string;
    }>;
  };
}

interface EntityMemberRolesVars {
  entityName: string;
}

export const ENTITY_MEMBER_ROLES_QUERY = gql`
  query EntityMemberRoles($entityName: String!) {
    entity(name: $entityName) {
      id
      members {
        id
        username
        role
      }
    }
  }
` as TypedDocumentNode<EntityMemberRolesData, EntityMemberRolesVars>;

type TeamAdminResponse = {
  loading: boolean;
  isAdmin: boolean | null;
  error?: string;
};

export const useIsTeamAdmin = (
  entityName: string,
  username: string
): TeamAdminResponse => {
  const [response, setResponse] = useState<TeamAdminResponse>({
    loading: true,
    isAdmin: null,
  });

  const apolloClient = useApolloClient();

  useEffect(() => {
    let mounted = true;

    const fetchEntityData = async () => {
      try {
        const result = await apolloClient.query({
          query: ENTITY_MEMBER_ROLES_QUERY,
          variables: {entityName},
        });

        if (!mounted) {
          return;
        }

        const entityData = result.data.entity;

        if (!entityData) {
          setResponse({
            loading: false,
            isAdmin: false,
            error: 'Team not found',
          });
          return;
        }

        const userMember = entityData.members.find(
          (member: {username: string; role: string}) =>
            member.username === username
        );

        setResponse({
          loading: false,
          isAdmin: userMember?.role === 'admin',
        });
      } catch (error) {
        if (mounted) {
          setResponse({
            loading: false,
            isAdmin: false,
            error: 'Error fetching team data',
          });
        }
      }
    };

    fetchEntityData();

    return () => {
      mounted = false;
    };
  }, [apolloClient, entityName, username]);

  return response;
};

export const useIsViewerTeamAdmin = (entityName: string): boolean => {
  const {userInfo} = useViewerInfo();
  const {isAdmin} = useIsTeamAdmin(
    entityName,
    userInfo && 'username' in userInfo ? userInfo.username : ''
  );
  return isAdmin ?? false;
};
