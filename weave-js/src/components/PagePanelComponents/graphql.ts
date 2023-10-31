import {gql} from '../../generated/gql';

export const DELETE_ARTIFACT_SEQUENCE = gql(`
  mutation DeleteArtifactSequence($artifactSequenceID: ID!) {
    deleteArtifactSequence(input: {artifactSequenceID: $artifactSequenceID}) {
      artifactCollection {
        id
      }
    }
  }
`);
