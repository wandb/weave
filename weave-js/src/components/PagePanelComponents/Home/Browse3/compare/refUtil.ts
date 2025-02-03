import {isWeaveRef} from '../filters/common';
import {traverse, TraverseContext} from '../pages/CallPage/traverse';
import {isExpandableRef} from '../pages/wfReactInterface/tsDataModelHooksCallRefExpansion';
import {ComparableObjects} from './types';

// When we replace a ref with its resolved data we insert this key
// with the ref URI to keep track of the original value.
export const RESOLVED_REF_KEY = '_ref';

export type RefValues = Record<string, any>; // ref URI to value

// Traverse the data and find all ref URIs.
export const getRefs = (objects: ComparableObjects): string[] => {
  const refs = new Set<string>();
  for (const obj of objects) {
    traverse(obj, (context: TraverseContext) => {
      if (isWeaveRef(context.value)) {
        refs.add(context.value);
      }
    });
  }
  return Array.from(refs);
};

// Get the refs in the objects that are expandable.
export const getExpandableRefs = (objects: ComparableObjects): string[] => {
  return getRefs(objects).filter(isExpandableRef);
};
