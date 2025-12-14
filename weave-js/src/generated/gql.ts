/* eslint-disable */
import * as types from './graphql';
import { TypedDocumentNode as DocumentNode } from '@graphql-typed-document-node/core';

/**
 * Map of all GraphQL operations in the project.
 *
 * This map has several performance disadvantages:
 * 1. It is not tree-shakeable, so it will include all operations in the project.
 * 2. It is not minifiable, so the string of a GraphQL query will be multiple times inside the bundle.
 * 3. It does not support dead code elimination, so it will add unused operations.
 *
 * Therefore it is highly recommended to use the babel or swc plugin for production.
 */
const documents = {
    "\n  query entity(\n    $entityName: String!\n    $projectName: String!\n    $artifactName: String!\n  ) {\n    entity(name: $entityName) {\n      id\n      project(name: $projectName) {\n        id\n        artifact(name: $artifactName) {\n          id\n          artifactType {\n            id\n            name\n          }\n        }\n      }\n      organization {\n        id\n        name\n      }\n    }\n  }\n": types.EntityDocument,
    "\n  query EntityMemberRoles($entityName: String!) {\n    entity(name: $entityName) {\n      id\n      members {\n        id\n        username\n        role\n      }\n    }\n  }\n": types.EntityMemberRolesDocument,
    "\n  query Organization($entityName: String) {\n    entity(name: $entityName) {\n      id\n      organization {\n        id\n        name\n      }\n    }\n  }\n": types.OrganizationDocument,
    "\n  query Project($entityName: String!, $projectName: String!) {\n    project(name: $projectName, entityName: $entityName) {\n      id\n      internalId\n    }\n  }\n": types.ProjectDocument,
    "\n  query secrets($entityName: String!) {\n    entity(name: $entityName) {\n      id\n      secrets {\n        entityId\n        name\n        createdAt\n      }\n    }\n  }\n": types.SecretsDocument,
    "\n  mutation insertSecret(\n    $entityName: String!\n    $secretName: String!\n    $secretValue: String!\n  ) {\n    insertSecret(\n      input: {\n        entityName: $entityName\n        secretName: $secretName\n        secretValue: $secretValue\n      }\n    ) {\n      success\n    }\n  }\n": types.InsertSecretDocument,
    "\n  query Viewer {\n    viewer {\n      id\n      username\n      admin\n      teams {\n        edges {\n          node {\n            id\n            name\n          }\n        }\n      }\n    }\n  }\n": types.ViewerDocument,
    "\n  query Viewer2 {\n    viewer {\n      id\n      username\n    }\n  }\n": types.Viewer2Document,
    "\n  mutation UpdateUserInfo(\n    $userInfo: JSONString\n  ) {\n    updateUser(\n      input: {\n        id: null\n        userInfo: $userInfo\n      }\n    ) {\n      user {\n        id\n      }\n    }\n  }\n": types.UpdateUserInfoDocument,
    "\n  query FindRun(\n    $entityName: String!\n    $projectName: String!\n    $runName: String!\n  ) {\n    project(name: $projectName, entityName: $entityName) {\n      run(name: $runName) {\n        id\n        name\n        displayName\n      }\n    }\n  }\n": types.FindRunDocument,
    "\n  mutation UpdateArtifactCollection(\n    $artifactSequenceID: ID!\n    $name: String\n    $description: String\n  ) {\n    updateArtifactSequence(\n      input: {\n        artifactSequenceID: $artifactSequenceID\n        name: $name\n        description: $description\n      }\n    ) {\n      artifactCollection {\n        id\n        name\n        description\n      }\n    }\n  }\n  ": types.UpdateArtifactCollectionDocument,
    "\n  mutation DeleteArtifactSequence($artifactSequenceID: ID!) {\n    deleteArtifactSequence(input: {artifactSequenceID: $artifactSequenceID}) {\n      artifactCollection {\n        id\n      }\n    }\n  }\n": types.DeleteArtifactSequenceDocument,
    "\n  query GetReport($id: ID!) {\n    view(id: $id) {\n      id\n      coverUrl\n      description\n      displayName\n      previewUrl\n      spec\n      children {\n        edges {\n          node {\n            id\n            createdAt\n            displayName\n            spec\n            user {\n              id\n            }\n          }\n        }\n      }\n    }\n  }\n": types.GetReportDocument,
    "\n  mutation UpsertReport(\n    $id: ID,\n    $coverUrl: String,\n    $createdUsing: ViewSource,\n    $description: String,\n    $displayName: String,\n    $entityName: String,\n    $name: String,\n    $parentId: ID,\n    $previewUrl: String,\n    $projectName: String,\n    $spec: String,\n    $type: String,\n  ) {\n    upsertView(\n      input: {\n        id: $id,\n        coverUrl: $coverUrl,\n        createdUsing: $createdUsing,\n        description: $description,\n        displayName: $displayName,\n        entityName: $entityName,\n        name: $name,\n        parentId: $parentId,\n        previewUrl: $previewUrl,\n        projectName: $projectName,\n        spec: $spec,\n        type: $type,\n      }\n    ) {\n      view {\n        id\n        displayName\n      }\n    }\n  }\n": types.UpsertReportDocument,
    "\n  mutation DeleteReportDraft($id: ID) {\n    deleteView(input: {id: $id}) {\n      success\n    }\n  }\n": types.DeleteReportDraftDocument,
    "\n  query FindUser($userId: ID!) {\n    user(id: $userId) {\n      id\n      name\n      email\n      photoUrl\n      deletedAt\n      username\n    }\n  }\n": types.FindUserDocument,
};

/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 *
 *
 * @example
 * ```ts
 * const query = gql(`query GetUser($id: ID!) { user(id: $id) { name } }`);
 * ```
 *
 * The query argument is unknown!
 * Please regenerate the types.
 */
export function gql(source: string): unknown;

/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  query entity(\n    $entityName: String!\n    $projectName: String!\n    $artifactName: String!\n  ) {\n    entity(name: $entityName) {\n      id\n      project(name: $projectName) {\n        id\n        artifact(name: $artifactName) {\n          id\n          artifactType {\n            id\n            name\n          }\n        }\n      }\n      organization {\n        id\n        name\n      }\n    }\n  }\n"): (typeof documents)["\n  query entity(\n    $entityName: String!\n    $projectName: String!\n    $artifactName: String!\n  ) {\n    entity(name: $entityName) {\n      id\n      project(name: $projectName) {\n        id\n        artifact(name: $artifactName) {\n          id\n          artifactType {\n            id\n            name\n          }\n        }\n      }\n      organization {\n        id\n        name\n      }\n    }\n  }\n"];
/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  query EntityMemberRoles($entityName: String!) {\n    entity(name: $entityName) {\n      id\n      members {\n        id\n        username\n        role\n      }\n    }\n  }\n"): (typeof documents)["\n  query EntityMemberRoles($entityName: String!) {\n    entity(name: $entityName) {\n      id\n      members {\n        id\n        username\n        role\n      }\n    }\n  }\n"];
/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  query Organization($entityName: String) {\n    entity(name: $entityName) {\n      id\n      organization {\n        id\n        name\n      }\n    }\n  }\n"): (typeof documents)["\n  query Organization($entityName: String) {\n    entity(name: $entityName) {\n      id\n      organization {\n        id\n        name\n      }\n    }\n  }\n"];
/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  query Project($entityName: String!, $projectName: String!) {\n    project(name: $projectName, entityName: $entityName) {\n      id\n      internalId\n    }\n  }\n"): (typeof documents)["\n  query Project($entityName: String!, $projectName: String!) {\n    project(name: $projectName, entityName: $entityName) {\n      id\n      internalId\n    }\n  }\n"];
/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  query secrets($entityName: String!) {\n    entity(name: $entityName) {\n      id\n      secrets {\n        entityId\n        name\n        createdAt\n      }\n    }\n  }\n"): (typeof documents)["\n  query secrets($entityName: String!) {\n    entity(name: $entityName) {\n      id\n      secrets {\n        entityId\n        name\n        createdAt\n      }\n    }\n  }\n"];
/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  mutation insertSecret(\n    $entityName: String!\n    $secretName: String!\n    $secretValue: String!\n  ) {\n    insertSecret(\n      input: {\n        entityName: $entityName\n        secretName: $secretName\n        secretValue: $secretValue\n      }\n    ) {\n      success\n    }\n  }\n"): (typeof documents)["\n  mutation insertSecret(\n    $entityName: String!\n    $secretName: String!\n    $secretValue: String!\n  ) {\n    insertSecret(\n      input: {\n        entityName: $entityName\n        secretName: $secretName\n        secretValue: $secretValue\n      }\n    ) {\n      success\n    }\n  }\n"];
/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  query Viewer {\n    viewer {\n      id\n      username\n      admin\n      teams {\n        edges {\n          node {\n            id\n            name\n          }\n        }\n      }\n    }\n  }\n"): (typeof documents)["\n  query Viewer {\n    viewer {\n      id\n      username\n      admin\n      teams {\n        edges {\n          node {\n            id\n            name\n          }\n        }\n      }\n    }\n  }\n"];
/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  query Viewer2 {\n    viewer {\n      id\n      username\n    }\n  }\n"): (typeof documents)["\n  query Viewer2 {\n    viewer {\n      id\n      username\n    }\n  }\n"];
/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  mutation UpdateUserInfo(\n    $userInfo: JSONString\n  ) {\n    updateUser(\n      input: {\n        id: null\n        userInfo: $userInfo\n      }\n    ) {\n      user {\n        id\n      }\n    }\n  }\n"): (typeof documents)["\n  mutation UpdateUserInfo(\n    $userInfo: JSONString\n  ) {\n    updateUser(\n      input: {\n        id: null\n        userInfo: $userInfo\n      }\n    ) {\n      user {\n        id\n      }\n    }\n  }\n"];
/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  query FindRun(\n    $entityName: String!\n    $projectName: String!\n    $runName: String!\n  ) {\n    project(name: $projectName, entityName: $entityName) {\n      run(name: $runName) {\n        id\n        name\n        displayName\n      }\n    }\n  }\n"): (typeof documents)["\n  query FindRun(\n    $entityName: String!\n    $projectName: String!\n    $runName: String!\n  ) {\n    project(name: $projectName, entityName: $entityName) {\n      run(name: $runName) {\n        id\n        name\n        displayName\n      }\n    }\n  }\n"];
/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  mutation UpdateArtifactCollection(\n    $artifactSequenceID: ID!\n    $name: String\n    $description: String\n  ) {\n    updateArtifactSequence(\n      input: {\n        artifactSequenceID: $artifactSequenceID\n        name: $name\n        description: $description\n      }\n    ) {\n      artifactCollection {\n        id\n        name\n        description\n      }\n    }\n  }\n  "): (typeof documents)["\n  mutation UpdateArtifactCollection(\n    $artifactSequenceID: ID!\n    $name: String\n    $description: String\n  ) {\n    updateArtifactSequence(\n      input: {\n        artifactSequenceID: $artifactSequenceID\n        name: $name\n        description: $description\n      }\n    ) {\n      artifactCollection {\n        id\n        name\n        description\n      }\n    }\n  }\n  "];
/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  mutation DeleteArtifactSequence($artifactSequenceID: ID!) {\n    deleteArtifactSequence(input: {artifactSequenceID: $artifactSequenceID}) {\n      artifactCollection {\n        id\n      }\n    }\n  }\n"): (typeof documents)["\n  mutation DeleteArtifactSequence($artifactSequenceID: ID!) {\n    deleteArtifactSequence(input: {artifactSequenceID: $artifactSequenceID}) {\n      artifactCollection {\n        id\n      }\n    }\n  }\n"];
/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  query GetReport($id: ID!) {\n    view(id: $id) {\n      id\n      coverUrl\n      description\n      displayName\n      previewUrl\n      spec\n      children {\n        edges {\n          node {\n            id\n            createdAt\n            displayName\n            spec\n            user {\n              id\n            }\n          }\n        }\n      }\n    }\n  }\n"): (typeof documents)["\n  query GetReport($id: ID!) {\n    view(id: $id) {\n      id\n      coverUrl\n      description\n      displayName\n      previewUrl\n      spec\n      children {\n        edges {\n          node {\n            id\n            createdAt\n            displayName\n            spec\n            user {\n              id\n            }\n          }\n        }\n      }\n    }\n  }\n"];
/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  mutation UpsertReport(\n    $id: ID,\n    $coverUrl: String,\n    $createdUsing: ViewSource,\n    $description: String,\n    $displayName: String,\n    $entityName: String,\n    $name: String,\n    $parentId: ID,\n    $previewUrl: String,\n    $projectName: String,\n    $spec: String,\n    $type: String,\n  ) {\n    upsertView(\n      input: {\n        id: $id,\n        coverUrl: $coverUrl,\n        createdUsing: $createdUsing,\n        description: $description,\n        displayName: $displayName,\n        entityName: $entityName,\n        name: $name,\n        parentId: $parentId,\n        previewUrl: $previewUrl,\n        projectName: $projectName,\n        spec: $spec,\n        type: $type,\n      }\n    ) {\n      view {\n        id\n        displayName\n      }\n    }\n  }\n"): (typeof documents)["\n  mutation UpsertReport(\n    $id: ID,\n    $coverUrl: String,\n    $createdUsing: ViewSource,\n    $description: String,\n    $displayName: String,\n    $entityName: String,\n    $name: String,\n    $parentId: ID,\n    $previewUrl: String,\n    $projectName: String,\n    $spec: String,\n    $type: String,\n  ) {\n    upsertView(\n      input: {\n        id: $id,\n        coverUrl: $coverUrl,\n        createdUsing: $createdUsing,\n        description: $description,\n        displayName: $displayName,\n        entityName: $entityName,\n        name: $name,\n        parentId: $parentId,\n        previewUrl: $previewUrl,\n        projectName: $projectName,\n        spec: $spec,\n        type: $type,\n      }\n    ) {\n      view {\n        id\n        displayName\n      }\n    }\n  }\n"];
/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  mutation DeleteReportDraft($id: ID) {\n    deleteView(input: {id: $id}) {\n      success\n    }\n  }\n"): (typeof documents)["\n  mutation DeleteReportDraft($id: ID) {\n    deleteView(input: {id: $id}) {\n      success\n    }\n  }\n"];
/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  query FindUser($userId: ID!) {\n    user(id: $userId) {\n      id\n      name\n      email\n      photoUrl\n      deletedAt\n      username\n    }\n  }\n"): (typeof documents)["\n  query FindUser($userId: ID!) {\n    user(id: $userId) {\n      id\n      name\n      email\n      photoUrl\n      deletedAt\n      username\n    }\n  }\n"];

export function gql(source: string) {
  return (documents as any)[source] ?? {};
}

export type DocumentType<TDocumentNode extends DocumentNode<any, any>> = TDocumentNode extends DocumentNode<  infer TType,  any>  ? TType  : never;