/**
 * This is a GraphQL approach to querying project information.
 */

import {gql, useApolloClient} from '@apollo/client';
import {useEffect, useState} from 'react';

// Note: id is the "external" ID, which changes when a project is renamed.
//       internalId does not change.
const PROJECT_QUERY = gql`
  query Project($entityName: String!, $projectName: String!) {
    project(name: $projectName, entityName: $entityName) {
      id
      internalId
    }
  }
`;

export type ProjectInfo = {
  externalIdEncoded: string;
  internalIdEncoded: string;
};
type ProjectInfoResponseLoading = {
  loading: true;
  projectInfo: {};
};
export type MaybeProjectInfo = ProjectInfo | null;
type ProjectInfoResponseSuccess = {
  loading: false;
  projectInfo: MaybeProjectInfo;
};
type ProjectInfoResponse =
  | ProjectInfoResponseLoading
  | ProjectInfoResponseSuccess;

export const useProjectInfo = (
  entityName: string,
  projectName: string
): ProjectInfoResponse => {
  const [response, setResponse] = useState<ProjectInfoResponse>({
    loading: true,
    projectInfo: {},
  });

  const apolloClient = useApolloClient();

  useEffect(() => {
    let mounted = true;
    apolloClient
      .query({
        query: PROJECT_QUERY as any,
        variables: {
          entityName,
          projectName,
        },
      })
      .then(result => {
        if (!mounted) {
          return;
        }
        const projectInfo = result.data.project;
        if (!projectInfo) {
          // Invalid project
          setResponse({
            loading: false,
            projectInfo: null,
          });
          return;
        }
        setResponse({
          loading: false,
          projectInfo: {
            externalIdEncoded: projectInfo.id,
            internalIdEncoded: projectInfo.internalId,
          },
        });
      });
    return () => {
      mounted = false;
    };
  }, [apolloClient, entityName, projectName]);

  return response;
};
