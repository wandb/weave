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
import {ContentType} from './traceServerClientTypes';

export type OpCategory = (typeof OP_CATEGORIES)[number];
export type KnownBaseObjectClassType =
  (typeof KNOWN_BASE_OBJECT_CLASSES)[number];

export type Loadable<T> = {
  loading: boolean;
  result: T | null;
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

type WeaveObjectVersionKey = {
  scheme: 'weave';
  weaveKind: WeaveKind;
} & CommonObjectVersionKey;

export type ObjectVersionKey =
  | WandbArtifactObjectVersionKey
  | WeaveObjectVersionKey;

export type ObjectVersionSchema = ObjectVersionKey & {
  // TODO: Add more fields & FKs
  versionIndex: number;
  baseObjectClass: string | null;
  createdAtMs: number;
  val: any;
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

export type WFDataModelHooksInterface = {
  useCall: (key: CallKey | null) => Loadable<CallSchema | null>;
  useCalls: (
    entity: string,
    project: string,
    filter: CallFilter,
    limit?: number,
    offset?: number,
    sortBy?: traceServerClientTypes.SortBy[],
    query?: Query,
    expandedRefColumns?: Set<string>,
    opts?: {skip?: boolean; refetchOnDelete?: boolean}
  ) => Loadable<CallSchema[]>;
  useCallsStats: (
    entity: string,
    project: string,
    filter: CallFilter,
    query?: Query,
    opts?: {skip?: boolean; refetchOnDelete?: boolean}
  ) => Loadable<traceServerClientTypes.TraceCallsQueryStatsRes>;
  useCallsDeleteFunc: () => (
    entity: string,
    project: string,
    callIDs: string[]
  ) => Promise<void>;
  useCallUpdateFunc: () => (
    entity: string,
    project: string,
    callID: string,
    newName: string
  ) => Promise<void>;
  useCallsExport: () => (
    entity: string,
    project: string,
    contentType: ContentType,
    filter: CallFilter,
    limit?: number,
    offset?: number,
    sortBy?: traceServerClientTypes.SortBy[],
    query?: Query,
    columns?: string[]
  ) => Promise<Blob>;
  useOpVersion: (key: OpVersionKey | null) => Loadable<OpVersionSchema | null>;
  useOpVersions: (
    entity: string,
    project: string,
    filter: OpVersionFilter,
    limit?: number,
    opts?: {skip?: boolean}
  ) => LoadableWithError<OpVersionSchema[]>;
  useObjectVersion: (
    key: ObjectVersionKey | null
  ) => Loadable<ObjectVersionSchema | null>;
  useRootObjectVersions: (
    entity: string,
    project: string,
    filter: ObjectVersionFilter,
    limit?: number,
    opts?: {skip?: boolean}
  ) => LoadableWithError<ObjectVersionSchema[]>;
  // `useRefsData` is in beta while we integrate Shawn's new Object DB
  useRefsData: (refUris: string[], tableQuery?: TableQuery) => Loadable<any[]>;
  // `useApplyMutationsToRef` is in beta while we integrate Shawn's new Object DB
  useApplyMutationsToRef: () => (
    refUri: string,
    mutations: RefMutation[]
  ) => Promise<string>;
  // Derived are under a subkey because they are not directly from the data model
  // and the logic should be pushed into the core APIs. This is a temporary solution
  // during the transition period.
  useFileContent: (
    entity: string,
    project: string,
    digest: string,
    opts?: {skip?: boolean}
  ) => Loadable<ArrayBuffer>;
  useFeedback: (
    key: FeedbackKey | null,
    sortBy?: traceServerClientTypes.SortBy[]
  ) => LoadableWithError<any[] | null> & Refetchable;
  derived: {
    useChildCallsForCompare: (
      entity: string,
      project: string,
      parentCallIds: string[],
      selectedOpVersionRef: string | null,
      selectedObjectVersionRef: string | null
    ) => Loadable<CallSchema[]>;
    // `useGetRefsType` is in beta while we integrate Shawn's new Object DB
    useGetRefsType: () => (refUris: string[]) => Promise<Types.Type[]>;
    // `useRefsType` is in beta while we integrate Shawn's new Object DB
    useRefsType: (refUris: string[]) => Loadable<Types.Type[]>;
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
