import {gql, useApolloClient} from '@apollo/client';
import {useEffect, useState} from 'react';

import {isArtifactRegistryProject} from '../util/artifacts';
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

export const useArtifactWeaveReference = ({
  entityName,
  projectName,
  artifactName,
  skip,
}: {
  entityName: string;
  projectName: string;
  artifactName: string;
  skip?: boolean;
}) => {
  const [artInfo, setArtInfo] = useState<ArtifactWeaveReferenceInfo | null>(
    null
  );
  const [loading, setLoading] = useState(!skip);
  const isMounted = useIsMounted();
  const apolloClient = useApolloClient();

  useEffect(() => {
    if (skip) {
      return;
    }
    setLoading(true);
    apolloClient
      .query({
        query: ARTIFACT_WEAVE_REF_QUERY as any,
        variables: {
          entityName,
          projectName,
          artifactName,
        },
      })
      .then(result => {
        const organization = result?.data?.entity?.organization?.name;
        const artifactType =
          result?.data?.entity?.project?.artifact?.artifactType?.name;
        if (artifactType == null) {
          return undefined;
        }
        if (organization == null && isArtifactRegistryProject(projectName)) {
          return undefined;
        }
        const info: ArtifactWeaveReferenceInfo = {
          orgName: organization,
          artifactType,
        };
        if (isMounted()) {
          setArtInfo(info);
          setLoading(false);
        }
        return info;
      })
      .catch(err => {
        console.error('Error fetching artifact weave reference: ', err);
        if (isMounted()) {
          setArtInfo(null);
          setLoading(false);
        }
        return undefined;
      });
  }, [skip, entityName, projectName, artifactName, isMounted, apolloClient]);
  return {loading, artInfo};
};
