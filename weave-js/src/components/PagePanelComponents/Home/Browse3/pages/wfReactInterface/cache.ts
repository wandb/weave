/**
 * In-memory LRU cache for Calls/Ops/ObjectVersions. This is a fairly simple
 * cache that lives just for the duration of the process page view. Our usage
 * pattern is very often a some query (returning many results), followed by a
 * read of a specific result. Using this caching mechanic, we can avoid
 * re-fetching the same data multiple times in a single page view.
 */

import LRUCache from 'lru-cache';

import {Node} from '../../../../../../core';
import {
  CallKey,
  CallSchema,
  ObjectVersionKey,
  ObjectVersionSchema,
  OpVersionKey,
  OpVersionSchema,
} from './wfDataModelHooksInterface';

const CACHE_SIZE = 5 * 2 ** 20; // 5MB

const makeSpecificCache = <K, V>(
  keyFn: (externalKey: K) => string,
  lruOptions: LRUCache.Options<string, V> = {
    max: CACHE_SIZE,
    updateAgeOnGet: true,
  }
) => {
  const cache = new LRUCache<string, V>(lruOptions);
  return {
    get: (key: K) => {
      return cache.get(keyFn(key));
    },
    set: (key: K, value: V) => {
      cache.set(keyFn(key), value);
    },
    del: (key: K) => {
      cache.del(keyFn(key));
    },
  };
};

export const callCache = makeSpecificCache<CallKey, CallSchema>(key => {
  return `call:${key.entity}/${key.project}/${key.callId}`;
});

export const opVersionCache = makeSpecificCache<OpVersionKey, OpVersionSchema>(
  key => {
    return `op:${key.entity}/${key.project}/${key.opId}/${key.versionHash}`;
  }
);

export const objectVersionCache = makeSpecificCache<
  ObjectVersionKey,
  ObjectVersionSchema
>(key => {
  return `obj:${key.entity}/${key.project}/${key.objectId}/${key.versionHash}/${key.path}/${key.refExtra}`;
});

export const refDataCache = makeSpecificCache<string, any>(key => {
  return key;
});

export const refTypedNodeCache = makeSpecificCache<string, Node>(key => {
  return key;
});
