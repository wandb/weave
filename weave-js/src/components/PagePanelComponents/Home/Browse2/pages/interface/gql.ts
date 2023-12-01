
import {gql} from '../../../../../../generated/gql';


export const UPDATE_ARTIFACT_DESCRIPTION = gql(`
  mutation UpdateArtifact(
    $artifactID: ID!
    $description: String
  ) {
    updateArtifact(
      input: {
        artifactID: $artifactID
        description: $description
      }
    ) {
      artifact {
        id
        description
      }
    }
  }
`);
