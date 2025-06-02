/**
 * This file define the primary _application_ interface for the weaveflow data model. Importantly, it is agnostic
 * to backend storage implementation and should provide an implementation-agnostic interface for the rest of the
 * application to use. Be very thoughtful when modifying this file. The primary exposed interfaces/types are:
 * - `WFDataModelHooks` -> this is the primary hook interface for reading data from the weaveflow data model.
 * - Schemas: These are the "nouns" of the application: Call, Op, and Object:
 *    - `CallSchema`
 *    - `OpVersionSchema`
 *    - `ObjectVersionSchema`
 */

import * as Types from '../../../../../../core/model/types';
import {WeaveKind} from '../../../../../../react';
import {KNOWN_BASE_OBJECT_CLASSES, OP_CATEGORIES} from './constants';
import {Query} from './traceServerClientInterface/query'; // TODO: This import is not ideal, should delete this whole interface
import * as traceServerClientTypes from './traceServerClientTypes'; // TODO: This import is not ideal, should delete this whole interface

export type OpCategory = (typeof OP_CATEGORIES)[number];
export type KnownBaseObjectClassType =
  (typeof KNOWN_BASE_OBJECT_CLASSES)[number];

export type Loadable<T> = {
  loading: boolean;
  result: T | null;
  error?: Error | null;
};

export type LoadableWithError<T> = {
  loading: boolean;
  result: T | null;
  error: Error | null;
};

export type CallKey = {
  entity: string;
  project: string;
  callId: string;
};

export type CacheableCallKey = CallKey & Record<string, unknown>;

export type CallSchema = CallKey & {
  spanName: string;
  displayName: string | null;
  opVersionRef: string | null;
  traceId: string;
  parentId: string | null;
  // See note above `RawSpanFromStreamTableEra` regarding the `rawSpan` field.
  // We should wean off of this and move the needed properties to `CallSchema`.
  rawSpan: RawSpanFromStreamTableEra;
  rawFeedback?: any;
  userId: string | null;
  runId: string | null;
  traceCall?: traceServerClientTypes.TraceCallSchema; // this will eventually be the entire call schema
  totalStorageSizeBytes?: number | null;
};

export type CallFilter = {
  // Filters are ANDed across the fields and ORed within the fields
  // Commented out means not yet implemented
  opVersionRefs?: string[];
  inputObjectVersionRefs?: string[];
  outputObjectVersionRefs?: string[];
  parentIds?: string[];
  traceId?: string;
  callIds?: string[];
  traceRootsOnly?: boolean;
  runIds?: string[];
  userIds?: string[];
};

export type OpVersionKey = {
  entity: string;
  project: string;
  opId: string;
  versionHash: string;
};

export type OpVersionSchema = OpVersionKey & {
  // TODO: Add more fields & FKs
  versionIndex: number;
  createdAtMs: number;
  userId?: string;
};

export type OpVersionFilter = {
  // Filters are ANDed across the fields and ORed within the fields
  opIds?: string[];
  latestOnly?: boolean;
};

type CommonObjectVersionKey = {
  entity: string;
  project: string;
  objectId: string;
  versionHash: string;
  path: string;
  refExtra?: string;
};

type WandbArtifactObjectVersionKey = {
  scheme: 'wandb-artifact';
} & CommonObjectVersionKey;

export type WeaveObjectVersionKey = {
  scheme: 'weave';
  weaveKind: WeaveKind;
} & CommonObjectVersionKey;

export type ObjectVersionKey =
  | WandbArtifactObjectVersionKey
  | WeaveObjectVersionKey;

export type ObjectVersionSchema<T extends any = any> = ObjectVersionKey & {
  // TODO: Add more fields & FKs
  versionIndex: number;
  baseObjectClass: string | null;
  createdAtMs: number;
  val: T;
  userId?: string;
  sizeBytes?: number;
};

export type ObjectVersionFilter = {
  // Filters are ANDed across the fields and ORed within the fields
  baseObjectClasses?: KnownBaseObjectClassType[];
  objectIds?: string[];
  latestOnly?: boolean;
};

export type TableQuery = {
  columns?: string[];
  limit?: number;
};

interface PathElObject {
  type: 'getattr';
  key: string;
}

interface PathElTypedDict {
  type: 'pick';
  key: string;
}

type PathEl = PathElObject | PathElTypedDict;

type SetRefMutation = {
  type: 'set';
  path: PathEl[];
  newValue: any;
};

type AppendRefMutation = {
  type: 'append';
  newValue: {[key: string]: any};
};

export type RefMutation = SetRefMutation | AppendRefMutation;

export type FeedbackKey = {
  entity: string;
  project: string;
  weaveRef: string;
};

export type Refetchable = {
  refetch: () => void;
};

export interface UseCallParams {
  key: CallKey | null;
  includeCosts?: boolean;
  refetchOnRename?: boolean;
  includeTotalStorageSize?: boolean;
}

export interface UseCallsParams {
  entity: string;
  project: string;
  filter: CallFilter;
  limit?: number;
  offset?: number;
  sortBy?: traceServerClientTypes.SortBy[];
  query?: Query;
  columns?: string[];
  expandedRefColumns?: Set<string>;
  skip?: boolean;
  refetchOnDelete?: boolean;
  includeCosts?: boolean;
  includeFeedback?: boolean;
  includeTotalStorageSize?: boolean;
}

export interface UseCallsStatsParams {
  entity: string;
  project: string;
  filter?: CallFilter;
  query?: Query;
  limit?: number;
  skip?: boolean;
  refetchOnDelete?: boolean;
  includeTotalStorageSize?: boolean;
}

export interface UseProjectHasCallsParams {
  entity: string;
  project: string;
  skip?: boolean;
}

export interface UseCallsDeleteParams {
  entity: string;
  project: string;
  callIDs: string[];
}

export interface UseCallUpdateParams {
  entity: string;
  project: string;
  callID: string;
  newName: string;
}

export interface UseCallsExportParams {
  entity: string;
  project: string;
  contentType: traceServerClientTypes.ContentType;
  filter: CallFilter;
  limit?: number;
  offset?: number;
  sortBy?: traceServerClientTypes.SortBy[];
  query?: Query;
  columns?: string[];
  expandedRefCols?: string[];
  includeFeedback?: boolean;
  includeCosts?: boolean;
}

export interface UseObjCreateParams {
  projectId: string;
  objectId: string;
  val: any;
  baseObjectClass?: string;
}

export interface UseOpVersionParams {
  key: OpVersionKey | null;
  metadataOnly?: boolean;
}

export interface UseOpVersionsParams {
  entity: string;
  project: string;
  filter: OpVersionFilter;
  limit?: number;
  metadataOnly?: boolean;
  orderBy?: traceServerClientTypes.SortBy[];
  skip?: boolean;
}

export interface UseObjectVersionParams {
  key: ObjectVersionKey | null;
  metadataOnly?: boolean;
}

export interface UseTableQueryParams {
  projectId: string;
  digest: string;
  filter: traceServerClientTypes.TraceTableQueryReq['filter'];
  limit?: traceServerClientTypes.TraceTableQueryReq['limit'];
  offset?: traceServerClientTypes.TraceTableQueryReq['offset'];
  sortBy?: traceServerClientTypes.TraceTableQueryReq['sort_by'];
  skip?: boolean;
}

export interface UseTableRowsQueryParams {
  entity: string;
  project: string;
  digest: string;
  filter?: traceServerClientTypes.TraceTableQueryReq['filter'];
  limit?: traceServerClientTypes.TraceTableQueryReq['limit'];
  offset?: traceServerClientTypes.TraceTableQueryReq['offset'];
  sortBy?: traceServerClientTypes.TraceTableQueryReq['sort_by'];
  skip?: boolean;
}

export interface UseTableQueryStatsParams {
  entity: string;
  project: string;
  digests: string[];
  skip?: boolean;
  includeStorageSize?: boolean;
}

export interface UseRootObjectVersionsParams {
  entity: string;
  project: string;
  filter?: ObjectVersionFilter;
  limit?: number;
  metadataOnly?: boolean;
  skip?: boolean;
  noAutoRefresh?: boolean;
  includeStorageSize?: boolean;
}

export interface ObjectDeleteParams {
  entity: string;
  project: string;
  objectId: string;
  digests?: string[];
}

export interface ObjectDeleteAllVersionsParams {
  key: ObjectVersionKey;
}

export interface OpVersionDeleteParams {
  entity: string;
  project: string;
  opId: string;
  digests?: string[];
}

export interface OpVersionDeleteAllVersionsParams {
  key: OpVersionKey;
}

export interface UseRefsDataParams {
  refUris: string[];
  tableQuery?: TableQuery;
}

export interface UseRefsReadBatchParams {
  refUris: string[];
  skip?: boolean;
}

export interface UseApplyMutationsToRefParams {
  refUri: string;
  mutations: RefMutation[];
}

export interface UseFileContentParams {
  entity: string;
  project: string;
  digest: string;
  skip?: boolean;
}

export interface UseFeedbackParams {
  key: FeedbackKey | null;
  sortBy?: traceServerClientTypes.SortBy[];
}

export interface UseTableUpdateParams {
  projectId: string;
  baseDigest: string;
  updates: traceServerClientTypes.TableUpdateSpec[];
}

export interface UseChildCallsForCompareParams {
  entity: string;
  project: string;
  parentCallIds: string[];
  selectedOpVersionRef: string | null;
  selectedObjectVersionRef: string | null;
}

export interface UseGetRefsTypeParams {
  refUris: string[];
}

export type WFDataModelHooksInterface = {
  useCall: (params: UseCallParams) => Loadable<CallSchema | null>;
  useCalls: (params: UseCallsParams) => Loadable<CallSchema[]> & Refetchable;
  useCallsStats: (
    params: UseCallsStatsParams
  ) => Loadable<traceServerClientTypes.TraceCallsQueryStatsRes> & Refetchable;
  useProjectHasCalls: (params: UseProjectHasCallsParams) => Loadable<boolean>;
  useCallsDeleteFunc: () => (params: UseCallsDeleteParams) => Promise<void>;
  useCallUpdateFunc: () => (params: UseCallUpdateParams) => Promise<void>;
  useCallsExport: () => (params: UseCallsExportParams) => Promise<Blob>;
  useObjCreate: () => (params: UseObjCreateParams) => Promise<string>;
  useOpVersion: (
    params: UseOpVersionParams
  ) => LoadableWithError<OpVersionSchema | null>;
  useOpVersions: (
    params: UseOpVersionsParams
  ) => LoadableWithError<OpVersionSchema[]>;
  useObjectVersion: (
    params: UseObjectVersionParams
  ) => LoadableWithError<ObjectVersionSchema | null>;
  useTableRowsQuery: (
    params: UseTableRowsQueryParams
  ) => Loadable<traceServerClientTypes.TraceTableQueryRes>;
  useTableQueryStats: (
    params: UseTableQueryStatsParams
  ) => Loadable<traceServerClientTypes.TraceTableQueryStatsBatchRes>;
  useRootObjectVersions: (
    params: UseRootObjectVersionsParams
  ) => LoadableWithError<ObjectVersionSchema[]>;
  useObjectDeleteFunc: () => {
    objectVersionsDelete: (
      params: ObjectDeleteParams
    ) => Promise<traceServerClientTypes.TraceObjDeleteRes>;
    objectDeleteAllVersions: (
      params: ObjectDeleteAllVersionsParams
    ) => Promise<traceServerClientTypes.TraceObjDeleteRes>;
    opVersionsDelete: (
      params: OpVersionDeleteParams
    ) => Promise<traceServerClientTypes.TraceObjDeleteRes>;
    opDeleteAllVersions: (
      params: OpVersionDeleteAllVersionsParams
    ) => Promise<traceServerClientTypes.TraceObjDeleteRes>;
  };
  useRefsData: (params: UseRefsDataParams) => Loadable<any[]>;
  useApplyMutationsToRef: () => (
    params: UseApplyMutationsToRefParams
  ) => Promise<string>;
  useFileContent: (params: UseFileContentParams) => Loadable<ArrayBuffer>;
  useFeedback: (
    params: UseFeedbackParams
  ) => LoadableWithError<traceServerClientTypes.Feedback[] | null> &
    Refetchable;
  useTableUpdate: () => (
    params: UseTableUpdateParams
  ) => Promise<traceServerClientTypes.TableUpdateRes>;
  useTableCreate: () => (
    params: traceServerClientTypes.TableCreateReq
  ) => Promise<traceServerClientTypes.TableCreateRes>;
  derived: {
    useChildCallsForCompare: (
      params: UseChildCallsForCompareParams
    ) => Loadable<CallSchema[]>;
    useGetRefsType: () => (
      params: UseGetRefsTypeParams
    ) => Promise<Types.Type[]>;
    useRefsType: (params: UseGetRefsTypeParams) => Loadable<Types.Type[]>;
    useCodeForOpRef: (opVersionRef: string) => Loadable<string>;
  };
};

/**
 * `RawSpanFromStreamTableEra` and `RawSpanFromStreamTableEraWithFeedback` are
 * sort of relics from the past. The fact that they are exported is a smell of
 * some leaky abstraction. They were originally defined in callTree.ts and
 * mapped exactly the the StreamTable schema for calls - which were then
 * referred to as spans. Now, much of the UI was built against these types.
 * However, in an ideal world, we move the needed properties to `CallSchema` (a
 * common interface regardless of storage). However, in the interim, we store
 * the "rawSpan" in `CallSchema` to give more legacy react code the ability to
 * reach in and get the needed properties. However, with the new Clickhouse
 * backend, we actually have to do the work of converting the raw data format to
 * this raw span! A good refactor would be to remove the `rawSpan` field from
 * `CallSchema` and go fix all the type errors in the app by moving parts of the
 * needed properties to `CallSchema`, and updating the converters from the raw
 * data format to the `CallSchema` format. This would allow us to remove the
 * `RawSpanFromStreamTableEra` and `RawSpanFromStreamTableEraWithFeedback`.
 * (hence the more specific name `RawSpanFromStreamTableEra`).
 */
export interface RawSpanFromStreamTableEra {
  name: string;
  inputs: {_keys?: string[]; [key: string]: any};
  output: undefined | {_keys?: string[]; [key: string]: any};
  status_code: string; // TODO enum
  exception?: string;
  attributes: {[key: string]: any};
  summary: {latency_s: number; [key: string]: any};
  span_id: string;
  trace_id: string;
  parent_id?: string;
  timestamp: number;
  start_time_ms: number;
  end_time_ms?: number;
}

export type RawSpanFromStreamTableEraWithFeedback =
  RawSpanFromStreamTableEra & {feedback?: any};
