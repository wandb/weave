import _ from 'lodash';
import {useCallback, useEffect, useMemo, useState} from 'react';

import {isWeaveObjectRef, parseRef} from '../../../../../../react';
import {isRef} from '../common/util';
import {useWFHooks} from '../wfReactInterface/context';
import {mapObject, traverse, TraverseContext} from './traverse';

// TODO: Remove this
export const NON_OBJECT_OUTPUT_KEY = '_result';
export const EXPANDED_REF_REF_KEY = '__ref';
export const EXPANDED_REF_VALUE_KEY = '__value';

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
  // this might contain nested refs not in the `dataRefs` set. The keys are paths and the values
  // are the refs.
  // TODO: remove path concept
  const [expandedRefs, setExpandedRefs] = useState<{
    [path: string]: Set<string>;
  }>({});

  // `addExpandedRef` is a function that can be used to add an expanded ref to the `expandedRefs` state.
  const addExpandedRefs = useCallback(
    (newRefs: Array<{path: string; ref: string}>) => {
      setExpandedRefs(eRefs => {
        for (const {path, ref} of newRefs) {
          if (!eRefs[path]) {
            eRefs[path] = new Set([]);
          }
          eRefs[path].add(ref);
        }
        return {...eRefs};
      });
    },
    []
  );

  // `refs` is the union of `dataRefs` and the refs in `expandedRefs`.
  const refs = useMemo(() => {
    const allRefs = new Set<string>([]);
    if (shouldAutoExpand) {
      for (const ref of dataRefs) {
        allRefs.add(ref);
      }
    }
    Object.values(expandedRefs).forEach(refs => {
      for (const ref of refs) {
        allRefs.add(ref);
      }
    });

    return Array.from(allRefs);
  }, [dataRefs, expandedRefs, shouldAutoExpand]);

  // finally, we get the ref data for all refs. This function is highly memoized and
  // cached. Therefore, we only ever make network calls for new refs in the list.
  const refsData = useRefsData(refs);

  // This effect is responsible for resolving the refs in the data. It iteratively
  // replaces refs with their resolved values. It also adds a `_ref` key to the resolved
  // value to indicate the original ref URI. It is ultimately responsible for setting
  // `resolvedRows`.
  console.log(refs, refsData);
  useEffect(() => {
    if (refsData.loading) {
      return;
    }
    const resolvedRefData = refsData.result;

    const refValues: RefValues = {};
    for (const [r, v] of _.zip(refs, resolvedRefData)) {
      console.log({r, v});
      if (!r || !v) {
        // Shouldn't be possible
        console.log('Error resolving ref', r, v);
        continue;
      }
      let val = r;
      if (v == null) {
        console.error('Error resolving ref', r);
      } else {
        val = v;
        if (typeof val === 'object' && val !== null) {
          // TODO: FIX OBJECT VIEWER!
          val = {
            [EXPANDED_REF_VALUE_KEY]: v,
            [EXPANDED_REF_REF_KEY]: r,
          };
        } else {
          // This makes it so that runs pointing to primitives can still be expanded in the table.
          val = {
            // TODO: FIX OBJECT VIEWER!
            [EXPANDED_REF_VALUE_KEY]: v,
            [EXPANDED_REF_REF_KEY]: r,
          };
        }
      }
      refValues[r] = val;
    }
    console.log({refs, resolvedRefData, rows, refValues});
    const resolved = rows.map(row => {
      let resolved = row;
      let dirty = true;
      const replacedPaths = new Set<string>();
      const mapper = (context: TraverseContext) => {
        const path = context.path.toString();
        if (
          replacedPaths.has(path) ||
          context.path.endsWith(EXPANDED_REF_REF_KEY)
        ) {
          return context.value;
        }
        if (isRef(context.value) && refValues[context.value] != null) {
          dirty = true;
          const res = refValues[context.value];
          // delete refValues[context.value];
          replacedPaths.add(path);
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

  return {resolvedRows, expandedRefs, addExpandedRefs};
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
