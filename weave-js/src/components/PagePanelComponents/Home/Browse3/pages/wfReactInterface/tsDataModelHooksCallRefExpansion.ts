/**
 * This is intended to be a temporary solution to the problem of expanding
 * references in the client side. This is a stop-gap solution until we can
 * implement the server-side expansion of references. After that is implemented,
 * this hook should be removed.
 */

import * as _ from 'lodash';
import {useEffect, useMemo, useState} from 'react';

import {isWeaveObjectRef, parseRef} from '../../../../../../react';
import {isWeaveRef} from '../../filters/common';
import {refDataCache} from './cache';
import * as traceServerClient from './traceServerClient';
import {useGetTraceServerClientContext} from './traceServerClientContext';
import * as traceServerClientTypes from './traceServerClientTypes';
import {CallSchema, Loadable} from './wfDataModelHooksInterface';

// Prevent excessive recursion (safety guard)
export const MAX_REF_RECURSION_DEPTH = 50;
export const EXPANDED_REF_REF_KEY = '__ref__';
export const EXPANDED_REF_VAL_KEY = '__val__';

export const useClientSideCallRefExpansion = (
  calls: Loadable<CallSchema[]>,
  expandedRefColumns?: Set<string>,
  options?: {
    expansionDepth?: number;
    expandAttr?: boolean;
  }
) => {
  const getTsClient = useGetTraceServerClientContext();
  const [expandedCalls, setExpandedCalls] = useState<
    traceServerClientTypes.TraceCallSchema[]
  >([]);
  const [isExpanding, setIsExpanding] = useState(false);

  useEffect(() => {
    let mounted = true;
    if (calls.loading || calls.result == null) {
      setExpandedCalls([]);
      setIsExpanding(true);
      return;
    }

    if (calls.result.length === 0) {
      setExpandedCalls([]);
      setIsExpanding(false);
      return;
    }

    const callResultStart = calls.result;

    doExpansionIteration(
      callResultStart.map(c => c.traceCall!),
      expandedRefColumns ?? new Set<string>(),
      getTsClient(),
      options?.expansionDepth ?? 0,
      0,
      10,
      options?.expandAttr ?? false
    ).then(innerExpandedCalls => {
      if (calls.result === callResultStart && mounted) {
        setExpandedCalls(innerExpandedCalls);
        setIsExpanding(false);
      }
    });

    return () => {
      mounted = false;
    };
  }, [
    calls,
    calls.loading,
    calls.result,
    expandedRefColumns,
    getTsClient,
    options?.expansionDepth,
    options?.expandAttr,
  ]);

  return useMemo(() => {
    return {
      expandedCalls,
      isExpanding,
    };
  }, [expandedCalls, isExpanding]);
};

/**
 * Helper function to navigate to a specific path in an object
 * @param obj The object to navigate
 * @param path The path as a string with dot notation (e.g. 'a.b.c')
 * @returns An object with the value at the path, the parent object, and the full navigation path
 */
const navigateToPath = (
  obj: any,
  path: string
): {
  value: any;
  parent: any;
  path: string[];
  isValid: boolean;
} => {
  const parts = path.split('.');
  let value: any = obj;
  let parent: any = null;
  const fullPath: string[] = [];
  let isValid = true;

  // Navigate to the target following the path
  for (let i = 0; i < parts.length; i++) {
    const part = parts[i];

    // Handle nested expansion - unwrap __val__ references as we go
    while (
      typeof value === 'object' &&
      value != null &&
      EXPANDED_REF_VAL_KEY in value
    ) {
      value = value[EXPANDED_REF_VAL_KEY];
      fullPath.push(EXPANDED_REF_VAL_KEY);
    }

    if (value == null || typeof value !== 'object') {
      isValid = false;
      break;
    }

    if (i === parts.length - 1) {
      parent = value;
    }

    if (!(part in value)) {
      isValid = false;
      break;
    }

    value = value[part];
    fullPath.push(part);
  }

  // Final unwrapping of the target value
  while (
    typeof value === 'object' &&
    value != null &&
    EXPANDED_REF_VAL_KEY in value
  ) {
    value = value[EXPANDED_REF_VAL_KEY];
    fullPath.push(EXPANDED_REF_VAL_KEY);
  }

  return {value, parent, path: fullPath, isValid};
};

const doExpansionIteration = async (
  traceCalls: traceServerClientTypes.TraceCallSchema[],
  expandedRefColumns: Set<string>,
  client: traceServerClient.TraceServerClient,
  expansionDepth: number = 0,
  iterationCount: number = 0,
  maxIterations: number = 10,
  expandAttr: boolean = false
): Promise<traceServerClientTypes.TraceCallSchema[]> => {
  // Safety check to prevent infinite recursion
  if (iterationCount >= maxIterations) {
    return traceCalls;
  }

  const refsNeeded = new Set<string>();

  // Phase 1: Find all refs in specified columns
  if (expansionDepth > 0) {
    // Recursively find all references in specified columns/paths
    const expandedRefColumnsList = Array.from(expandedRefColumns ?? []);

    traceCalls.forEach(call => {
      expandedRefColumnsList.forEach(column => {
        const {value, isValid} = navigateToPath(call, column);

        // If we found a value at this path, recursively find all refs in it
        if (isValid && value !== undefined) {
          findAllRefsRecursively(value, refsNeeded, new Set(), 0, 50);
        }
      });
    });
  } else {
    // Original implementation: only look at specified columns
    const expandedRefColumnsList = Array.from(expandedRefColumns ?? []);
    traceCalls.forEach(call => {
      expandedRefColumnsList.forEach(col => {
        const {value, isValid} = navigateToPath(call, col);

        if (isValid && isExpandableRef(value)) {
          refsNeeded.add(value);
        }
      });
    });
  }

  // Phase 2: Find all /attr/ refs if expandAttr is enabled
  if (expandAttr) {
    traceCalls.forEach(call => {
      // Find all references in the entire call object
      findAttrRefsRecursively(call, refsNeeded);
    });
  }

  const refsNeededArray = Array.from(refsNeeded);

  if (refsNeededArray.length === 0) {
    return traceCalls;
  }

  try {
    const refsData = await directFetchRefsData(refsNeededArray, client);
    const refsDataMap = new Map<string, any>();
    refsNeededArray.forEach((ref, i) => {
      refsDataMap.set(ref, refsData[i]);
    });

    const expandedTraceCalls = traceCalls.map(call => {
      call = _.cloneDeep(call);

      // Phase 1: Process specified columns/paths
      if (expansionDepth > 0) {
        // Recursively replace all references, but only in specified paths
        const expandedRefColumnsList = Array.from(expandedRefColumns ?? []);

        expandedRefColumnsList.forEach(column => {
          const {value, parent, isValid} = navigateToPath(call, column);

          // If we found the path, recursively replace refs in it
          if (isValid && value !== undefined && parent !== null) {
            // Replace refs in the target value
            replaceAllRefsRecursively(
              value,
              refsDataMap,
              new Set(),
              0,
              expansionDepth
            );
          }
        });
      } else {
        // Original implementation: only replace refs in specified columns
        const expandedRefColumnsList = Array.from(expandedRefColumns ?? []);
        expandedRefColumnsList.forEach(col => {
          const {value, path, isValid} = navigateToPath(call, col);

          if (isValid && isWeaveRef(value) && refsDataMap.has(value)) {
            const refObj = refsDataMap.get(value);
            _.set(call, path, makeRefExpandedPayload(value, refObj));
          }
        });
      }

      // Phase 2: Expand all /attr/ refs if enabled
      if (expandAttr) {
        replaceAttrRefsRecursively(call, refsDataMap);
      }

      return call;
    });

    // Only continue recursion if there are more depths to expand
    const nextDepth = expansionDepth > 0 ? expansionDepth - 1 : 0;

    if (nextDepth > 0 || iterationCount === 0) {
      return doExpansionIteration(
        expandedTraceCalls,
        expandedRefColumns,
        client,
        nextDepth,
        iterationCount + 1,
        maxIterations,
        expandAttr
      );
    } else {
      return expandedTraceCalls;
    }
  } catch (error) {
    // Return the calls as they are if an error occurs
    return traceCalls;
  }
};

/**
 * Recursively finds all expandable references in an object
 * @param obj The object to search
 * @param refsNeeded Set to collect found references
 * @param visited Set of objects already visited to prevent circular reference issues
 * @param depth Current recursion depth
 * @param maxDepth Maximum allowed recursion depth (safety guard)
 */
const findAllRefsRecursively = (
  obj: any,
  refsNeeded: Set<string>,
  visited: Set<any> = new Set(),
  depth: number = 0,
  maxDepth: number = 50
): void => {
  // Prevent excessive recursion
  if (depth > maxDepth) {
    return;
  }

  // Base case: null or primitive value
  if (!obj || typeof obj !== 'object') {
    if (isExpandableRef(obj)) {
      refsNeeded.add(obj);
    }
    return;
  }

  // Prevent circular references
  if (visited.has(obj)) {
    return;
  }
  visited.add(obj);

  // Handle arrays
  if (Array.isArray(obj)) {
    for (const item of obj) {
      findAllRefsRecursively(item, refsNeeded, visited, depth + 1, maxDepth);
    }
    return;
  }

  // Handle objects
  for (const key in obj) {
    if (Object.prototype.hasOwnProperty.call(obj, key)) {
      // If we find a value that's already a reference with a __val__
      if (
        key === EXPANDED_REF_REF_KEY &&
        EXPANDED_REF_VAL_KEY in obj &&
        isExpandableRef(obj[EXPANDED_REF_REF_KEY])
      ) {
        // Make sure the ref is added
        refsNeeded.add(obj[EXPANDED_REF_REF_KEY]);
        // Continue recursively with the __val__ part
        findAllRefsRecursively(
          obj[EXPANDED_REF_VAL_KEY],
          refsNeeded,
          visited,
          depth + 1,
          maxDepth
        );
      } else {
        // Regular property
        const value = obj[key];
        if (isExpandableRef(value)) {
          refsNeeded.add(value);
        } else if (typeof value === 'object' && value !== null) {
          findAllRefsRecursively(
            value,
            refsNeeded,
            visited,
            depth + 1,
            maxDepth
          );
        }
      }
    }
  }
};

/**
 * Recursively replaces all references in an object with their expanded values
 * @param obj The object to process
 * @param refsDataMap Map of reference URIs to their resolved values
 * @param visited Set of objects already visited to prevent circular reference issues
 * @param depth Current recursion depth
 * @param maxDepth Maximum allowed expansion depth (user-specified)
 */
const replaceAllRefsRecursively = (
  obj: any,
  refsDataMap: Map<string, any>,
  visited: Set<any> = new Set(),
  depth: number = 0,
  maxDepth: number = 0
): void => {
  // Stop recursion if we've reached the user-specified max depth
  if (maxDepth > 0 && depth >= maxDepth) {
    return;
  }

  if (depth > MAX_REF_RECURSION_DEPTH) {
    return;
  }

  // Base case: null or primitive value
  if (!obj || typeof obj !== 'object') {
    return;
  }

  // Prevent circular references
  if (visited.has(obj)) {
    return;
  }
  visited.add(obj);

  // Handle arrays
  if (Array.isArray(obj)) {
    for (let i = 0; i < obj.length; i++) {
      const item = obj[i];

      if (isExpandableRef(item) && refsDataMap.has(item)) {
        // Replace the string reference with an expanded reference object
        obj[i] = makeRefExpandedPayload(item, refsDataMap.get(item));

        // Only continue recursion if we haven't reached max depth
        if (maxDepth === 0 || depth < maxDepth) {
          replaceAllRefsRecursively(
            obj[i][EXPANDED_REF_VAL_KEY],
            refsDataMap,
            visited,
            depth + 1,
            maxDepth
          );
        }
      } else if (typeof item === 'object' && item !== null) {
        replaceAllRefsRecursively(
          item,
          refsDataMap,
          visited,
          depth + 1,
          maxDepth
        );
      }
    }
    return;
  }

  // Handle objects
  for (const key in obj) {
    if (Object.prototype.hasOwnProperty.call(obj, key)) {
      const value = obj[key];

      // If this is already an expanded reference, recurse into its __val__ part
      if (key === EXPANDED_REF_REF_KEY && EXPANDED_REF_VAL_KEY in obj) {
        // Only continue recursion if we haven't reached max depth
        if (maxDepth === 0 || depth < maxDepth) {
          replaceAllRefsRecursively(
            obj[EXPANDED_REF_VAL_KEY],
            refsDataMap,
            visited,
            depth + 1,
            maxDepth
          );
        }
      }
      // Handle string references
      else if (isExpandableRef(value) && refsDataMap.has(value)) {
        obj[key] = makeRefExpandedPayload(value, refsDataMap.get(value));

        // Only continue recursion if we haven't reached max depth
        if (maxDepth === 0 || depth < maxDepth) {
          replaceAllRefsRecursively(
            obj[key][EXPANDED_REF_VAL_KEY],
            refsDataMap,
            visited,
            depth + 1,
            maxDepth
          );
        }
      }
      // Recurse into nested objects
      else if (typeof value === 'object' && value !== null) {
        replaceAllRefsRecursively(
          value,
          refsDataMap,
          visited,
          depth + 1,
          maxDepth
        );
      }
    }
  }
};

export type ExpandedRefWithValue<T = any> = {
  [EXPANDED_REF_REF_KEY]: string;
  [EXPANDED_REF_VAL_KEY]: T;
};

export const makeRefExpandedPayload = <T = any>(
  originalRef: string,
  refData: T
): ExpandedRefWithValue<T> => {
  return {
    [EXPANDED_REF_REF_KEY]: originalRef,
    [EXPANDED_REF_VAL_KEY]: refData,
  };
};

export const isExpandedRefWithValue = (
  ref: any
): ref is ExpandedRefWithValue => {
  return (
    typeof ref === 'object' &&
    ref !== null &&
    EXPANDED_REF_REF_KEY in ref &&
    EXPANDED_REF_VAL_KEY in ref
  );
};

export const directFetchRefsData = async (
  refUris: string[],
  client: traceServerClient.TraceServerClient
): Promise<any[]> => {
  const needed: string[] = [];
  const cached: Record<string, any> = {};
  refUris.forEach(sUri => {
    const res = refDataCache.get(sUri);
    if (res == null) {
      needed.push(sUri);
    } else {
      cached[sUri] = res;
    }
  });

  const batchResults = await client.readBatch({
    refs: needed,
  });

  needed.forEach((uri, i) => {
    const val = batchResults.vals[i];
    refDataCache.set(uri, val);
    cached[uri] = val;
  });

  return refUris.map(uri => cached[uri]);
};

export const isTableRef = (ref: any): boolean => {
  if (typeof ref !== 'string') {
    return false;
  }
  if (!isWeaveRef(ref)) {
    return false;
  }
  const parsed = parseRef(ref);
  if (isWeaveObjectRef(parsed)) {
    return parsed.weaveKind === 'table';
  }
  return false;
};

export const isExpandableRef = (ref: any): boolean => {
  if (typeof ref !== 'string') {
    return false;
  }
  if (!isWeaveRef(ref)) {
    return false;
  }
  const parsed = parseRef(ref);
  if (isWeaveObjectRef(parsed)) {
    return (
      parsed.weaveKind === 'object' ||
      parsed.weaveKind === 'op' ||
      (parsed.weaveKind === 'table' &&
        parsed.artifactRefExtra != null &&
        parsed.artifactRefExtra.length > 0)
    );
  }
  return false;
};

/**
 * Recursively finds all references containing '/attr/' in an object
 * @param obj The object to search
 * @param refsNeeded Set to collect found references
 * @param visited Set of objects already visited to prevent circular reference issues
 * @param depth Current recursion depth
 */
const findAttrRefsRecursively = (
  obj: any,
  refsNeeded: Set<string>,
  visited: Set<any> = new Set(),
  depth: number = 0
): void => {
  // Prevent excessive recursion
  if (depth > MAX_REF_RECURSION_DEPTH) {
    return;
  }

  // Base case: null or primitive value
  if (!obj || typeof obj !== 'object') {
    if (isExpandableRef(obj) && obj.includes('/attr/')) {
      refsNeeded.add(obj);
    }
    return;
  }

  // Prevent circular references
  if (visited.has(obj)) {
    return;
  }
  visited.add(obj);

  // Handle arrays
  if (Array.isArray(obj)) {
    for (const item of obj) {
      findAttrRefsRecursively(item, refsNeeded, visited, depth + 1);
    }
    return;
  }

  // Handle objects
  for (const key in obj) {
    if (Object.prototype.hasOwnProperty.call(obj, key)) {
      // If we find a value that's already a reference with a __val__
      if (
        key === EXPANDED_REF_REF_KEY &&
        EXPANDED_REF_VAL_KEY in obj &&
        isExpandableRef(obj[EXPANDED_REF_REF_KEY]) &&
        obj[EXPANDED_REF_REF_KEY].includes('/attr/')
      ) {
        // Make sure the ref is added
        refsNeeded.add(obj[EXPANDED_REF_REF_KEY]);
        // Continue recursively with the __val__ part
        findAttrRefsRecursively(
          obj[EXPANDED_REF_VAL_KEY],
          refsNeeded,
          visited,
          depth + 1
        );
      } else {
        // Regular property
        const value = obj[key];
        if (isExpandableRef(value) && value.includes('/attr/')) {
          refsNeeded.add(value);
        } else if (typeof value === 'object' && value !== null) {
          findAttrRefsRecursively(value, refsNeeded, visited, depth + 1);
        }
      }
    }
  }
};

/**
 * Recursively replaces all attr references in an object with their expanded values
 * @param obj The object to process
 * @param refsDataMap Map of reference URIs to their resolved values
 * @param visited Set of objects already visited to prevent circular reference issues
 * @param depth Current recursion depth
 */
const replaceAttrRefsRecursively = (
  obj: any,
  refsDataMap: Map<string, any>,
  visited: Set<any> = new Set(),
  depth: number = 0
): void => {
  // Prevent excessive recursion
  if (depth > MAX_REF_RECURSION_DEPTH) {
    return;
  }

  // Base case: null or primitive value
  if (!obj || typeof obj !== 'object') {
    return;
  }

  // Prevent circular references
  if (visited.has(obj)) {
    return;
  }
  visited.add(obj);

  // Handle arrays
  if (Array.isArray(obj)) {
    for (let i = 0; i < obj.length; i++) {
      const item = obj[i];

      if (
        isExpandableRef(item) &&
        item.includes('/attr/') &&
        refsDataMap.has(item)
      ) {
        // Replace the string reference with an expanded reference object
        obj[i] = makeRefExpandedPayload(item, refsDataMap.get(item));

        // Continue recursion with the expanded value
        replaceAttrRefsRecursively(
          obj[i][EXPANDED_REF_VAL_KEY],
          refsDataMap,
          visited,
          depth + 1
        );
      } else if (typeof item === 'object' && item !== null) {
        replaceAttrRefsRecursively(item, refsDataMap, visited, depth + 1);
      }
    }
    return;
  }

  // Handle objects
  for (const key in obj) {
    if (Object.prototype.hasOwnProperty.call(obj, key)) {
      const value = obj[key];

      // If this is already an expanded reference, recurse into its __val__ part
      if (key === EXPANDED_REF_REF_KEY && EXPANDED_REF_VAL_KEY in obj) {
        if (obj[EXPANDED_REF_REF_KEY].includes('/attr/')) {
          replaceAttrRefsRecursively(
            obj[EXPANDED_REF_VAL_KEY],
            refsDataMap,
            visited,
            depth + 1
          );
        }
      }
      // Handle string references
      else if (
        isExpandableRef(value) &&
        value.includes('/attr/') &&
        refsDataMap.has(value)
      ) {
        obj[key] = makeRefExpandedPayload(value, refsDataMap.get(value));

        // Continue recursion with the expanded value
        replaceAttrRefsRecursively(
          obj[key][EXPANDED_REF_VAL_KEY],
          refsDataMap,
          visited,
          depth + 1
        );
      }
      // Recurse into nested objects
      else if (typeof value === 'object' && value !== null) {
        replaceAttrRefsRecursively(value, refsDataMap, visited, depth + 1);
      }
    }
  }
};
