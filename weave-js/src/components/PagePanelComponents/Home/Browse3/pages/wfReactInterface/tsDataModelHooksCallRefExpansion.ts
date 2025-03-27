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

export const EXPANDED_REF_REF_KEY = '__ref__';
export const EXPANDED_REF_VAL_KEY = '__val__';
export const useClientSideCallRefExpansion = (
  calls: Loadable<CallSchema[]>,
  expandedRefColumns?: Set<string>,
  options?: {
    recursiveUnwrap?: boolean;
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
      options?.recursiveUnwrap ?? false
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
    options?.recursiveUnwrap,
  ]);

  return useMemo(() => {
    return {
      expandedCalls,
      isExpanding,
    };
  }, [expandedCalls, isExpanding]);
};

const doExpansionIteration = async (
  traceCalls: traceServerClientTypes.TraceCallSchema[],
  expandedRefColumns: Set<string>,
  client: traceServerClient.TraceServerClient,
  recursiveUnwrap: boolean = false,
  iterationCount: number = 0,
  maxIterations: number = 10
): Promise<traceServerClientTypes.TraceCallSchema[]> => {
  // Safety check to prevent infinite recursion
  if (iterationCount >= maxIterations) {
    return traceCalls;
  }

  const refsNeeded = new Set<string>();

  if (recursiveUnwrap) {
    // Recursively find all references in specified columns/paths
    const expandedRefColumnsList = Array.from(expandedRefColumns ?? []);

    traceCalls.forEach(call => {
      expandedRefColumnsList.forEach(column => {
        // Get the value at the specified column path
        const parts = column.split('.');
        let value: any = call;

        // Navigate to the column
        for (const part of parts) {
          if (value == null || typeof value !== 'object') {
            value = undefined;
            break;
          }
          // Use bracket notation with any type to bypass TypeScript's index signature check
          value = value[part as keyof typeof value];
        }

        // If we found a value at this path, recursively find all refs in it
        if (value !== undefined) {
          findAllRefsRecursively(value, refsNeeded);
        }
      });
    });
  } else {
    // Original implementation: only look at specified columns
    const expandedRefColumnsList = Array.from(expandedRefColumns ?? []);
    traceCalls.forEach(call => {
      expandedRefColumnsList.forEach(col => {
        const colParts = col.split('.');
        let value: any = call;
        for (const part of colParts) {
          while (
            typeof value === 'object' &&
            value != null &&
            EXPANDED_REF_VAL_KEY in value
          ) {
            value = value[EXPANDED_REF_VAL_KEY];
          }
          if (value == null) {
            break;
          }
          if (typeof value !== 'object' || !(part in value)) {
            value = null;
            break;
          }
          value = value[part];
        }
        while (
          typeof value === 'object' &&
          value != null &&
          EXPANDED_REF_VAL_KEY in value
        ) {
          value = value[EXPANDED_REF_VAL_KEY];
        }
        if (isExpandableRef(value)) {
          refsNeeded.add(value);
        }
      });
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

      if (recursiveUnwrap) {
        // Recursively replace all references, but only in specified paths
        const expandedRefColumnsList = Array.from(expandedRefColumns ?? []);

        expandedRefColumnsList.forEach(column => {
          // Navigate to the column path
          const parts = column.split('.');
          let target: any = call;
          let parent: any = null;

          // Find the parent object that contains the target field
          for (let i = 0; i < parts.length; i++) {
            const part = parts[i];
            if (target == null || typeof target !== 'object') {
              target = undefined;
              break;
            }

            if (i === parts.length - 1) {
              parent = target;
            }

            target = target[part as keyof typeof target];
          }

          // If we found the path, recursively replace refs in it
          if (target !== undefined && parent !== null) {
            // Replace refs in the target value
            replaceAllRefsRecursively(target, refsDataMap);
          }
        });
      } else {
        // Original implementation: only replace refs in specified columns
        const expandedRefColumnsList = Array.from(expandedRefColumns ?? []);
        expandedRefColumnsList.forEach(col => {
          const colParts = col.split('.');
          let value: any = call;
          const path: string[] = [];
          for (const part of colParts) {
            while (
              typeof value === 'object' &&
              value != null &&
              EXPANDED_REF_VAL_KEY in value
            ) {
              value = value[EXPANDED_REF_VAL_KEY];
              path.push(EXPANDED_REF_VAL_KEY);
            }
            if (value == null) {
              break;
            }
            if (typeof value !== 'object' || !(part in value)) {
              value = null;
              break;
            }
            value = value[part];
            path.push(part);
          }
          while (
            typeof value === 'object' &&
            value != null &&
            EXPANDED_REF_VAL_KEY in value
          ) {
            value = value[EXPANDED_REF_VAL_KEY];
            path.push(EXPANDED_REF_VAL_KEY);
          }
          if (isWeaveRef(value) && refsDataMap.has(value)) {
            const refObj = refsDataMap.get(value);
            _.set(call, path, makeRefExpandedPayload(value, refObj));
          }
        });
      }

      return call;
    });

    return doExpansionIteration(
      expandedTraceCalls,
      expandedRefColumns,
      client,
      recursiveUnwrap,
      iterationCount + 1,
      maxIterations
    );
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
 * @param maxDepth Maximum recursion depth to prevent stack overflow
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
 * @param maxDepth Maximum recursion depth to prevent stack overflow
 */
const replaceAllRefsRecursively = (
  obj: any,
  refsDataMap: Map<string, any>,
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
        replaceAllRefsRecursively(
          obj[EXPANDED_REF_VAL_KEY],
          refsDataMap,
          visited,
          depth + 1,
          maxDepth
        );
      }
      // Handle string references
      else if (isExpandableRef(value) && refsDataMap.has(value)) {
        obj[key] = makeRefExpandedPayload(value, refsDataMap.get(value));
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
