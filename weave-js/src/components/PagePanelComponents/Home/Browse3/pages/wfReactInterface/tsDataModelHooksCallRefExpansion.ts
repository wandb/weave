/**
 * This is intended to be a temporary solution to the problem of expanding
 * references in the client side. This is a stop-gap solution until we can
 * implement the server-side expansion of references. After that is implemented,
 * this hook should be removed.
 */

import * as _ from 'lodash';
import {useEffect, useMemo, useState} from 'react';

import {isWeaveObjectRef, parseRef} from '../../../../../../react';
import {isRef} from '../common/util';
import {refDataCache} from './cache';
import * as traceServerClient from './traceServerClient';
import {useGetTraceServerClientContext} from './traceServerClientContext';
import * as traceServerClientTypes from './traceServerClientTypes';
import {CallSchema, Loadable} from './wfDataModelHooksInterface';

export const EXPANDED_REF_REF_KEY = '__ref__';
export const EXPANDED_REF_VAL_KEY = '__val__';
export const useClientSideCallRefExpansion = (
  calls: Loadable<CallSchema[]>,
  expandedRefColumns?: Set<string>
) => {
  const getTsClient = useGetTraceServerClientContext();
  const [expandedCalls, setExpandedCalls] = useState<
    traceServerClientTypes.TraceCallSchema[]
  >([]);
  const [isExpanding, setIsExpanding] = useState(false);

  useEffect(() => {
    if (calls.loading || calls.result == null) {
      setExpandedCalls([]);
      setIsExpanding(true);
      return;
    }

    const doExpansionIteration = async (
      traceCalls: traceServerClientTypes.TraceCallSchema[]
    ) => {
      const refsNeeded = new Set<string>();
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

      const refsNeededArray = Array.from(refsNeeded);

      if (refsNeededArray.length === 0) {
        setExpandedCalls(traceCalls);
        setIsExpanding(false);
        return;
      }

      setIsExpanding(true);
      const refsData = await directFetchRefsData(
        refsNeededArray,
        getTsClient()
      );
      const refsDataMap = new Map<string, any>();
      refsNeededArray.forEach((ref, i) => {
        refsDataMap.set(ref, refsData[i]);
      });

      const expandedTraceCalls = traceCalls.map(call => {
        call = _.cloneDeep(call);
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
          if (isRef(value) && refsDataMap.has(value)) {
            const refObj = refsDataMap.get(value);
            _.set(call, path, makeRefExpandedPayload(value, refObj));
          }
        });
        return call;
      });

      doExpansionIteration(expandedTraceCalls);
    };

    doExpansionIteration(calls.result.map(c => c.traceCall!));
  }, [calls.loading, calls.result, expandedRefColumns, getTsClient]);

  return useMemo(() => {
    return {
      expandedCalls,
      isExpanding,
    };
  }, [expandedCalls, isExpanding]);
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
  if (!isRef(ref)) {
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
  if (!isRef(ref)) {
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
