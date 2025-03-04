import {gql, useApolloClient} from '@apollo/client';
import {useEffect, useState} from 'react';

const SECRETS_QUERY = gql`
  query Secrets($entityName: String!) {
    entity(name: $entityName) {
      id
      secrets {
        entityId
        name
        createdAt
      }
    }
  }
`;

export type Secret = {
  entityId: string;
  name: string;
  createdAt: string;
};

type SecretsResponseLoading = {
  loading: true;
  secrets: [];
};

type SecretsResponseSuccess = {
  loading: false;
  secrets: Secret[];
};

type SecretsResponse = SecretsResponseLoading | SecretsResponseSuccess;

export const useTeamSecrets = (entityName: string): SecretsResponse => {
  const apolloClient = useApolloClient();

  const [response, setResponse] = useState<SecretsResponse>({
    loading: true,
    secrets: [],
  });

  useEffect(() => {
    let mounted = true;

    apolloClient
      .query({
        query: SECRETS_QUERY,
        variables: {
          entityName,
        },
      })
      .then(result => {
        if (!mounted) {
          return;
        }
        const entityData = result.data.entity;
        if (!entityData) {
          setResponse({
            loading: false,
            secrets: [],
          });
          return;
        }
        setResponse({
          loading: false,
          secrets: entityData.secrets,
        });
      })
      .catch(error => {
        console.error('Error fetching secrets:', error);
        if (mounted) {
          setResponse({
            loading: false,
            secrets: [],
          });
        }
      });

    return () => {
      mounted = false;
    };
  }, [apolloClient, entityName]);

  return response;
};
