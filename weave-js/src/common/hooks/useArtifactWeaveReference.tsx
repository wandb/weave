import {ApolloClient, gql, useApolloClient} from '@apollo/client';
import {useEffect, useState} from 'react';

import {isOrgRegistryProjectName} from '../util/artifacts';
import {useIsMounted} from './useIsMounted';

export const ARTIFACT_WEAVE_REF_QUERY = gql`
  query entity(
    $entityName: String!
    $projectName: String!
    $artifactName: String!
  ) {
    entity(name: $entityName) {
      id
      project(name: $projectName) {
        id
        artifact(name: $artifactName) {
          id
          artifactType {
            id
            name
          }
        }
      }
      organization {
        id
        name
      }
    }
  }
`;

export type ArtifactWeaveReferenceInfo = {
  orgName: string;
  artifactType: string;
};

const fetchArtifactWeaveReference = async (
  apolloClient: ApolloClient<any>,
  variables: {
    entityName: string;
    projectName: string;
    artifactName: string;
  }
): Promise<ArtifactWeaveReferenceInfo | undefined> => {
  const result = await apolloClient.query({
    query: ARTIFACT_WEAVE_REF_QUERY as any,
    variables,
  });

  const organization = result?.data?.entity?.organization?.name;
  const artifactType =
    result?.data?.entity?.project?.artifact?.artifactType?.name;

  // Early returns for invalid cases
  if (!artifactType) {
    return undefined;
  }

  if (!organization && isOrgRegistryProjectName(variables.projectName)) {
    return undefined;
  }

  return {
    orgName: organization,
    artifactType,
  };
};

export const useArtifactWeaveReference = ({
  entityName,
  projectName,
  artifactName,
  skip = false,
}: {
  entityName: string;
  projectName: string;
  artifactName: string;
  skip?: boolean;
}) => {
  const [loading, setLoading] = useState(!skip);
  const [artInfo, setArtInfo] = useState<ArtifactWeaveReferenceInfo | null>(
    null
  );
  const isMounted = useIsMounted();
  const apolloClient = useApolloClient();

  useEffect(() => {
    if (skip) {
      return;
    }

    const fetchData = async () => {
      try {
        setLoading(true);
        const info = await fetchArtifactWeaveReference(apolloClient, {
          entityName,
          projectName,
          artifactName,
        });

        if (isMounted()) {
          setArtInfo(info ?? null);
        }
      } catch (err) {
        console.error('Error fetching artifact weave reference:', err);
        if (isMounted()) {
          setArtInfo(null);
        }
      } finally {
        if (isMounted()) {
          setLoading(false);
        }
      }
    };

    fetchData();
  }, [skip, entityName, projectName, artifactName, isMounted, apolloClient]);

  return {loading, artInfo};
};
