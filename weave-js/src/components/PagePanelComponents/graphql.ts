import {gql} from '../../generated/gql';

export const UPDATE_ARTIFACT_COLLECTION: any = gql(`
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

export const DELETE_ARTIFACT_SEQUENCE: any = gql(`
  mutation DeleteArtifactSequence($artifactSequenceID: ID!) {
    deleteArtifactSequence(input: {artifactSequenceID: $artifactSequenceID}) {
      artifactCollection {
        id
      }
    }
  }
`);
