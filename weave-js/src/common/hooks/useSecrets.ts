/**
 * This is a GraphQL approach to querying viewer information.
 * There is a query engine based approach in useViewerUserInfo.ts.
 */

import {
  gql,
  TypedDocumentNode,
  useApolloClient,
  useMutation,
} from '@apollo/client';
import {useCallback,useEffect, useState} from 'react';

const SECRETS_QUERY = gql`
  query secrets($entityName: String!) {
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

const SECRETS_MUTATION = gql`
  mutation insertSecret(
    $entityName: String!
    $secretName: String!
    $secretValue: String!
  ) {
    insertSecret(
      input: {
        entityName: $entityName
        secretName: $secretName
        secretValue: $secretValue
      }
    ) {
      success
    }
  }
` as TypedDocumentNode<InsertSecretResponse, InsertSecretVariables>;

type SecretResponseLoading = {
  loading: true;
  entityId: string;
  secrets: string[];
};
type SecretResponseSuccess = {
  loading: false;
  entityId: string;
  secrets: string[];
};
type SecretResponse = SecretResponseLoading | SecretResponseSuccess;

export const useSecrets = ({
  entityName,
}: {
  entityName: string;
}): SecretResponse & {refetch: () => void} => {
  const [response, setResponse] = useState<SecretResponse>({
    loading: true,
    entityId: '',
    secrets: [],
  });

  const apolloClient = useApolloClient();

  const fetchSecrets = useCallback(
    async (isMounted?: () => boolean) => {
      try {
        const result = await apolloClient.query({
          query: SECRETS_QUERY as any,
          variables: {entityName},
          fetchPolicy: 'no-cache',
        });
        if (isMounted && !isMounted()) {
          return;
        }
        const secretPayloads = result.data.entity?.secrets ?? [];
        if (!secretPayloads) {
          setResponse({
            loading: false,
            entityId: '',
            secrets: [],
          });
          return;
        }
        const secrets = secretPayloads.map((secret: any) => secret.name).sort();
        setResponse({
          loading: false,
          entityId: result.data.entity?.id ?? '',
          secrets,
        });
      } catch (error) {
        if (!isMounted || isMounted()) {
          setResponse(prev => ({...prev, loading: false}));
        }
      }
    },
    [apolloClient, entityName]
  );

  useEffect(() => {
    let mounted = true;
    fetchSecrets(() => mounted);
    return () => {
      mounted = false;
    };
  }, [fetchSecrets]);

  return {...response, refetch: () => fetchSecrets()};
};

interface InsertSecretResponse {
  insertSecret: {
    success: boolean;
  };
}

type InsertSecretVariables = {
  entityName: string;
  secretName: string;
  secretValue: string;
};

export const useInsertSecret = () => {
  const [insertSecret] = useMutation<
    InsertSecretResponse,
    InsertSecretVariables
  >(SECRETS_MUTATION);

  return insertSecret;
};
