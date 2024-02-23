import {OBJECT_CATEGORIES, OP_CATEGORIES} from './constants';

export type OpCategory = (typeof OP_CATEGORIES)[number];
export type ObjectCategory = (typeof OBJECT_CATEGORIES)[number];

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
  // TODO: Add more fields & FKs
  spanName: string;
  opVersionRef: string | null;
  traceId: string;
  parentId: string | null;
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
    ) => Loadable<
      Array<{
        parent: RawSpanFromStreamTableEra;
        child: RawSpanFromStreamTableEra;
      }>
    >;
  };
};
