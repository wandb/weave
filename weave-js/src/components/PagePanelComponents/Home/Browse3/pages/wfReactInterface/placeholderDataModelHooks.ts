/**
 * This file defines `placeholderWFDataModelHooks` which conforms to the the
 * `WFDataModelHooksInterface`, providing a default data model implementation.
 * It just returns empty data but can be used in the rare case where the UI
 * does not have a connection to a data provider.
 */

import {
  CallFilter,
  CallKey,
  CallSchema,
  Loadable,
  ObjectVersionFilter,
  ObjectVersionKey,
  ObjectVersionSchema,
  OpVersionFilter,
  OpVersionKey,
  OpVersionSchema,
  WFDataModelHooksInterface,
} from './wfDataModelHooksInterface';

const useCall = (key: CallKey | null): Loadable<CallSchema | null> => {
  return {
    loading: false,
    result: null,
  };
};

const useCalls = (
  entity: string,
  project: string,
  filter: CallFilter,
  limit?: number,
  opts?: {skip?: boolean}
): Loadable<CallSchema[]> => {
  return {
    loading: false,
    result: [],
  };
};

const useOpVersion = (
  // Null value skips
  key: OpVersionKey | null
): Loadable<OpVersionSchema | null> => {
  return {
    loading: false,
    result: null,
  };
};

const useOpVersions = (
  entity: string,
  project: string,
  filter: OpVersionFilter,
  limit?: number,
  opts?: {skip?: boolean}
): Loadable<OpVersionSchema[]> => {
  return {
    loading: false,
    result: [],
  };
};

const useObjectVersion = (
  // Null value skips
  key: ObjectVersionKey | null
): Loadable<ObjectVersionSchema | null> => {
  return {
    loading: false,
    result: null,
  };
};

const useRootObjectVersions = (
  entity: string,
  project: string,
  filter: ObjectVersionFilter,
  limit?: number,
  opts?: {skip?: boolean}
): Loadable<ObjectVersionSchema[]> => {
  return {
    loading: false,
    result: [],
  };
};

const useChildCallsForCompare = (
  entity: string,
  project: string,
  parentCallIds: string[] | undefined,
  selectedOpVersionRef: string | null,
  selectedObjectVersionRef: string | null
): {
  loading: boolean;
  result: CallSchema[];
} => {
  return {
    loading: false,
    result: [],
  };
};

export const placeholderWFDataModelHooks: WFDataModelHooksInterface = {
  useCall,
  useCalls,
  useOpVersion,
  useOpVersions,
  useObjectVersion,
  useRootObjectVersions,
  derived: {useChildCallsForCompare},
};
