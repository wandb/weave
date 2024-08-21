import Box from '@mui/material/Box';
import {
  DataGridProProps,
  GridApiPro,
  GridColDef,
  GridRowHeightParams,
  GridRowId,
} from '@mui/x-data-grid-pro';
import _ from 'lodash';
import React, {
  Dispatch,
  SetStateAction,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';

import {LoadingDots} from '../../../../../LoadingDots';
import {Browse2OpDefCode} from '../../../Browse2/Browse2OpDefCode';
import {parseRefMaybe} from '../../../Browse2/SmallRef';
import {StyledDataGrid} from '../../StyledDataGrid';
import {isCustomWeaveTypePayload} from '../../typeViews/customWeaveType.types';
import {isRef} from '../common/util';
import {
  LIST_INDEX_EDGE_NAME,
  OBJECT_ATTR_EDGE_NAME,
} from '../wfReactInterface/constants';
import {useWFHooks} from '../wfReactInterface/context';
import {isExpandableRef} from '../wfReactInterface/tsDataModelHooksCallRefExpansion';
import {
  USE_TABLE_FOR_ARRAYS,
  WeaveCHTableSourceRefContext,
} from './DataTableView';
import {ObjectViewerGroupingCell} from './ObjectViewerGroupingCell';
import {
  getKnownImageDictContexts,
  isKnownImageDictFormat,
} from './objectViewerUtilities';
import {mapObject, ObjectPath, traverse, TraverseContext} from './traverse';
import {ValueView} from './ValueView';

type Data = Record<string, any>;

type ObjectViewerProps = {
  apiRef: React.MutableRefObject<GridApiPro>;
  data: Data;
  isExpanded: boolean;
  expandedIds: GridRowId[];
  setExpandedIds: Dispatch<SetStateAction<GridRowId[]>>;
};

// Traverse the data and find all ref URIs.
const getRefs = (data: Data): string[] => {
  const refs = new Set<string>();
  traverse(data, (context: TraverseContext) => {
    if (isRef(context.value)) {
      refs.add(context.value);
    }
  });
  return Array.from(refs);
};

type RefValues = Record<string, any>; // ref URI to value

// This is a general purpose object viewer that can be used to view any object.
export const ObjectViewer = ({
  apiRef,
  data,
  isExpanded,
  expandedIds,
  setExpandedIds,
}: ObjectViewerProps) => {
  const {useRefsData} = useWFHooks();

  // `resolvedData` holds ref-resolved data.
  const [resolvedData, setResolvedData] = useState<Data>(data);

  // `dataRefs` are the refs contained in the data, filtered to only include expandable refs.
  const dataRefs = useMemo(() => getRefs(data).filter(isExpandableRef), [data]);

  // Expanded refs are the explicit set of refs that have been expanded by the user. Note that
  // this might contain nested refs not in the `dataRefs` set. The keys are refs and the values
  // are the paths at which the refs were expanded.
  const [expandedRefs, setExpandedRefs] = useState<{[ref: string]: string}>({});

  // `addExpandedRef` is a function that can be used to add an expanded ref to the `expandedRefs` state.
  const addExpandedRef = useCallback((path: string, ref: string) => {
    setExpandedRefs(eRefs => ({...eRefs, [path]: ref}));
  }, []);

  // `refs` is the union of `dataRefs` and the refs in `expandedRefs`.
  const refs = useMemo(() => {
    return Array.from(new Set([...dataRefs, ...Object.values(expandedRefs)]));
  }, [dataRefs, expandedRefs]);

  // finally, we get the ref data for all refs. This function is highly memoized and
  // cached. Therefore, we only ever make network calls for new refs in the list.
  const refsData = useRefsData(refs);

  // This effect is responsible for resolving the refs in the data. It iteratively
  // replaces refs with their resolved values. It also adds a `_ref` key to the resolved
  // value to indicate the original ref URI. It is ultimately responsible for setting
  // `resolvedData`.
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
    let resolved = data;
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
    setResolvedData(resolved);
  }, [data, refs, refsData.loading, refsData.result]);

  // `rows` are the data-grid friendly rows that we will render. This method traverses
  // the data, hiding certain keys and adding loader rows for expandable refs.
  const {rows} = useMemo(() => {
    const contexts: Array<
      TraverseContext & {
        isExpandableRef?: boolean;
        isLoader?: boolean;
        isCode?: boolean;
      }
    > = [];
    traverse(resolvedData, context => {
      // Ops should be migrated to the generic CustomWeaveType pattern, but for
      // now they are custom handled.
      const isOpPayload = context.value?.weave_type?.type === 'Op';

      if (isCustomWeaveTypePayload(context.value) && !isOpPayload) {
        /**
         * This block adds an "empty" key that is used to render the custom
         * weave type. In the event that a custom type has both properties AND
         * custom views, then we might need to extend / modify this part.
         */
        const refBackingData = context.value?._ref;
        let depth = context.depth;
        let path = context.path;
        if (refBackingData) {
          contexts.push({
            ...context,
            isExpandableRef: true,
          });
          depth += 1;
          path = context.path.plus('');
        }
        contexts.push({
          depth,
          isLeaf: true,
          path,
          value: context.value,
          valueType: context.valueType,
        });
        return 'skip';
      }

      if (context.depth !== 0) {
        const contextTail = context.path.tail();
        const isNullDescription =
          typeof contextTail === 'string' &&
          contextTail === 'description' &&
          context.valueType === 'null';
        // For now we'll hide all keys that start with an underscore, is a name field, or is a null description.
        // Eventually we might offer a user toggle to display them.
        if (context.path.hasHiddenKey() || isNullDescription) {
          return 'skip';
        }
        if (isExpandableRef(context.value)) {
          // These are possibly expandable refs. When we encounter an expandable ref, we
          // indicate that it is expandable and add a loader row. The effect is that the
          // group header will show the expansion icon when `isExpandableRef` is true. Also,
          // until the ref data is actually resolved, we will show a loader in place of the
          // expanded data.
          contexts.push({
            ...context,
            isExpandableRef: true,
          });
          contexts.push({
            depth: context.depth + 1,
            isLeaf: true,
            path: context.path.plus(''),
            isLoader: true,
            value: '',
            valueType: 'undefined',
          });
        } else if (
          context.valueType === 'object' &&
          isKnownImageDictFormat(context.value)
        ) {
          // If we detect an object with base64 encoded image data in a known schema,
          // replace it with a patched version that can be rendered as a thumbnail.
          contexts.push(...getKnownImageDictContexts(context));
          return 'skip';
        } else {
          contexts.push(context);
        }
      }
      if (USE_TABLE_FOR_ARRAYS && context.valueType === 'array') {
        return 'skip';
      }
      if (context.value?._ref && isOpPayload) {
        // This should be moved to the CustomWeaveType pattern.
        contexts.push({
          depth: context.depth + 1,
          isLeaf: true,
          path: context.path.plus('code'),
          isCode: true,
          value: context.value?._ref,
          valueType: 'undefined',
        });
        return 'skip';
      }
      return true;
    });
    const rowsInner = contexts.map((c, id) => ({id: c.path.toString(), ...c}));
    return {rows: rowsInner};
  }, [resolvedData]);

  // Next, we setup the columns. In our case, there is just one column: Value.
  // In most cases, we just render the generic `ValueView` component. However,
  // in the case that we have an expanded ref, then we want to set the base
  // ref context such that nested table links work correctly.
  const currentRefContext = useContext(WeaveCHTableSourceRefContext);
  const columns: GridColDef[] = useMemo(() => {
    return [
      {
        field: 'value',
        headerName: 'Value',
        flex: 1,
        sortable: false,
        renderCell: ({row}) => {
          if (row.isCode) {
            return (
              <Box
                sx={{
                  width: '100%',
                  height: '100%',
                }}>
                <Browse2OpDefCode uri={row.value} maxRowsInView={20} />
              </Box>
            );
          }
          if (row.isLoader) {
            return <LoadingDots />;
          }
          let baseRef: string | undefined;
          const path: ObjectPath = row.path;
          if (currentRefContext) {
            baseRef = buildBaseRef(currentRefContext, path, path.length());
          }
          for (let i = 0; i < path.length(); i++) {
            const ancestorPath = path.ancestor(-i);
            const ancestorExpandedRef = expandedRefs[ancestorPath.toString()];
            if (ancestorExpandedRef) {
              baseRef = buildBaseRef(ancestorExpandedRef, path, i);
              break;
            }
          }

          const colInner = <ValueView data={row} isExpanded={isExpanded} />;
          if (baseRef) {
            return (
              <WeaveCHTableSourceRefContext.Provider value={baseRef}>
                {colInner}
              </WeaveCHTableSourceRefContext.Provider>
            );
          }
          return colInner;
        },
      },
    ];
  }, [currentRefContext, expandedRefs, isExpanded]);

  // Here, we setup the `Path` column which acts as a grouping column. This
  // column is responsible for showing the expand/collapse icons and handling
  // the expansion. Importantly, when the column is clicked, we do some
  // bookkeeping to add the expanded ref to the `expandedRefs` state. This
  // triggers a set of state updates to populate the expanded data.

  const groupingColDef: DataGridProProps['groupingColDef'] = useMemo(
    () => ({
      headerName: 'Path',
      hideDescendantCount: true,
      renderCell: params => {
        const refToExpand = params.row.value;
        return (
          <ObjectViewerGroupingCell
            {...params}
            onClick={() => {
              setExpandedIds(eIds => {
                if (eIds.includes(params.row.id)) {
                  return eIds.filter(id => id !== params.row.id);
                }
                return [...eIds, params.row.id];
              });
              if (isRef(refToExpand)) {
                addExpandedRef(params.row.id, refToExpand);
              }
            }}
          />
        );
      },
    }),
    [addExpandedRef, setExpandedIds]
  );

  // Next we define a function that updates the row expansion state. This
  // function is responsible for setting the expansion state of rows that have
  // been expanded by the user. It is bound to the `rowsSet` event so that it is
  // called whenever the rows are updated. The MUI data grid will rerender and
  // close all expanded rows when the rows are updated. This function is
  // responsible for re-expanding the rows that were previously expanded.
  const updateRowExpand = useCallback(() => {
    expandedIds.forEach(id => {
      if (apiRef.current.getRow(id)) {
        const children = apiRef.current.getRowGroupChildren({groupId: id});
        if (children.length !== 0) {
          apiRef.current.setRowChildrenExpansion(id, true);
        }
      }
    });
  }, [apiRef, expandedIds]);
  useEffect(() => {
    updateRowExpand();
    return apiRef.current.subscribeEvent('rowsSet', () => {
      updateRowExpand();
    });
  }, [apiRef, expandedIds, updateRowExpand]);

  // Finally, we memoize the inner data grid component. This is important to
  // reduce the number of re-renders when the data changes.
  const inner = useMemo(() => {
    return (
      <StyledDataGrid
        apiRef={apiRef}
        // Start Column Menu
        // ColumnMenu is only needed when we have other actions
        // such as filtering.
        disableColumnMenu={true}
        // In this context, we don't need to filter columns. I suppose
        // we can add this in the future, but we should be intentional
        // about what we enable.
        disableColumnFilter={true}
        disableMultipleColumnsFiltering={true}
        // ColumnPinning seems to be required in DataGridPro, else it crashes.
        disableColumnPinning={false}
        // There is no need to reorder the 2 columns in this context.
        disableColumnReorder={true}
        // Resizing columns might be helpful to show more data
        disableColumnResize={false}
        // There are only 2 columns, let's not confuse the user.
        disableColumnSelector={true}
        // We don't need to sort multiple columns.
        disableMultipleColumnsSorting={true}
        // End Column Menu
        treeData
        getTreeDataPath={row => row.path.toStringArray()}
        rows={rows}
        columns={columns}
        isGroupExpandedByDefault={node => {
          return expandedIds.includes(node.id);
        }}
        columnHeaderHeight={38}
        getRowHeight={(params: GridRowHeightParams) => {
          const isNonRefString =
            params.model.valueType === 'string' && !isRef(params.model.value);
          const isArray = params.model.valueType === 'array';
          const isTableRef =
            isRef(params.model.value) &&
            (parseRefMaybe(params.model.value) as any).weaveKind === 'table';
          const {isCode} = params.model;
          const isCustomWeaveType = isCustomWeaveTypePayload(
            params.model.value
          );
          if (
            isNonRefString ||
            (isArray && USE_TABLE_FOR_ARRAYS) ||
            isTableRef ||
            isCode ||
            isCustomWeaveType
          ) {
            return 'auto';
          }
          return 38;
        }}
        hideFooter
        rowSelection={false}
        groupingColDef={groupingColDef}
        sx={{
          borderRadius: '0px',
          '& .MuiDataGrid-row:hover': {
            backgroundColor: 'inherit',
          },
          '& > div > div > div > div > .MuiDataGrid-row > .MuiDataGrid-cell': {
            paddingRight: '0px',
            paddingLeft: '0px',
            // only the first column
            '&:first-of-type': {
              paddingRight: '8px',
            },
          },
        }}
      />
    );
  }, [apiRef, rows, columns, groupingColDef, expandedIds]);

  // Return the inner data grid wrapped in a div with overflow hidden.
  return <div style={{overflow: 'hidden'}}>{inner}</div>;
};

// Helper function to build the base ref for a given path. This function is used
// to construct the base ref for nested table links.
const buildBaseRef = (
  baseRef: string,
  path: ObjectPath,
  startIndex: number
) => {
  if (startIndex !== 0) {
    const parts = path.toPath().slice(-startIndex);
    parts.forEach(part => {
      if (typeof part === 'string') {
        baseRef += '/' + OBJECT_ATTR_EDGE_NAME + '/' + part;
      } else if (typeof part === 'number') {
        baseRef += '/' + LIST_INDEX_EDGE_NAME + '/' + part.toString();
      } else {
        console.error('Invalid path part:', part);
      }
    });
  }
  return baseRef;
};
