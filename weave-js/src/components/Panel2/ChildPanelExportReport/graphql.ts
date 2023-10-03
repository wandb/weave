import {gql} from '../../../generated/gql';

export const GET_REPORT = gql(`
  query GetReport($id: ID!) {
    view(id: $id) {
      id
      displayName
      spec
      children {
        edges {
          node {
            id
            displayName
            spec
            user {
              id
            }
          }
        }
      }
    }
  }
`);

export const UPSERT_REPORT = gql(`
  mutation UpsertReport(
    $id: ID,
    $spec: String,
  ) {
    upsertView(
      input: {
        id: $id,
        spec: $spec,
      }
    ) {
      view {
        id
        displayName
      }
    }
  }
`);
