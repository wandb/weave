/**
 * In-memory LRU cache for Calls/Ops/ObjectVersions. This is a fairly simple
 * cache that lives just for the duration of the process page view. Our usage
 * pattern is very often a some query (returning many results), followed by a
 * read of a specific result. Using this caching mechanic, we can avoid
 * re-fetching the same data multiple times in a single page view.
 */

import LRUCache from 'lru-cache';

import {
  CallKey,
  CallSchema,
  ObjectVersionKey,
  ObjectVersionSchema,
  OpVersionKey,
  OpVersionSchema,
} from './wfDataModelHooksInterface';

const CACHE_SIZE = 5 * 2 ** 20; // 5MB

const callCache = new LRUCache<string, CallSchema>({
  max: CACHE_SIZE,
  updateAgeOnGet: true,
});

const callCacheKeyFn = (key: CallKey) => {
  return `call:${key.entity}/${key.project}/${key.callId}`;
};

export const getCallFromCache = (key: CallKey) => {
  return callCache.get(callCacheKeyFn(key));
};

export const setCallInCache = (key: CallKey, value: CallSchema) => {
  callCache.set(callCacheKeyFn(key), value);
};

const opVersionCache = new LRUCache<string, OpVersionSchema>({
  max: CACHE_SIZE,
  updateAgeOnGet: true,
});

const opVersionCacheKeyFn = (key: OpVersionKey) => {
  return `op:${key.entity}/${key.project}/${key.opId}/${key.versionHash}`;
};

export const getOpVersionFromCache = (key: OpVersionKey) => {
  return opVersionCache.get(opVersionCacheKeyFn(key));
};

export const setOpVersionInCache = (
  key: OpVersionKey,
  value: OpVersionSchema
) => {
  opVersionCache.set(opVersionCacheKeyFn(key), value);
};

const objectVersionCache = new LRUCache<string, ObjectVersionSchema>({
  max: CACHE_SIZE,
  updateAgeOnGet: true,
});

const objectVersionCacheKeyFn = (key: ObjectVersionKey) => {
  return `obj:${key.entity}/${key.project}/${key.objectId}/${key.versionHash}/${key.path}/${key.refExtra}`;
};

export const getObjectVersionFromCache = (key: ObjectVersionKey) => {
  return objectVersionCache.get(objectVersionCacheKeyFn(key));
};

export const setObjectVersionInCache = (
  key: ObjectVersionKey,
  value: ObjectVersionSchema
) => {
  objectVersionCache.set(objectVersionCacheKeyFn(key), value);
};
