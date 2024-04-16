import _ from 'lodash';
import {useCallback, useEffect, useMemo, useState} from 'react';

import {isWeaveObjectRef, parseRef} from '../../../../../../react';
import {isRef} from '../common/util';
import {useWFHooks} from '../wfReactInterface/context';
import {mapObject, traverse, TraverseContext} from './traverse';

type Rows = Array<Row>;
type Row = Record<string, any>;

export const useRowsWithExpandedRefs = (
  rows: Rows,
  shouldAutoExpand: boolean
) => {
  const {useRefsData} = useWFHooks();

  // `resolvedRows` holds ref-resolved data.
  const [resolvedRows, setResolvedRows] = useState<Rows>(rows);

  // `dataRefs` are the refs contained in the data, filtered to only include expandable refs.
  const dataRefs = useMemo(() => getRefs(rows).filter(refIsExpandable), [rows]);

  // Expanded refs are the explicit set of refs that have been expanded by the user. Note that
  // this might contain nested refs not in the `dataRefs` set. The keys are refs and the values
  // are the paths at which the refs were expanded.
  const [expandedRefs, setExpandedRefs] = useState<{
    [ref: string]: Set<string>;
  }>({});

  // `addExpandedRef` is a function that can be used to add an expanded ref to the `expandedRefs` state.
  const addExpandedRef = useCallback((path: string, ref: string) => {
    setExpandedRefs(eRefs => {
      if (!eRefs[path]) {
        eRefs[path] = new Set([]);
      }
      eRefs[path].add(ref);
      return eRefs;
    });
  }, []);

  // `refs` is the union of `dataRefs` and the refs in `expandedRefs`.
  const refs = useMemo(() => {
    const allRefs = new Set<string>([]);
    if (shouldAutoExpand) {
      for (const ref of dataRefs) {
        allRefs.add(ref);
      }
    }
    for (const path of Object.keys(expandedRefs)) {
      for (const ref of expandedRefs[path]) {
        allRefs.add(ref);
      }
    }
    return Array.from(allRefs);
  }, [dataRefs, expandedRefs, shouldAutoExpand]);

  // finally, we get the ref data for all refs. This function is highly memoized and
  // cached. Therefore, we only ever make network calls for new refs in the list.
  const refsData = useRefsData(refs);

  // This effect is responsible for resolving the refs in the data. It iteratively
  // replaces refs with their resolved values. It also adds a `_ref` key to the resolved
  // value to indicate the original ref URI. It is ultimately responsible for setting
  // `resolvedRows`.
  useEffect(() => {
    if (refsData.loading) {
      return;
    }
    const resolvedRefData = refsData.result;

    const refValues: RefValues = {};
    for (const [r, v] of _.zip(refs, resolvedRefData)) {
      if (!r || !v) {
        // Shouldn't be possible
        continue;
      }
      let val = r;
      if (v == null) {
        console.error('Error resolving ref', r);
      } else {
        val = v;
        if (typeof val === 'object' && val !== null) {
          val = {
            ...v,
            _ref: r,
          };
        } else {
          // This makes it so that runs pointing to primitives can still be expanded in the table.
          val = {
            '': v,
            _ref: r,
          };
        }
      }
      refValues[r] = val;
    }
    const resolved = rows.map(row => {
      let resolved = row;
      let dirty = true;
      const mapper = (context: TraverseContext) => {
        if (isRef(context.value) && refValues[context.value] != null) {
          dirty = true;
          const res = refValues[context.value];
          delete refValues[context.value];
          return res;
        }
        return _.clone(context.value);
      };
      while (dirty) {
        dirty = false;
        resolved = mapObject(resolved, mapper);
      }
      return resolved;
    });
    setResolvedRows(resolved);
  }, [refs, refsData.loading, refsData.result, rows]);

  return {resolvedRows, expandedRefs, addExpandedRef};
};

// Traverse the data and find all ref URIs.
const getRefs = (data: Row): string[] => {
  const refs = new Set<string>();
  traverse(data, (context: TraverseContext) => {
    if (isRef(context.value)) {
      refs.add(context.value);
    }
  });
  return Array.from(refs);
};

type RefValues = Record<string, any>; // ref URI to value

export const refIsExpandable = (ref: string): boolean => {
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
