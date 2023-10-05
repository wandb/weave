import {gql} from '../../../generated/gql';

export const GET_REPORT = gql(`
  query GetReport($id: ID!) {
    view(id: $id) {
      id
      coverUrl
      description
      displayName
      previewUrl
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
    $coverUrl: String,
    $description: String,
    $displayName: String,
    $name: String,
    $parentId: ID,
    $previewUrl: String,
    $spec: String,
    $type: String,
  ) {
    upsertView(
      input: {
        id: $id,
        coverUrl: $coverUrl,
        description: $description,
        displayName: $displayName,
        name: $name,
        parentId: $parentId,
        previewUrl: $previewUrl,
        spec: $spec,
        type: $type,
      }
    ) {
      view {
        id
        displayName
      }
    }
  }
`);
