import {
  GridColDef,
  GridColumnGroup,
  GridColumnGroupingModel,
  GridColumnNode,
  GridValidRowModel,
} from '@mui/x-data-grid-pro';
import React from 'react';

import {isWeaveObjectRef, parseRef} from '../../../../../../../react';
import {ErrorBoundary} from '../../../../../../ErrorBoundary';
import {flattenObjectPreservingWeaveTypes} from '../../../../Browse2/browse2Util';
import {CellValue} from '../../../../Browse2/CellValue';
import {CollapseHeader} from '../../../../Browse2/CollapseGroupHeader';
import {ExpandHeader} from '../../../../Browse2/ExpandHeader';
import {NotApplicable} from '../../../../Browse2/NotApplicable';
import {SmallRef} from '../../../../Browse2/SmallRef';
import {CellFilterWrapper} from '../../../filters/CellFilterWrapper';
import {isCustomWeaveTypePayload} from '../../../typeViews/customWeaveType.types';
import {CustomWeaveTypeProjectContext} from '../../../typeViews/CustomWeaveTypeDispatcher';
import {
  OBJECT_ATTR_EDGE_NAME,
  WEAVE_PRIVATE_PREFIX,
} from '../../wfReactInterface/constants';
import {privateRefToSimpleName} from '../../wfReactInterface/tsDataModelHooks';
import {
  EXPANDED_REF_REF_KEY,
  EXPANDED_REF_VAL_KEY,
  ExpandedRefWithValue,
  isExpandedRefWithValue,
  isTableRef,
  makeRefExpandedPayload,
} from '../../wfReactInterface/tsDataModelHooksCallRefExpansion';
import {isRef} from '../util';
import {buildTree} from './buildTree';

/**
 * This function is responsible for taking the raw data and flattening it
 * into a format that can be consumed by the MUI Data Grid.
 *
 * Specifically it does 3 things:
 * 1. Flattens the nested object structure of the data
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
export function prepareFlattenedDataForTable<T>(
  data: T[]
): Array<T & {[key: string]: string}> {
  return data.map(r => {
    // First, flatten the inner object
    let flattened = flattenObjectPreservingWeaveTypes(r ?? {});

    // In the rare case that we have custom objects in the root (this only occurs if you directly)
    // publish a custom object. Then we want to instead nest it under an empty key!
    if (isCustomWeaveTypePayload(flattened)) {
      flattened = {
        ' ': flattened,
      };
    }

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
      if (newKey.includes('._') || newKey.startsWith('_')) {
        return;
      }

      // and add the cleaned key to the cleaned object
      cleaned[newKey] = flattened[key];
    });

    return cleaned as T & {[key: string]: string};
  });
}
/**
 * This processing step is admittedly a bit of a hack. It replaces "table refs"
 * (those that are of weaveKind "table" with a special format that can be
 * consumed by the CallsTable / ObjectTable. THe reason we don't want to leave plain table
 * refs in play is that they technically are not intended to be surfaced to the
 * user. However, when we fetch the data for an object with a table ref inside
 * (ie. a Dataset), the table ref is returned from the server. In some cases, we
 * want this - for example, when viewing a Dataset object, it is useful to know
 * that the `rows` key is table ref and we can render a UI appropriate for that.
 * However, we have specific business rules on the server that explicitly deny
 * data requests for the entire table ref (by design). In this way, it is a
 * "leak" of the internal data model to have a table ref in the data. To
 * compensate for this, we replace the table ref with a special format that can
 * be consumed by the CallsTable / ObjectTable. This format contains both the source ref (the
 * path from the object ref to the table data) as well as the actual table ref
 * itself. This allows the table to appropriately render a ref link to the
 * "source". We cannot just replace the ref with the source ref however, since
 * the table doesn't have any way to "know" that it is a table ref. As a
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
                const newVal: ExpandedRefWithValueAsTableRef =
                  makeRefExpandedPayload(
                    parentRef + '/' + OBJECT_ATTR_EDGE_NAME + '/' + attr,
                    val
                  );
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

type ExpandedRefWithValueAsTableRef = ExpandedRefWithValue<string>;

const isExpandedRefWithValueAsTableRef = (
  ref: any
): ref is ExpandedRefWithValueAsTableRef => {
  if (!isExpandedRefWithValue(ref)) {
    return false;
  }
  return isTableRef(ref[EXPANDED_REF_VAL_KEY]);
};

export const buildDynamicColumns = <T extends GridValidRowModel>(
  filteredDynamicColumnNames: string[],
  entityProjectFromRow: (row: T) => {entity: string; project: string},
  valueForKey: (row: T, key: string) => any,
  columnIsExpanded?: (col: string) => boolean,
  columnCanBeExpanded?: (col: string) => boolean,
  onCollapse?: (col: string) => void,
  onExpand?: (col: string) => void,
  columnIsSortable?: (col: string) => boolean,
  onAddFilter?: (field: string, operator: string | null, value: any) => void
) => {
  const cols: Array<GridColDef<T>> = [];

  const tree = buildTree([...filteredDynamicColumnNames]);
  let groupingModel: GridColumnGroupingModel = tree.children.filter(
    c => 'groupId' in c
  ) as GridColumnGroup[];

  const walkGroupingModel = (
    nodes: GridColumnNode[],
    fn: (node: GridColumnNode) => GridColumnNode
  ) => {
    return nodes.map(node => {
      node = fn(node);
      if ('children' in node) {
        node.children = walkGroupingModel(node.children, fn);
      }
      return node;
    });
  };
  const groupIds = new Set<string>();
  groupingModel = walkGroupingModel(groupingModel, node => {
    if ('groupId' in node) {
      const key = node.groupId;
      groupIds.add(key);
      if (columnIsExpanded && onCollapse && columnIsExpanded(key)) {
        node.renderHeaderGroup = () => {
          return (
            <CollapseHeader
              headerName={key.split('.').slice(-1)[0]}
              field={key}
              onCollapse={onCollapse}
            />
          );
        };
      } else if (columnCanBeExpanded && onExpand && columnCanBeExpanded(key)) {
        node.renderHeaderGroup = () => {
          return (
            <ExpandHeader
              headerName={key.split('.').slice(-1)[0]}
              field={key}
              hasExpand
              onExpand={onExpand}
            />
          );
        };
      }
    }
    return node;
  }) as GridColumnGroupingModel;

  for (const key of filteredDynamicColumnNames) {
    const col: GridColDef<T> = {
      flex: 1,
      minWidth: 150,
      field: key,
      sortable: columnIsSortable && columnIsSortable(key),
      headerName: key,
      renderHeader: () => {
        return (
          <div
            style={{
              fontWeight: 600,
            }}>
            {key.split('.').slice(-1)[0]}
          </div>
        );
      },
      valueGetter: cellParams => {
        const val = valueForKey(cellParams.row, key);
        if (Array.isArray(val) || typeof val === 'object') {
          try {
            return JSON.stringify(val);
          } catch {
            return val;
          }
        }
        return val;
      },
      renderCell: cellParams => {
        const {entity, project} = entityProjectFromRow(cellParams.row);
        const val = valueForKey(cellParams.row, key);
        if (val === undefined) {
          return (
            <CellFilterWrapper
              onAddFilter={onAddFilter}
              field={key}
              operation={'(any): isEmpty'}
              value={undefined}>
              <NotApplicable />
            </CellFilterWrapper>
          );
        }
        return (
          <ErrorBoundary>
            <CellFilterWrapper
              onAddFilter={onAddFilter}
              field={key}
              operation={null}
              value={val}
              style={{
                width: '100%',
                height: '100%',
                alignContent: 'center',
              }}>
              {/* In the future, we may want to move this isExpandedRefWithValueAsTableRef condition
            into `CellValue`. However, at the moment, `ExpandedRefWithValueAsTableRef` is a
            Table-specific data structure and we might not want to leak that into the
            rest of the system*/}
              {isExpandedRefWithValueAsTableRef(val) ? (
                <SmallRef objRef={parseRef(val[EXPANDED_REF_REF_KEY])} />
              ) : (
                <CustomWeaveTypeProjectContext.Provider
                  value={{entity, project}}>
                  <CellValue value={val} />
                </CustomWeaveTypeProjectContext.Provider>
              )}
            </CellFilterWrapper>
          </ErrorBoundary>
        );
      },
    };

    if (groupIds.has(key)) {
      col.renderHeader = () => {
        return <></>;
      };
    } else if (columnIsExpanded && onCollapse && columnIsExpanded(key)) {
      col.renderHeader = () => {
        return (
          <CollapseHeader
            headerName={key.split('.').slice(-1)[0]}
            field={key}
            onCollapse={onCollapse}
          />
        );
      };
    } else if (columnCanBeExpanded && onExpand && columnCanBeExpanded(key)) {
      col.renderHeader = () => {
        return (
          <ExpandHeader
            headerName={key.split('.').slice(-1)[0]}
            field={key}
            hasExpand
            onExpand={onExpand}
          />
        );
      };
    }
    cols.push(col);
  }

  return {cols, groupingModel};
};
