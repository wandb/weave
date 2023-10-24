import {gql} from '../../generated/gql';

export const UPDATE_ARTIFACT_COLLECTION = gql(`
  mutation UpdateArtifactCollection(
    $artifactSequenceID: ID!
    $name: String
    $description: String
  ) {
    updateArtifactSequence(
      input: {
        artifactSequenceID: $artifactSequenceID
        name: $name
        description: $description
      }
    ) {
      artifactCollection {
        id
        name
        description
      }
    }
  }
`);
