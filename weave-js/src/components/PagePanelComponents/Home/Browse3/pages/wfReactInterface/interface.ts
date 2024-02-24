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

import {OBJECT_CATEGORIES, OP_CATEGORIES} from './constants';

export type OpCategory = (typeof OP_CATEGORIES)[number];
export type ObjectCategory = (typeof OBJECT_CATEGORIES)[number];

export type Loadable<T> = {
  loading: boolean;
  result: T | null;
};

export type CallKey = {
  entity: string;
  project: string;
  callId: string;
};
export type CallSchema = CallKey & {
  spanName: string;
  opVersionRef: string | null;
  traceId: string;
  parentId: string | null;
  // See note above `RawSpanFromStreamTableEra` regarding the `rawSpan` field.
  // We should wean off of this and move the needed properties to `CallSchema`.
  rawSpan: RawSpanFromStreamTableEra; 
  rawFeedback?: any;
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
  opCategory?: OpCategory[];
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
  category: OpCategory | null;
};

export type OpVersionFilter = {
  // Filters are ANDed across the fields and ORed within the fields
  category?: OpCategory[];
  opIds?: string[];
  latestOnly?: boolean;
};

export type ObjectVersionKey = {
  entity: string;
  project: string;
  objectId: string;
  versionHash: string;
  path: string;
  refExtra?: string;
};

export type ObjectVersionSchema = ObjectVersionKey & {
  // TODO: Add more fields & FKs
  versionIndex: number;
  typeName: string;
  category: ObjectCategory | null;
  createdAtMs: number;
};

export type ObjectVersionFilter = {
  // Filters are ANDed across the fields and ORed within the fields
  category?: ObjectCategory[];
  objectIds?: string[];
  latestOnly?: boolean;
};

export type WFDataModelHooks = {
  useCall: (key: CallKey | null) => Loadable<CallSchema | null>;
  useCalls: (
    entity: string,
    project: string,
    filter: CallFilter,
    limit?: number,
    opts?: {skip?: boolean}
  ) => Loadable<CallSchema[]>;
  useOpVersion: (key: OpVersionKey | null) => Loadable<OpVersionSchema | null>;
  useOpVersions: (
    entity: string,
    project: string,
    filter: OpVersionFilter,
    limit?: number,
    opts?: {skip?: boolean}
  ) => Loadable<OpVersionSchema[]>;
  useObjectVersion: (
    key: ObjectVersionKey | null
  ) => Loadable<ObjectVersionSchema | null>;
  useRootObjectVersions: (
    entity: string,
    project: string,
    filter: ObjectVersionFilter,
    limit?: number,
    opts?: {skip?: boolean}
  ) => Loadable<ObjectVersionSchema[]>;
  // Derived are under a subkey because they are not directly from the data model
  // and the logic should be pushed into the core APIs. This is a temporary solution
  // during the transition period.
  derived: {
    useChildCallsForCompare: (
      entity: string,
      project: string,
      parentCallIds: string[],
      selectedOpVersionRef: string | null,
      selectedObjectVersionRef: string | null
    ) => Loadable<CallSchema[]>;
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
