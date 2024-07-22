import {isWeaveObjectRef, parseRef} from '../../../../../../react';
import {flattenObject} from '../../../Browse2/browse2Util';
import {isRef} from '../common/util';
import {
  OBJECT_ATTR_EDGE_NAME,
  WEAVE_PRIVATE_PREFIX,
} from '../wfReactInterface/constants';
import {TraceCallSchema} from '../wfReactInterface/traceServerClient';
import {privateRefToSimpleName} from '../wfReactInterface/tsDataModelHooks';
import {
  EXPANDED_REF_REF_KEY,
  EXPANDED_REF_VAL_KEY,
} from '../wfReactInterface/tsDataModelHooksCallRefExpansion';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {ExpandedRefWithValueAsTableRef} from './callsTableColumns';

/**
 * This function is responsible for taking the raw calls data and flattening it
 * into a format that can be consumed by the MUI Data Grid. Importantly, we strip
 * away the legacy `CallSchema` wrapper and just operate on the inner `TraceCallSchema`
 *
 * Specifically it does 3 things:
 * 1. Flattens the nested object structure of the calls data
 * 2. Removes any keys that start with underscore
 * 3. Converts expanded values to their actual values. This takes two forms:
 *    1. If expanded value is a dictionary, then the flattened data will look like:
 *      {
 *        [EXPANDED_REF_REF_KEY]: 'weave://...',
 *        [EXPANDED_REF_VAL_KEY].sub_key_x: 'value_x',
 *         ...
 *      }
 *      In this case, we want to remove the [EXPANDED_REF_REF_KEY] and [EXPANDED_REF_VAL_KEY] from the paths,
 *      leaving everything else. The result is that the ref is left at the primitive position for the data.
 *     2. If the expanded value is a primitive, then the flattened data will look like:
 *      {
 *        [EXPANDED_REF_REF_KEY]: 'weave://...',
 *        [EXPANDED_REF_VAL_KEY]: 'value'
 *      }
 *      In this case, we don't have a place to put the ref value, so we just remove it.
 */
export function prepareFlattenedCallDataForTable(
  callsResult: CallSchema[]
): Array<TraceCallSchema & {[key: string]: string}> {
  return callsResult.map(r => {
    // First, flatten the inner trace call (this is the on-wire format)
    let flattened = flattenObject(r.traceCall ?? {});

    flattened = replaceTableRefsInFlattenedData(flattened);

    // Next, process some of the keys.
    const cleaned: {[key: string]: any} = {};
    Object.keys(flattened).forEach(key => {
      let newKey = key;

      // If the key ends with the expanded ref key, then we have 2 cases
      if (key.endsWith('.' + EXPANDED_REF_REF_KEY)) {
        const keyRoot = newKey.slice(0, -EXPANDED_REF_REF_KEY.length - 1);

        // Case 1: the refVal is a primitive and we just need to toss away the ref key
        const refValIsPrimitive =
          flattened[newKey + '.' + EXPANDED_REF_VAL_KEY] !== undefined;
        if (refValIsPrimitive) {
          return;

          // Case 2: the refVal is a dictionary and we just remove the ref part of the path
        } else {
          newKey = keyRoot;
        }
      }

      // Next, we remove all path parts that are the expanded ref val key
      if (newKey.includes('.' + EXPANDED_REF_VAL_KEY)) {
        newKey = newKey.replaceAll('.' + EXPANDED_REF_VAL_KEY, '');
      }

      // Finally, we remove any keys that start with underscore
      if (newKey.includes('._')) {
        return;
      }

      // and add the cleaned key to the cleaned object
      cleaned[newKey] = flattened[key];
    });

    return cleaned as TraceCallSchema & {[key: string]: string};
  });
}
/**
 * This processing step is admittedly a bit of a hack. It replaces "table refs"
 * (those that are of weaveKind "table" with a special format that can be
 * consumed by the CallsTable. THe reason we don't want to leave plain table
 * refs in play is that they technically are not intended to be surfaced to the
 * user. However, when we fetch the data for an object with a table ref inside
 * (ie. a Dataset), the table ref is returned from the server. In some cases, we
 * want this - for example, when viewing a Dataset object, it is useful to know
 * that the `rows` key is table ref and we can render a UI appropriate for that.
 * However, we have specific business rules on the server that explicitly deny
 * data requests for the entire table ref (by design). In this way, it is a
 * "leak" of the internal data model to have a table ref in the data. To
 * compensate for this, we replace the table ref with a special format that can
 * be consumed by the CallsTable. This format contains both the source ref (the
 * path from the object ref to the table data) as well as the actual table ref
 * itself. This allows the calls table to appropriately render a ref link to the
 * "source". We cannot just replace the ref with the source ref however, since
 * the calls table doesn't have any way to "know" that it is a table ref. As a
 * result, it would think that this ref is expandable, which is not a valid
 * operation. Therefore, we use this special type
 * `ExpandedRefWithValueAsTableRef` to handle this case.
 */
function replaceTableRefsInFlattenedData(flattened: Record<string, any>) {
  return Object.fromEntries(
    Object.entries(flattened).map(([key, val]) => {
      if (isRef(val)) {
        const parsedRef = parseRef(val);
        if (isWeaveObjectRef(parsedRef)) {
          if (parsedRef.weaveKind === 'table') {
            let parentRef: string | null = null;
            const lookupPath = key.split('.');
            if (lookupPath.length > 0) {
              const attr = lookupPath.pop()!;
              while (lookupPath.length > 0) {
                const parentKey =
                  lookupPath.join('.') + '.' + EXPANDED_REF_REF_KEY;
                if (parentKey in flattened) {
                  const parentVal = flattened[parentKey];
                  if (isRef(parentVal)) {
                    parentRef = parentVal;
                  }
                  break;
                }
                lookupPath.pop();
              }
              if (parentRef) {
                const newVal: ExpandedRefWithValueAsTableRef = {
                  [EXPANDED_REF_REF_KEY]:
                    parentRef + '/' + OBJECT_ATTR_EDGE_NAME + '/' + attr,
                  [EXPANDED_REF_VAL_KEY]: val,
                };
                return [key, newVal];
              }
            }
          }
        }
      } else if (
        typeof val === 'string' &&
        val.startsWith(WEAVE_PRIVATE_PREFIX)
      ) {
        return [key, privateRefToSimpleName(val)];
      }
      return [key, val];
    })
  );
}
