/* eslint-disable */
import { TypedDocumentNode as DocumentNode } from '@graphql-typed-document-node/core';
export type Maybe<T> = T | null;
export type InputMaybe<T> = Maybe<T>;
export type Exact<T extends { [key: string]: unknown }> = { [K in keyof T]: T[K] };
export type MakeOptional<T, K extends keyof T> = Omit<T, K> & { [SubKey in K]?: Maybe<T[SubKey]> };
export type MakeMaybe<T, K extends keyof T> = Omit<T, K> & { [SubKey in K]: Maybe<T[SubKey]> };
export type MakeEmpty<T extends { [key: string]: unknown }, K extends keyof T> = { [_ in K]?: never };
export type Incremental<T> = T | { [P in keyof T]?: P extends ' $fragmentName' | '__typename' ? T[P] : never };
/** All built-in and custom scalars, mapped to their actual values */
export type Scalars = {
  ID: { input: string; output: string; }
  String: { input: string; output: string; }
  Boolean: { input: boolean; output: boolean; }
  Int: { input: number; output: number; }
  Float: { input: number; output: number; }
  DateTime: { input: any; output: any; }
  Duration: { input: any; output: any; }
  Int64: { input: any; output: any; }
  JSON: { input: any; output: any; }
  JSONString: { input: any; output: any; }
};

export type Artifact = {
  __typename?: 'Artifact';
  aliases: Array<ArtifactAlias>;
  artifactCollections: ArtifactCollectionConnection;
  artifactMemberships: ArtifactCollectionMembershipConnection;
  artifactSequence: ArtifactSequence;
  artifactType: ArtifactType;
  commitHash?: Maybe<Scalars['String']['output']>;
  createdAt: Scalars['DateTime']['output'];
  createdBy?: Maybe<Initiator>;
  currentManifest?: Maybe<ArtifactManifest>;
  description?: Maybe<Scalars['String']['output']>;
  digest: Scalars['String']['output'];
  fileCount: Scalars['Int64']['output'];
  historyStep?: Maybe<Scalars['Int64']['output']>;
  id: Scalars['ID']['output'];
  labels?: Maybe<Scalars['JSONString']['output']>;
  metadata?: Maybe<Scalars['JSONString']['output']>;
  size: Scalars['Int64']['output'];
  state: ArtifactState;
  storageBytes: Scalars['Int64']['output'];
  tags: Array<Tag>;
  ttlDurationSeconds: Scalars['Int64']['output'];
  updatedAt?: Maybe<Scalars['DateTime']['output']>;
  usedBy: RunConnection;
  usedCount: Scalars['Int']['output'];
  versionIndex?: Maybe<Scalars['Int']['output']>;
};


export type ArtifactAliasesArgs = {
  artifactCollectionName?: InputMaybe<Scalars['String']['input']>;
};


export type ArtifactCommitHashArgs = {
  artifactCollectionName?: InputMaybe<Scalars['String']['input']>;
};


export type ArtifactUsedByArgs = {
  after?: InputMaybe<Scalars['String']['input']>;
  before?: InputMaybe<Scalars['String']['input']>;
  filters?: InputMaybe<Scalars['JSONString']['input']>;
  first?: InputMaybe<Scalars['Int']['input']>;
  last?: InputMaybe<Scalars['Int']['input']>;
  order?: InputMaybe<Scalars['String']['input']>;
};


export type ArtifactVersionIndexArgs = {
  artifactCollectionName?: InputMaybe<Scalars['String']['input']>;
};

export type ArtifactAlias = {
  __typename?: 'ArtifactAlias';
  alias: Scalars['String']['output'];
  artifact?: Maybe<Artifact>;
  artifactCollection?: Maybe<ArtifactCollection>;
  artifactCollectionName: Scalars['String']['output'];
  id: Scalars['ID']['output'];
};

export type ArtifactAliasConnection = {
  __typename?: 'ArtifactAliasConnection';
  edges: Array<ArtifactAliasEdge>;
  pageInfo: PageInfo;
};

export type ArtifactAliasEdge = {
  __typename?: 'ArtifactAliasEdge';
  cursor: Scalars['String']['output'];
  node?: Maybe<ArtifactAlias>;
};

export type ArtifactCollection = {
  aliases: ArtifactAliasConnection;
  artifactMembership?: Maybe<ArtifactCollectionMembership>;
  artifactMemberships: ArtifactCollectionMembershipConnection;
  artifacts?: Maybe<VersionedArtifactConnection>;
  createdAt: Scalars['DateTime']['output'];
  defaultArtifactType: ArtifactType;
  description?: Maybe<Scalars['String']['output']>;
  id: Scalars['ID']['output'];
  name: Scalars['String']['output'];
  project: Project;
  tags: TagConnection;
};


export type ArtifactCollectionAliasesArgs = {
  first?: InputMaybe<Scalars['Int']['input']>;
};


export type ArtifactCollectionArtifactMembershipArgs = {
  aliasName: Scalars['String']['input'];
};


export type ArtifactCollectionArtifactMembershipsArgs = {
  first?: InputMaybe<Scalars['Int']['input']>;
};


export type ArtifactCollectionArtifactsArgs = {
  first?: InputMaybe<Scalars['Int']['input']>;
};

export type ArtifactCollectionConnection = {
  __typename?: 'ArtifactCollectionConnection';
  edges: Array<ArtifactCollectionEdge>;
  pageInfo: PageInfo;
  totalCount: Scalars['Int']['output'];
};

export type ArtifactCollectionEdge = {
  __typename?: 'ArtifactCollectionEdge';
  cursor: Scalars['String']['output'];
  node?: Maybe<ArtifactCollection>;
};

export type ArtifactCollectionMembership = {
  __typename?: 'ArtifactCollectionMembership';
  aliases: Array<ArtifactAlias>;
  artifact?: Maybe<Artifact>;
  artifactCollection?: Maybe<ArtifactCollection>;
  commitHash?: Maybe<Scalars['String']['output']>;
  createdAt: Scalars['DateTime']['output'];
  id: Scalars['ID']['output'];
  versionIndex?: Maybe<Scalars['Int']['output']>;
};

export type ArtifactCollectionMembershipConnection = {
  __typename?: 'ArtifactCollectionMembershipConnection';
  edges: Array<ArtifactCollectionMembershipEdge>;
  pageInfo: PageInfo;
};

export type ArtifactCollectionMembershipEdge = {
  __typename?: 'ArtifactCollectionMembershipEdge';
  cursor: Scalars['String']['output'];
  node?: Maybe<ArtifactCollectionMembership>;
};

export enum ArtifactCollectionType {
  Portfolio = 'PORTFOLIO',
  Sequence = 'SEQUENCE'
}

export type ArtifactConnection = ArtifactConnectionType & {
  __typename?: 'ArtifactConnection';
  edges: Array<ArtifactEdge>;
  pageInfo: PageInfo;
  totalCount: Scalars['Int']['output'];
};

export type ArtifactConnectionType = {
  edges: Array<ArtifactEdgeType>;
  pageInfo: PageInfo;
  totalCount: Scalars['Int']['output'];
};

export type ArtifactEdge = ArtifactEdgeType & {
  __typename?: 'ArtifactEdge';
  cursor: Scalars['String']['output'];
  node?: Maybe<Artifact>;
};

export type ArtifactEdgeType = {
  cursor: Scalars['String']['output'];
  node?: Maybe<Artifact>;
};

export type ArtifactManifest = {
  __typename?: 'ArtifactManifest';
  artifact: Artifact;
  createdAt: Scalars['DateTime']['output'];
  digest: Scalars['String']['output'];
  id: Scalars['ID']['output'];
  type: ArtifactManifestType;
};

export type ArtifactManifestConnection = {
  __typename?: 'ArtifactManifestConnection';
  edges: Array<ArtifactManifestEdge>;
  pageInfo: PageInfo;
};

export type ArtifactManifestEdge = {
  __typename?: 'ArtifactManifestEdge';
  cursor: Scalars['String']['output'];
  node?: Maybe<ArtifactManifest>;
};

export enum ArtifactManifestType {
  Full = 'FULL',
  Incremental = 'INCREMENTAL',
  Patch = 'PATCH'
}

export type ArtifactPortfolio = ArtifactCollection & {
  __typename?: 'ArtifactPortfolio';
  aliases: ArtifactAliasConnection;
  artifactMembership?: Maybe<ArtifactCollectionMembership>;
  artifactMemberships: ArtifactCollectionMembershipConnection;
  artifacts: VersionedArtifactConnection;
  createdAt: Scalars['DateTime']['output'];
  defaultArtifactType: ArtifactType;
  description?: Maybe<Scalars['String']['output']>;
  id: Scalars['ID']['output'];
  name: Scalars['String']['output'];
  project: Project;
};


export type ArtifactPortfolioAliasesArgs = {
  first?: InputMaybe<Scalars['Int']['input']>;
};


export type ArtifactPortfolioArtifactMembershipArgs = {
  aliasName: Scalars['String']['input'];
};


export type ArtifactPortfolioArtifactMembershipsArgs = {
  first?: InputMaybe<Scalars['Int']['input']>;
};


export type ArtifactPortfolioArtifactsArgs = {
  first?: InputMaybe<Scalars['Int']['input']>;
};

export type ArtifactSequence = ArtifactCollection & {
  __typename?: 'ArtifactSequence';
  aliases: ArtifactAliasConnection;
  artifactMembership?: Maybe<ArtifactCollectionMembership>;
  artifactMemberships: ArtifactCollectionMembershipConnection;
  artifacts: VersionedArtifactConnection;
  createdAt: Scalars['DateTime']['output'];
  defaultArtifactType: ArtifactType;
  description?: Maybe<Scalars['String']['output']>;
  id: Scalars['ID']['output'];
  name: Scalars['String']['output'];
  project: Project;
};


export type ArtifactSequenceAliasesArgs = {
  first?: InputMaybe<Scalars['Int']['input']>;
};


export type ArtifactSequenceArtifactMembershipArgs = {
  aliasName: Scalars['String']['input'];
};


export type ArtifactSequenceArtifactMembershipsArgs = {
  first?: InputMaybe<Scalars['Int']['input']>;
};


export type ArtifactSequenceArtifactsArgs = {
  first?: InputMaybe<Scalars['Int']['input']>;
};

export type ArtifactSequenceConnection = {
  __typename?: 'ArtifactSequenceConnection';
  edges: Array<ArtifactSequenceEdge>;
  pageInfo: PageInfo;
  totalCount: Scalars['Int']['output'];
};

export type ArtifactSequenceEdge = {
  __typename?: 'ArtifactSequenceEdge';
  cursor: Scalars['String']['output'];
  node?: Maybe<ArtifactSequence>;
};

export enum ArtifactState {
  Committed = 'COMMITTED',
  Deleted = 'DELETED',
  Pending = 'PENDING'
}

export type ArtifactType = {
  __typename?: 'ArtifactType';
  artifact?: Maybe<Artifact>;
  artifactCollections?: Maybe<ArtifactCollectionConnection>;
  id: Scalars['ID']['output'];
  name: Scalars['String']['output'];
  project: Project;
};


export type ArtifactTypeArtifactArgs = {
  name: Scalars['String']['input'];
};


export type ArtifactTypeArtifactCollectionsArgs = {
  first?: InputMaybe<Scalars['Int']['input']>;
};

export type ArtifactTypeConnection = {
  __typename?: 'ArtifactTypeConnection';
  edges: Array<ArtifactTypeEdge>;
  pageInfo: PageInfo;
};

export type ArtifactTypeEdge = {
  __typename?: 'ArtifactTypeEdge';
  cursor: Scalars['String']['output'];
  node?: Maybe<ArtifactType>;
};

export type DeleteArtifactCollectionPayload = {
  __typename?: 'DeleteArtifactCollectionPayload';
  artifactCollection: ArtifactCollection;
  clientMutationId?: Maybe<Scalars['String']['output']>;
};

export type DeleteArtifactSequenceInput = {
  artifactSequenceID: Scalars['ID']['input'];
  clientMutationId?: InputMaybe<Scalars['String']['input']>;
};

export type DeleteViewInput = {
  clientMutationId?: InputMaybe<Scalars['String']['input']>;
  deleteDrafts?: InputMaybe<Scalars['Boolean']['input']>;
  id?: InputMaybe<Scalars['ID']['input']>;
};

export type DeleteViewPayload = {
  __typename?: 'DeleteViewPayload';
  clientMutationId?: Maybe<Scalars['String']['output']>;
  pendingDrafts?: Maybe<Scalars['Boolean']['output']>;
  success?: Maybe<Scalars['Boolean']['output']>;
};

export type Entity = Node & {
  __typename?: 'Entity';
  artifactCollections?: Maybe<ArtifactCollectionConnection>;
  id: Scalars['ID']['output'];
  isTeam: Scalars['Boolean']['output'];
  members: Array<Member>;
  name: Scalars['String']['output'];
  organization?: Maybe<Organization>;
  project?: Maybe<Project>;
  projects?: Maybe<ProjectConnection>;
  secrets: Array<Secret>;
};


export type EntityArtifactCollectionsArgs = {
  after?: InputMaybe<Scalars['String']['input']>;
  before?: InputMaybe<Scalars['String']['input']>;
  collectionTypes?: InputMaybe<Array<ArtifactCollectionType>>;
  filters?: InputMaybe<Scalars['JSONString']['input']>;
  first?: InputMaybe<Scalars['Int']['input']>;
  last?: InputMaybe<Scalars['Int']['input']>;
  order?: InputMaybe<Scalars['String']['input']>;
};


export type EntityProjectArgs = {
  name?: InputMaybe<Scalars['String']['input']>;
};


export type EntityProjectsArgs = {
  after?: InputMaybe<Scalars['String']['input']>;
  before?: InputMaybe<Scalars['String']['input']>;
  first?: InputMaybe<Scalars['Int']['input']>;
  last?: InputMaybe<Scalars['Int']['input']>;
  order?: InputMaybe<Scalars['String']['input']>;
};

export type EntityConnection = {
  __typename?: 'EntityConnection';
  edges: Array<EntityEdge>;
};

export type EntityEdge = {
  __typename?: 'EntityEdge';
  cursor: Scalars['String']['output'];
  node?: Maybe<Entity>;
};

export type Error = {
  message: Scalars['String']['output'];
};

export enum ErrorSeverity {
  Error = 'ERROR',
  Warn = 'WARN'
}

export type ImageUrl = {
  __typename?: 'ImageUrl';
  path?: Maybe<Scalars['String']['output']>;
  publicUrl?: Maybe<Scalars['String']['output']>;
  url?: Maybe<Scalars['String']['output']>;
};

export type Initiator = Run | User;

export type InputArtifactConnection = ArtifactConnectionType & {
  __typename?: 'InputArtifactConnection';
  edges: Array<InputArtifactEdge>;
  pageInfo: PageInfo;
  totalCount: Scalars['Int']['output'];
};

export type InputArtifactEdge = ArtifactEdgeType & {
  __typename?: 'InputArtifactEdge';
  cursor: Scalars['String']['output'];
  node?: Maybe<Artifact>;
  usedAs: Array<Scalars['String']['output']>;
};

export type InsertSecretInput = {
  clientMutationId?: InputMaybe<Scalars['String']['input']>;
  entityName: Scalars['String']['input'];
  secretName: Scalars['String']['input'];
  secretValue: Scalars['String']['input'];
};

export type InsertSecretPayload = {
  __typename?: 'InsertSecretPayload';
  clientMutationId?: Maybe<Scalars['String']['output']>;
  success: Scalars['Boolean']['output'];
};

export type Member = {
  __typename?: 'Member';
  id?: Maybe<Scalars['String']['output']>;
  role?: Maybe<Scalars['String']['output']>;
  username?: Maybe<Scalars['String']['output']>;
};

export type Mutation = {
  __typename?: 'Mutation';
  deleteArtifactSequence?: Maybe<DeleteArtifactCollectionPayload>;
  deleteView?: Maybe<DeleteViewPayload>;
  insertSecret?: Maybe<InsertSecretPayload>;
  updateArtifactSequence?: Maybe<UpdateArtifactCollectionPayload>;
  updateUser?: Maybe<UpdateUserPayload>;
  upsertView?: Maybe<UpsertViewPayload>;
};


export type MutationDeleteArtifactSequenceArgs = {
  input: DeleteArtifactSequenceInput;
};


export type MutationDeleteViewArgs = {
  input: DeleteViewInput;
};


export type MutationInsertSecretArgs = {
  input: InsertSecretInput;
};


export type MutationUpdateArtifactSequenceArgs = {
  input: UpdateArtifactSequenceInput;
};


export type MutationUpdateUserArgs = {
  input: UpdateUserInput;
};


export type MutationUpsertViewArgs = {
  input: UpsertViewInput;
};

export type Node = {
  id: Scalars['ID']['output'];
};

export enum OrgType {
  Organization = 'ORGANIZATION',
  Personal = 'PERSONAL'
}

export type Organization = Node & {
  __typename?: 'Organization';
  artifactCollections?: Maybe<ArtifactCollectionConnection>;
  id: Scalars['ID']['output'];
  name: Scalars['String']['output'];
  projects?: Maybe<ProjectConnection>;
  views: ViewConnection;
};


export type OrganizationArtifactCollectionsArgs = {
  first?: InputMaybe<Scalars['Int']['input']>;
};


export type OrganizationProjectsArgs = {
  first?: InputMaybe<Scalars['Int']['input']>;
};


export type OrganizationViewsArgs = {
  first?: InputMaybe<Scalars['Int']['input']>;
};

export type OrganizationConnection = {
  __typename?: 'OrganizationConnection';
  edges: Array<OrganizationEdge>;
  pageInfo: PageInfo;
};

export type OrganizationEdge = {
  __typename?: 'OrganizationEdge';
  cursor: Scalars['String']['output'];
  node: Organization;
};

export type PageInfo = {
  __typename?: 'PageInfo';
  endCursor?: Maybe<Scalars['String']['output']>;
  hasNextPage: Scalars['Boolean']['output'];
  hasPreviousPage: Scalars['Boolean']['output'];
  startCursor?: Maybe<Scalars['String']['output']>;
};

export type ParquetHistory = {
  __typename?: 'ParquetHistory';
  liveData: Array<Scalars['JSON']['output']>;
  parquetUrls: Array<Scalars['String']['output']>;
};

export type Project = Node & {
  __typename?: 'Project';
  artifact?: Maybe<Artifact>;
  artifactCollection?: Maybe<ArtifactCollection>;
  artifactCollections?: Maybe<ArtifactCollectionConnection>;
  artifactType?: Maybe<ArtifactType>;
  artifactTypes: ArtifactTypeConnection;
  createdAt: Scalars['DateTime']['output'];
  entity: Entity;
  id: Scalars['ID']['output'];
  internalId: Scalars['ID']['output'];
  name: Scalars['String']['output'];
  run?: Maybe<Run>;
  runQueues: Array<RunQueue>;
  runs?: Maybe<RunConnection>;
  updatedAt?: Maybe<Scalars['DateTime']['output']>;
  user?: Maybe<User>;
};


export type ProjectArtifactArgs = {
  name: Scalars['String']['input'];
};


export type ProjectArtifactCollectionArgs = {
  name: Scalars['String']['input'];
};


export type ProjectArtifactCollectionsArgs = {
  first?: InputMaybe<Scalars['Int']['input']>;
};


export type ProjectArtifactTypeArgs = {
  name: Scalars['String']['input'];
};


export type ProjectArtifactTypesArgs = {
  first?: InputMaybe<Scalars['Int']['input']>;
};


export type ProjectRunArgs = {
  name: Scalars['String']['input'];
};


export type ProjectRunsArgs = {
  filters?: InputMaybe<Scalars['JSONString']['input']>;
  first?: InputMaybe<Scalars['Int']['input']>;
  order?: InputMaybe<Scalars['String']['input']>;
};

export type ProjectConnection = {
  __typename?: 'ProjectConnection';
  edges: Array<ProjectEdge>;
  pageInfo: PageInfo;
};

export type ProjectEdge = {
  __typename?: 'ProjectEdge';
  cursor: Scalars['String']['output'];
  node?: Maybe<Project>;
};

export type ProjectIdentifierInput = {
  EntityName?: InputMaybe<Scalars['String']['input']>;
  Name?: InputMaybe<Scalars['String']['input']>;
};

export type PublicImageUploadInfo = {
  __typename?: 'PublicImageUploadInfo';
  imageUrl: Scalars['String']['output'];
  uploadHeaders: Array<Scalars['String']['output']>;
  uploadUrl: Scalars['String']['output'];
};

export type Query = {
  __typename?: 'Query';
  artifact?: Maybe<Artifact>;
  artifactCollection?: Maybe<ArtifactCollection>;
  artifactSequence?: Maybe<ArtifactSequence>;
  entities?: Maybe<EntityConnection>;
  entity?: Maybe<Entity>;
  instance?: Maybe<WbInstance>;
  organization?: Maybe<Organization>;
  organizations: OrganizationConnection;
  project?: Maybe<Project>;
  projects?: Maybe<ProjectConnection>;
  repo?: Maybe<Repo>;
  repoInsightsPlotData?: Maybe<RepoInsightsRowConnection>;
  user?: Maybe<User>;
  users?: Maybe<UserConnection>;
  view?: Maybe<View>;
  viewer?: Maybe<User>;
  views?: Maybe<ViewConnection>;
};


export type QueryArtifactArgs = {
  id: Scalars['ID']['input'];
};


export type QueryArtifactCollectionArgs = {
  id: Scalars['ID']['input'];
};


export type QueryArtifactSequenceArgs = {
  id: Scalars['ID']['input'];
};


export type QueryEntitiesArgs = {
  after?: InputMaybe<Scalars['String']['input']>;
  before?: InputMaybe<Scalars['String']['input']>;
  first?: InputMaybe<Scalars['Int']['input']>;
  last?: InputMaybe<Scalars['Int']['input']>;
  order?: InputMaybe<Scalars['String']['input']>;
};


export type QueryEntityArgs = {
  login?: InputMaybe<Scalars['Boolean']['input']>;
  name?: InputMaybe<Scalars['String']['input']>;
};


export type QueryOrganizationArgs = {
  id?: InputMaybe<Scalars['ID']['input']>;
  name?: InputMaybe<Scalars['String']['input']>;
};


export type QueryOrganizationsArgs = {
  after?: InputMaybe<Scalars['String']['input']>;
  before?: InputMaybe<Scalars['String']['input']>;
  emailDomain?: InputMaybe<Scalars['String']['input']>;
  first?: InputMaybe<Scalars['Int']['input']>;
  ids?: InputMaybe<Array<Scalars['ID']['input']>>;
  last?: InputMaybe<Scalars['Int']['input']>;
  query?: InputMaybe<Scalars['String']['input']>;
};


export type QueryProjectArgs = {
  entityName?: InputMaybe<Scalars['String']['input']>;
  name?: InputMaybe<Scalars['String']['input']>;
};


export type QueryProjectsArgs = {
  after?: InputMaybe<Scalars['String']['input']>;
  anonymous?: InputMaybe<Scalars['Boolean']['input']>;
  before?: InputMaybe<Scalars['String']['input']>;
  entityName?: InputMaybe<Scalars['String']['input']>;
  first?: InputMaybe<Scalars['Int']['input']>;
  last?: InputMaybe<Scalars['Int']['input']>;
  order?: InputMaybe<Scalars['String']['input']>;
};


export type QueryRepoArgs = {
  id: Scalars['ID']['input'];
};


export type QueryRepoInsightsPlotDataArgs = {
  after?: InputMaybe<Scalars['String']['input']>;
  before?: InputMaybe<Scalars['String']['input']>;
  columns?: InputMaybe<Array<Scalars['String']['input']>>;
  filters?: InputMaybe<Scalars['JSONString']['input']>;
  first?: InputMaybe<Scalars['Int']['input']>;
  groupKeys?: InputMaybe<Array<Scalars['String']['input']>>;
  last?: InputMaybe<Scalars['Int']['input']>;
  order?: InputMaybe<Scalars['String']['input']>;
  plotName: Scalars['String']['input'];
  repoName: Scalars['String']['input'];
};


export type QueryUserArgs = {
  id?: InputMaybe<Scalars['ID']['input']>;
  userName?: InputMaybe<Scalars['String']['input']>;
};


export type QueryUsersArgs = {
  after?: InputMaybe<Scalars['String']['input']>;
  before?: InputMaybe<Scalars['String']['input']>;
  first?: InputMaybe<Scalars['Int']['input']>;
  ids?: InputMaybe<Array<Scalars['ID']['input']>>;
  last?: InputMaybe<Scalars['Int']['input']>;
  query?: InputMaybe<Scalars['String']['input']>;
  usernames?: InputMaybe<Array<Scalars['String']['input']>>;
};


export type QueryViewArgs = {
  id: Scalars['ID']['input'];
  type?: InputMaybe<Scalars['String']['input']>;
};


export type QueryViewerArgs = {
  entityName?: InputMaybe<Scalars['String']['input']>;
};


export type QueryViewsArgs = {
  ids: Array<Scalars['ID']['input']>;
};

export type Repo = Node & {
  __typename?: 'Repo';
  displayName: Scalars['String']['output'];
  entity: Entity;
  id: Scalars['ID']['output'];
};

export type RepoConnection = {
  __typename?: 'RepoConnection';
  edges: Array<RepoEdge>;
};

export type RepoEdge = {
  __typename?: 'RepoEdge';
  cursor: Scalars['String']['output'];
  node?: Maybe<Repo>;
};

export type RepoInsightsRowConnection = {
  __typename?: 'RepoInsightsRowConnection';
  edges: Array<RowEdge>;
  isNormalizedUserCount: Scalars['Boolean']['output'];
  pageInfo: PageInfo;
  schema: Scalars['JSON']['output'];
  totalCount: Scalars['Int']['output'];
};

export type RowConnection = {
  __typename?: 'RowConnection';
  edges: Array<RowEdge>;
  pageInfo: PageInfo;
  schema: Scalars['JSON']['output'];
  totalCount: Scalars['Int']['output'];
};

export type RowEdge = {
  __typename?: 'RowEdge';
  node?: Maybe<RowType>;
};

export type RowType = {
  __typename?: 'RowType';
  row: Scalars['JSON']['output'];
};

export type Run = Node & {
  __typename?: 'Run';
  computeSeconds: Scalars['Duration']['output'];
  config?: Maybe<Scalars['JSONString']['output']>;
  createdAt: Scalars['DateTime']['output'];
  displayName?: Maybe<Scalars['String']['output']>;
  heartbeatAt?: Maybe<Scalars['DateTime']['output']>;
  history: Array<Scalars['String']['output']>;
  historyKeys?: Maybe<Scalars['JSON']['output']>;
  historyLineCount?: Maybe<Scalars['Int']['output']>;
  id: Scalars['ID']['output'];
  inputArtifacts?: Maybe<InputArtifactConnection>;
  jobType?: Maybe<Scalars['String']['output']>;
  name: Scalars['String']['output'];
  outputArtifacts?: Maybe<ArtifactConnection>;
  parquetHistory: ParquetHistory;
  project?: Maybe<Project>;
  summaryMetrics?: Maybe<Scalars['JSONString']['output']>;
  user?: Maybe<User>;
};


export type RunConfigArgs = {
  keys?: InputMaybe<Array<Scalars['String']['input']>>;
};


export type RunHistoryArgs = {
  maxStep?: InputMaybe<Scalars['Int64']['input']>;
  minStep?: InputMaybe<Scalars['Int64']['input']>;
};


export type RunInputArtifactsArgs = {
  first?: InputMaybe<Scalars['Int']['input']>;
};


export type RunOutputArtifactsArgs = {
  first?: InputMaybe<Scalars['Int']['input']>;
};


export type RunParquetHistoryArgs = {
  liveKeys: Array<Scalars['String']['input']>;
};


export type RunSummaryMetricsArgs = {
  keys?: InputMaybe<Array<Scalars['String']['input']>>;
};

export type RunConnection = {
  __typename?: 'RunConnection';
  edges: Array<RunEdge>;
  pageInfo: PageInfo;
  totalCount: Scalars['Int']['output'];
};

export type RunEdge = {
  __typename?: 'RunEdge';
  cursor: Scalars['String']['output'];
  node: Run;
};

export type RunQueue = {
  __typename?: 'RunQueue';
  id: Scalars['ID']['output'];
};

export type Secret = {
  __typename?: 'Secret';
  createdAt: Scalars['DateTime']['output'];
  entityId: Scalars['Int']['output'];
  name: Scalars['String']['output'];
};

export type Tag = {
  __typename?: 'Tag';
  attributes: Scalars['JSONString']['output'];
  id: Scalars['ID']['output'];
  name: Scalars['String']['output'];
  tagCategoryName: Scalars['String']['output'];
};

export type TagConnection = {
  __typename?: 'TagConnection';
  edges: Array<TagEdge>;
  pageInfo: PageInfo;
};

export type TagEdge = {
  __typename?: 'TagEdge';
  cursor: Scalars['String']['output'];
  node: Tag;
};

export type TimeWindow = {
  end: Scalars['DateTime']['input'];
  start: Scalars['DateTime']['input'];
};

export type UpdateArtifactCollectionPayload = {
  __typename?: 'UpdateArtifactCollectionPayload';
  artifactCollection: ArtifactCollection;
  clientMutationId?: Maybe<Scalars['String']['output']>;
};

export type UpdateArtifactSequenceInput = {
  artifactSequenceID: Scalars['ID']['input'];
  clientMutationId?: InputMaybe<Scalars['String']['input']>;
  description?: InputMaybe<Scalars['String']['input']>;
  name?: InputMaybe<Scalars['String']['input']>;
};

export type UpdateUserInput = {
  admin?: InputMaybe<Scalars['Boolean']['input']>;
  clientMutationId?: InputMaybe<Scalars['String']['input']>;
  code?: InputMaybe<Scalars['String']['input']>;
  defaultEntity?: InputMaybe<Scalars['String']['input']>;
  defaultFramework?: InputMaybe<Scalars['String']['input']>;
  galleryVisited?: InputMaybe<Scalars['Boolean']['input']>;
  hideTeamsFromPublic?: InputMaybe<Scalars['Boolean']['input']>;
  id?: InputMaybe<Scalars['ID']['input']>;
  name?: InputMaybe<Scalars['String']['input']>;
  onboardingHidden?: InputMaybe<Scalars['Boolean']['input']>;
  password?: InputMaybe<Scalars['String']['input']>;
  photoUrl?: InputMaybe<Scalars['String']['input']>;
  primaryEmail?: InputMaybe<Scalars['String']['input']>;
  private?: InputMaybe<Scalars['Boolean']['input']>;
  settingsVisited?: InputMaybe<Scalars['Boolean']['input']>;
  userInfo?: InputMaybe<Scalars['JSONString']['input']>;
};

export type UpdateUserPayload = {
  __typename?: 'UpdateUserPayload';
  clientMutationId?: Maybe<Scalars['String']['output']>;
  user?: Maybe<User>;
};

export type UpsertViewInput = {
  clientMutationId?: InputMaybe<Scalars['String']['input']>;
  coverUrl?: InputMaybe<Scalars['String']['input']>;
  createdUsing?: InputMaybe<ViewSource>;
  description?: InputMaybe<Scalars['String']['input']>;
  displayName?: InputMaybe<Scalars['String']['input']>;
  entityName?: InputMaybe<Scalars['String']['input']>;
  id?: InputMaybe<Scalars['ID']['input']>;
  locked?: InputMaybe<Scalars['Boolean']['input']>;
  name?: InputMaybe<Scalars['String']['input']>;
  parentId?: InputMaybe<Scalars['ID']['input']>;
  previewUrl?: InputMaybe<Scalars['String']['input']>;
  projectName?: InputMaybe<Scalars['String']['input']>;
  showcasedAt?: InputMaybe<Scalars['DateTime']['input']>;
  spec?: InputMaybe<Scalars['String']['input']>;
  type?: InputMaybe<Scalars['String']['input']>;
};

export type UpsertViewPayload = {
  __typename?: 'UpsertViewPayload';
  clientMutationId?: Maybe<Scalars['String']['output']>;
  inserted?: Maybe<Scalars['Boolean']['output']>;
  view?: Maybe<View>;
};

export type User = Node & {
  __typename?: 'User';
  admin?: Maybe<Scalars['Boolean']['output']>;
  deletedAt?: Maybe<Scalars['DateTime']['output']>;
  email?: Maybe<Scalars['String']['output']>;
  id: Scalars['ID']['output'];
  name: Scalars['String']['output'];
  photoUrl?: Maybe<Scalars['String']['output']>;
  teams?: Maybe<EntityConnection>;
  username?: Maybe<Scalars['String']['output']>;
};


export type UserTeamsArgs = {
  after?: InputMaybe<Scalars['String']['input']>;
  before?: InputMaybe<Scalars['String']['input']>;
  first?: InputMaybe<Scalars['Int']['input']>;
  last?: InputMaybe<Scalars['Int']['input']>;
};

export type UserConnection = {
  __typename?: 'UserConnection';
  edges: Array<UserEdge>;
  pageInfo: PageInfo;
};

export type UserEdge = {
  __typename?: 'UserEdge';
  cursor: Scalars['String']['output'];
  node?: Maybe<User>;
};

export type VersionedArtifactConnection = ArtifactConnectionType & {
  __typename?: 'VersionedArtifactConnection';
  edges: Array<VersionedArtifactEdge>;
  pageInfo: PageInfo;
  totalCount: Scalars['Int']['output'];
};

export type VersionedArtifactEdge = ArtifactEdgeType & {
  __typename?: 'VersionedArtifactEdge';
  cursor: Scalars['String']['output'];
  node: Artifact;
  version: Scalars['String']['output'];
};

export type View = Node & {
  __typename?: 'View';
  children?: Maybe<ViewConnection>;
  coverUrl?: Maybe<Scalars['String']['output']>;
  createdAt: Scalars['DateTime']['output'];
  createdUsing: ViewSource;
  description?: Maybe<Scalars['String']['output']>;
  displayName?: Maybe<Scalars['String']['output']>;
  entity?: Maybe<Entity>;
  entityName: Scalars['String']['output'];
  id: Scalars['ID']['output'];
  imageUploadUrl: ImageUrl;
  locked: Scalars['Boolean']['output'];
  name?: Maybe<Scalars['String']['output']>;
  parentId?: Maybe<Scalars['ID']['output']>;
  previewUrl?: Maybe<Scalars['String']['output']>;
  project?: Maybe<Project>;
  projectId?: Maybe<Scalars['Int']['output']>;
  projectName: Scalars['String']['output'];
  showcasedAt?: Maybe<Scalars['DateTime']['output']>;
  spec?: Maybe<Scalars['JSONString']['output']>;
  starCount: Scalars['Int']['output'];
  starred?: Maybe<Scalars['Boolean']['output']>;
  type?: Maybe<Scalars['String']['output']>;
  updatedAt?: Maybe<Scalars['DateTime']['output']>;
  updatedBy?: Maybe<User>;
  uploadHeaders: Array<Scalars['String']['output']>;
  user?: Maybe<User>;
  userId?: Maybe<Scalars['Int']['output']>;
  viewCount: Scalars['Int']['output'];
};


export type ViewImageUploadUrlArgs = {
  name: Scalars['String']['input'];
};


export type ViewStarCountArgs = {
  from?: InputMaybe<Scalars['DateTime']['input']>;
  to?: InputMaybe<Scalars['DateTime']['input']>;
};

export type ViewConnection = {
  __typename?: 'ViewConnection';
  edges: Array<ViewEdge>;
  pageInfo: PageInfo;
  totalCount: Scalars['Int']['output'];
};

export type ViewEdge = {
  __typename?: 'ViewEdge';
  cursor: Scalars['String']['output'];
  node?: Maybe<View>;
};

export enum ViewSource {
  WandbSdk = 'WANDB_SDK',
  WandbUi = 'WANDB_UI',
  WandbUiSharePanel = 'WANDB_UI_SHARE_PANEL',
  WeaveUi = 'WEAVE_UI'
}

export type WbInstance = {
  __typename?: 'WBInstance';
  artifactSequences?: Maybe<ArtifactSequenceConnection>;
  entities: Array<Entity>;
  projects?: Maybe<ProjectConnection>;
  views: ViewConnection;
};


export type WbInstanceArtifactSequencesArgs = {
  first?: InputMaybe<Scalars['Int']['input']>;
};


export type WbInstanceProjectsArgs = {
  first?: InputMaybe<Scalars['Int']['input']>;
};


export type WbInstanceViewsArgs = {
  first?: InputMaybe<Scalars['Int']['input']>;
};

export type EntityQueryVariables = Exact<{
  entityName: Scalars['String']['input'];
  projectName: Scalars['String']['input'];
  artifactName: Scalars['String']['input'];
}>;


export type EntityQuery = { __typename?: 'Query', entity?: { __typename?: 'Entity', id: string, project?: { __typename?: 'Project', id: string, artifact?: { __typename?: 'Artifact', id: string, artifactType: { __typename?: 'ArtifactType', id: string, name: string } } | null } | null, organization?: { __typename?: 'Organization', id: string, name: string } | null } | null };

export type EntityMemberRolesQueryVariables = Exact<{
  entityName: Scalars['String']['input'];
}>;


export type EntityMemberRolesQuery = { __typename?: 'Query', entity?: { __typename?: 'Entity', id: string, members: Array<{ __typename?: 'Member', id?: string | null, username?: string | null, role?: string | null }> } | null };

export type OrganizationQueryVariables = Exact<{
  entityName?: InputMaybe<Scalars['String']['input']>;
}>;


export type OrganizationQuery = { __typename?: 'Query', entity?: { __typename?: 'Entity', id: string, organization?: { __typename?: 'Organization', id: string, name: string } | null } | null };

export type ProjectQueryVariables = Exact<{
  entityName: Scalars['String']['input'];
  projectName: Scalars['String']['input'];
}>;


export type ProjectQuery = { __typename?: 'Query', project?: { __typename?: 'Project', id: string, internalId: string } | null };

export type SecretsQueryVariables = Exact<{
  entityName: Scalars['String']['input'];
}>;


export type SecretsQuery = { __typename?: 'Query', entity?: { __typename?: 'Entity', id: string, secrets: Array<{ __typename?: 'Secret', entityId: number, name: string, createdAt: any }> } | null };

export type InsertSecretMutationVariables = Exact<{
  entityName: Scalars['String']['input'];
  secretName: Scalars['String']['input'];
  secretValue: Scalars['String']['input'];
}>;


export type InsertSecretMutation = { __typename?: 'Mutation', insertSecret?: { __typename?: 'InsertSecretPayload', success: boolean } | null };

export type ViewerQueryVariables = Exact<{ [key: string]: never; }>;


export type ViewerQuery = { __typename?: 'Query', viewer?: { __typename?: 'User', id: string, username?: string | null, admin?: boolean | null, teams?: { __typename?: 'EntityConnection', edges: Array<{ __typename?: 'EntityEdge', node?: { __typename?: 'Entity', id: string, name: string } | null }> } | null } | null };

export type Viewer2QueryVariables = Exact<{ [key: string]: never; }>;


export type Viewer2Query = { __typename?: 'Query', viewer?: { __typename?: 'User', id: string, username?: string | null } | null };

export type UpdateUserInfoMutationVariables = Exact<{
  userInfo?: InputMaybe<Scalars['JSONString']['input']>;
}>;


export type UpdateUserInfoMutation = { __typename?: 'Mutation', updateUser?: { __typename?: 'UpdateUserPayload', user?: { __typename?: 'User', id: string } | null } | null };

export type FindRunQueryVariables = Exact<{
  entityName: Scalars['String']['input'];
  projectName: Scalars['String']['input'];
  runName: Scalars['String']['input'];
}>;


export type FindRunQuery = { __typename?: 'Query', project?: { __typename?: 'Project', run?: { __typename?: 'Run', id: string, name: string, displayName?: string | null } | null } | null };

export type UpdateArtifactCollectionMutationVariables = Exact<{
  artifactSequenceID: Scalars['ID']['input'];
  name?: InputMaybe<Scalars['String']['input']>;
  description?: InputMaybe<Scalars['String']['input']>;
}>;


export type UpdateArtifactCollectionMutation = { __typename?: 'Mutation', updateArtifactSequence?: { __typename?: 'UpdateArtifactCollectionPayload', artifactCollection: { __typename?: 'ArtifactPortfolio', id: string, name: string, description?: string | null } | { __typename?: 'ArtifactSequence', id: string, name: string, description?: string | null } } | null };

export type DeleteArtifactSequenceMutationVariables = Exact<{
  artifactSequenceID: Scalars['ID']['input'];
}>;


export type DeleteArtifactSequenceMutation = { __typename?: 'Mutation', deleteArtifactSequence?: { __typename?: 'DeleteArtifactCollectionPayload', artifactCollection: { __typename?: 'ArtifactPortfolio', id: string } | { __typename?: 'ArtifactSequence', id: string } } | null };

export type GetReportQueryVariables = Exact<{
  id: Scalars['ID']['input'];
}>;


export type GetReportQuery = { __typename?: 'Query', view?: { __typename?: 'View', id: string, coverUrl?: string | null, description?: string | null, displayName?: string | null, previewUrl?: string | null, spec?: any | null, children?: { __typename?: 'ViewConnection', edges: Array<{ __typename?: 'ViewEdge', node?: { __typename?: 'View', id: string, createdAt: any, displayName?: string | null, spec?: any | null, user?: { __typename?: 'User', id: string } | null } | null }> } | null } | null };

export type UpsertReportMutationVariables = Exact<{
  id?: InputMaybe<Scalars['ID']['input']>;
  coverUrl?: InputMaybe<Scalars['String']['input']>;
  createdUsing?: InputMaybe<ViewSource>;
  description?: InputMaybe<Scalars['String']['input']>;
  displayName?: InputMaybe<Scalars['String']['input']>;
  entityName?: InputMaybe<Scalars['String']['input']>;
  name?: InputMaybe<Scalars['String']['input']>;
  parentId?: InputMaybe<Scalars['ID']['input']>;
  previewUrl?: InputMaybe<Scalars['String']['input']>;
  projectName?: InputMaybe<Scalars['String']['input']>;
  spec?: InputMaybe<Scalars['String']['input']>;
  type?: InputMaybe<Scalars['String']['input']>;
}>;


export type UpsertReportMutation = { __typename?: 'Mutation', upsertView?: { __typename?: 'UpsertViewPayload', view?: { __typename?: 'View', id: string, displayName?: string | null } | null } | null };

export type DeleteReportDraftMutationVariables = Exact<{
  id?: InputMaybe<Scalars['ID']['input']>;
}>;


export type DeleteReportDraftMutation = { __typename?: 'Mutation', deleteView?: { __typename?: 'DeleteViewPayload', success?: boolean | null } | null };

export type FindUserQueryVariables = Exact<{
  userId: Scalars['ID']['input'];
}>;


export type FindUserQuery = { __typename?: 'Query', user?: { __typename?: 'User', id: string, name: string, email?: string | null, photoUrl?: string | null, deletedAt?: any | null, username?: string | null } | null };


export const EntityDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"query","name":{"kind":"Name","value":"entity"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"entityName"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}},{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"projectName"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}},{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"artifactName"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"entity"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"name"},"value":{"kind":"Variable","name":{"kind":"Name","value":"entityName"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"project"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"name"},"value":{"kind":"Variable","name":{"kind":"Name","value":"projectName"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"artifact"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"name"},"value":{"kind":"Variable","name":{"kind":"Name","value":"artifactName"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"artifactType"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"name"}}]}}]}}]}},{"kind":"Field","name":{"kind":"Name","value":"organization"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"name"}}]}}]}}]}}]} as unknown as DocumentNode<EntityQuery, EntityQueryVariables>;
export const EntityMemberRolesDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"query","name":{"kind":"Name","value":"EntityMemberRoles"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"entityName"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"entity"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"name"},"value":{"kind":"Variable","name":{"kind":"Name","value":"entityName"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"members"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"username"}},{"kind":"Field","name":{"kind":"Name","value":"role"}}]}}]}}]}}]} as unknown as DocumentNode<EntityMemberRolesQuery, EntityMemberRolesQueryVariables>;
export const OrganizationDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"query","name":{"kind":"Name","value":"Organization"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"entityName"}},"type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"entity"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"name"},"value":{"kind":"Variable","name":{"kind":"Name","value":"entityName"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"organization"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"name"}}]}}]}}]}}]} as unknown as DocumentNode<OrganizationQuery, OrganizationQueryVariables>;
export const ProjectDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"query","name":{"kind":"Name","value":"Project"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"entityName"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}},{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"projectName"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"project"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"name"},"value":{"kind":"Variable","name":{"kind":"Name","value":"projectName"}}},{"kind":"Argument","name":{"kind":"Name","value":"entityName"},"value":{"kind":"Variable","name":{"kind":"Name","value":"entityName"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"internalId"}}]}}]}}]} as unknown as DocumentNode<ProjectQuery, ProjectQueryVariables>;
export const SecretsDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"query","name":{"kind":"Name","value":"secrets"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"entityName"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"entity"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"name"},"value":{"kind":"Variable","name":{"kind":"Name","value":"entityName"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"secrets"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"entityId"}},{"kind":"Field","name":{"kind":"Name","value":"name"}},{"kind":"Field","name":{"kind":"Name","value":"createdAt"}}]}}]}}]}}]} as unknown as DocumentNode<SecretsQuery, SecretsQueryVariables>;
export const InsertSecretDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"mutation","name":{"kind":"Name","value":"insertSecret"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"entityName"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}},{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"secretName"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}},{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"secretValue"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"insertSecret"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"input"},"value":{"kind":"ObjectValue","fields":[{"kind":"ObjectField","name":{"kind":"Name","value":"entityName"},"value":{"kind":"Variable","name":{"kind":"Name","value":"entityName"}}},{"kind":"ObjectField","name":{"kind":"Name","value":"secretName"},"value":{"kind":"Variable","name":{"kind":"Name","value":"secretName"}}},{"kind":"ObjectField","name":{"kind":"Name","value":"secretValue"},"value":{"kind":"Variable","name":{"kind":"Name","value":"secretValue"}}}]}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"success"}}]}}]}}]} as unknown as DocumentNode<InsertSecretMutation, InsertSecretMutationVariables>;
export const ViewerDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"query","name":{"kind":"Name","value":"Viewer"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"viewer"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"username"}},{"kind":"Field","name":{"kind":"Name","value":"admin"}},{"kind":"Field","name":{"kind":"Name","value":"teams"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"edges"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"node"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"name"}}]}}]}}]}}]}}]}}]} as unknown as DocumentNode<ViewerQuery, ViewerQueryVariables>;
export const Viewer2Document = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"query","name":{"kind":"Name","value":"Viewer2"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"viewer"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"username"}}]}}]}}]} as unknown as DocumentNode<Viewer2Query, Viewer2QueryVariables>;
export const UpdateUserInfoDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"mutation","name":{"kind":"Name","value":"UpdateUserInfo"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"userInfo"}},"type":{"kind":"NamedType","name":{"kind":"Name","value":"JSONString"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"updateUser"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"input"},"value":{"kind":"ObjectValue","fields":[{"kind":"ObjectField","name":{"kind":"Name","value":"id"},"value":{"kind":"NullValue"}},{"kind":"ObjectField","name":{"kind":"Name","value":"userInfo"},"value":{"kind":"Variable","name":{"kind":"Name","value":"userInfo"}}}]}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"user"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}}]}}]}}]}}]} as unknown as DocumentNode<UpdateUserInfoMutation, UpdateUserInfoMutationVariables>;
export const FindRunDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"query","name":{"kind":"Name","value":"FindRun"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"entityName"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}},{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"projectName"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}},{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"runName"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"project"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"name"},"value":{"kind":"Variable","name":{"kind":"Name","value":"projectName"}}},{"kind":"Argument","name":{"kind":"Name","value":"entityName"},"value":{"kind":"Variable","name":{"kind":"Name","value":"entityName"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"run"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"name"},"value":{"kind":"Variable","name":{"kind":"Name","value":"runName"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"name"}},{"kind":"Field","name":{"kind":"Name","value":"displayName"}}]}}]}}]}}]} as unknown as DocumentNode<FindRunQuery, FindRunQueryVariables>;
export const UpdateArtifactCollectionDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"mutation","name":{"kind":"Name","value":"UpdateArtifactCollection"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"artifactSequenceID"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"ID"}}}},{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"name"}},"type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}},{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"description"}},"type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"updateArtifactSequence"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"input"},"value":{"kind":"ObjectValue","fields":[{"kind":"ObjectField","name":{"kind":"Name","value":"artifactSequenceID"},"value":{"kind":"Variable","name":{"kind":"Name","value":"artifactSequenceID"}}},{"kind":"ObjectField","name":{"kind":"Name","value":"name"},"value":{"kind":"Variable","name":{"kind":"Name","value":"name"}}},{"kind":"ObjectField","name":{"kind":"Name","value":"description"},"value":{"kind":"Variable","name":{"kind":"Name","value":"description"}}}]}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"artifactCollection"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"name"}},{"kind":"Field","name":{"kind":"Name","value":"description"}}]}}]}}]}}]} as unknown as DocumentNode<UpdateArtifactCollectionMutation, UpdateArtifactCollectionMutationVariables>;
export const DeleteArtifactSequenceDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"mutation","name":{"kind":"Name","value":"DeleteArtifactSequence"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"artifactSequenceID"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"ID"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"deleteArtifactSequence"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"input"},"value":{"kind":"ObjectValue","fields":[{"kind":"ObjectField","name":{"kind":"Name","value":"artifactSequenceID"},"value":{"kind":"Variable","name":{"kind":"Name","value":"artifactSequenceID"}}}]}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"artifactCollection"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}}]}}]}}]}}]} as unknown as DocumentNode<DeleteArtifactSequenceMutation, DeleteArtifactSequenceMutationVariables>;
export const GetReportDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"query","name":{"kind":"Name","value":"GetReport"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"id"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"ID"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"view"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"id"},"value":{"kind":"Variable","name":{"kind":"Name","value":"id"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"coverUrl"}},{"kind":"Field","name":{"kind":"Name","value":"description"}},{"kind":"Field","name":{"kind":"Name","value":"displayName"}},{"kind":"Field","name":{"kind":"Name","value":"previewUrl"}},{"kind":"Field","name":{"kind":"Name","value":"spec"}},{"kind":"Field","name":{"kind":"Name","value":"children"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"edges"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"node"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"createdAt"}},{"kind":"Field","name":{"kind":"Name","value":"displayName"}},{"kind":"Field","name":{"kind":"Name","value":"spec"}},{"kind":"Field","name":{"kind":"Name","value":"user"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}}]}}]}}]}}]}}]}}]}}]} as unknown as DocumentNode<GetReportQuery, GetReportQueryVariables>;
export const UpsertReportDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"mutation","name":{"kind":"Name","value":"UpsertReport"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"id"}},"type":{"kind":"NamedType","name":{"kind":"Name","value":"ID"}}},{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"coverUrl"}},"type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}},{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"createdUsing"}},"type":{"kind":"NamedType","name":{"kind":"Name","value":"ViewSource"}}},{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"description"}},"type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}},{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"displayName"}},"type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}},{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"entityName"}},"type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}},{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"name"}},"type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}},{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"parentId"}},"type":{"kind":"NamedType","name":{"kind":"Name","value":"ID"}}},{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"previewUrl"}},"type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}},{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"projectName"}},"type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}},{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"spec"}},"type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}},{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"type"}},"type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"upsertView"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"input"},"value":{"kind":"ObjectValue","fields":[{"kind":"ObjectField","name":{"kind":"Name","value":"id"},"value":{"kind":"Variable","name":{"kind":"Name","value":"id"}}},{"kind":"ObjectField","name":{"kind":"Name","value":"coverUrl"},"value":{"kind":"Variable","name":{"kind":"Name","value":"coverUrl"}}},{"kind":"ObjectField","name":{"kind":"Name","value":"createdUsing"},"value":{"kind":"Variable","name":{"kind":"Name","value":"createdUsing"}}},{"kind":"ObjectField","name":{"kind":"Name","value":"description"},"value":{"kind":"Variable","name":{"kind":"Name","value":"description"}}},{"kind":"ObjectField","name":{"kind":"Name","value":"displayName"},"value":{"kind":"Variable","name":{"kind":"Name","value":"displayName"}}},{"kind":"ObjectField","name":{"kind":"Name","value":"entityName"},"value":{"kind":"Variable","name":{"kind":"Name","value":"entityName"}}},{"kind":"ObjectField","name":{"kind":"Name","value":"name"},"value":{"kind":"Variable","name":{"kind":"Name","value":"name"}}},{"kind":"ObjectField","name":{"kind":"Name","value":"parentId"},"value":{"kind":"Variable","name":{"kind":"Name","value":"parentId"}}},{"kind":"ObjectField","name":{"kind":"Name","value":"previewUrl"},"value":{"kind":"Variable","name":{"kind":"Name","value":"previewUrl"}}},{"kind":"ObjectField","name":{"kind":"Name","value":"projectName"},"value":{"kind":"Variable","name":{"kind":"Name","value":"projectName"}}},{"kind":"ObjectField","name":{"kind":"Name","value":"spec"},"value":{"kind":"Variable","name":{"kind":"Name","value":"spec"}}},{"kind":"ObjectField","name":{"kind":"Name","value":"type"},"value":{"kind":"Variable","name":{"kind":"Name","value":"type"}}}]}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"view"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"displayName"}}]}}]}}]}}]} as unknown as DocumentNode<UpsertReportMutation, UpsertReportMutationVariables>;
export const DeleteReportDraftDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"mutation","name":{"kind":"Name","value":"DeleteReportDraft"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"id"}},"type":{"kind":"NamedType","name":{"kind":"Name","value":"ID"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"deleteView"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"input"},"value":{"kind":"ObjectValue","fields":[{"kind":"ObjectField","name":{"kind":"Name","value":"id"},"value":{"kind":"Variable","name":{"kind":"Name","value":"id"}}}]}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"success"}}]}}]}}]} as unknown as DocumentNode<DeleteReportDraftMutation, DeleteReportDraftMutationVariables>;
export const FindUserDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"query","name":{"kind":"Name","value":"FindUser"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"userId"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"ID"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"user"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"id"},"value":{"kind":"Variable","name":{"kind":"Name","value":"userId"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"name"}},{"kind":"Field","name":{"kind":"Name","value":"email"}},{"kind":"Field","name":{"kind":"Name","value":"photoUrl"}},{"kind":"Field","name":{"kind":"Name","value":"deletedAt"}},{"kind":"Field","name":{"kind":"Name","value":"username"}}]}}]}}]} as unknown as DocumentNode<FindUserQuery, FindUserQueryVariables>;