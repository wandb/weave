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
            createdAt
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
    $createdUsing: ViewSource,
    $description: String,
    $displayName: String,
    $entityName: String,
    $name: String,
    $parentId: ID,
    $previewUrl: String,
    $projectName: String,
    $spec: String,
    $type: String,
  ) {
    upsertView(
      input: {
        id: $id,
        coverUrl: $coverUrl,
        createdUsing: $createdUsing,
        description: $description,
        displayName: $displayName,
        entityName: $entityName,
        name: $name,
        parentId: $parentId,
        previewUrl: $previewUrl,
        projectName: $projectName,
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

export const DELETE_REPORT_DRAFT = gql(`
  mutation DeleteReportDraft($id: ID) {
    deleteView(input: {id: $id}) {
      success
    }
  }
`);
