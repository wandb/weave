import Box from '@mui/material/Box';
import {
  DataGridProProps,
  GridApiPro,
  GridColDef,
  GridRowHeightParams,
  GridRowId,
} from '@mui/x-data-grid-pro';
import {Button} from '@wandb/weave/components/Button';
import {parseRef} from '@wandb/weave/react';
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

import {parseRefMaybe} from '../../../../../../react';
import {LoadingDots} from '../../../../../LoadingDots';
import {Browse2OpDefCode} from '../../../Browse2/Browse2OpDefCode';
import {isWeaveRef} from '../../filters/common';
import {objectRefDisplayName} from '../../smallRef/SmallWeaveRef';
import {StyledDataGrid} from '../../StyledDataGrid';
import {
  CustomWeaveTypePayload,
  isCustomWeaveTypePayload,
} from '../../typeViews/customWeaveType.types';
import {getCustomWeaveTypePreferredRowHeight} from '../../typeViews/CustomWeaveTypeDispatcher';
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
import {
  getValueType,
  mapObject,
  ObjectPath,
  traverse,
  TraverseContext,
} from './traverse';
import {ValueView} from './ValueView';

const DEFAULT_ROW_HEIGHT = 38;
const CODE_ROW_HEIGHT = 350;
const TABLE_ROW_HEIGHT = 450;

type Data = Record<string, any> | any[];

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
    if (isWeaveRef(context.value)) {
      refs.add(context.value);
    }
  });
  return Array.from(refs);
};

type RefValues = Record<string, any>; // ref URI to value

type TruncatedStore = {[key: string]: {values: any; index: number}};

const RESOLVED_REF_KEY = '_ref';

export const ARRAY_TRUNCATION_LENGTH = 50;
const TRUNCATION_KEY = '__weave_array_truncated__';

// This is a general purpose object viewer that can be used to view any object.
export const ObjectViewer = ({
  apiRef,
  data,
  isExpanded,
  expandedIds,
  setExpandedIds,
}: ObjectViewerProps) => {
  const {useRefsData} = useWFHooks();

  // `truncatedData` holds the data with all arrays truncated to ARRAY_TRUNCATION_LENGTH, unless we have specifically added more rows to the array
  // `truncatedStore` is used to store the additional rows that we can add to the array when the user clicks "Show more"
  const {truncatedData, truncatedStore, setTruncatedData, setTruncatedStore} =
    useTruncatedData(data);

  // `resolvedData` holds ref-resolved data.
  const [resolvedData, setResolvedData] = useState<Data>(truncatedData);

  // `dataRefs` are the refs contained in the data, filtered to only include expandable refs.
  const dataRefs = useMemo(() => getRefs(data).filter(isExpandableRef), [data]);

  // Expanded refs are the explicit set of refs that have been expanded by the user. Note that
  // this might contain nested refs not in the `dataRefs` set. The keys are object paths at which the refs were expanded
  // and the values are the corresponding ref string.
  const [expandedRefs, setExpandedRefs] = useState<{[path: string]: string}>(
    {}
  );

  // `addExpandedRef` is a function that can be used to add an expanded ref to the `expandedRefs` state.
  const addExpandedRef = useCallback((path: string, ref: string) => {
    setExpandedRefs(eRefs => ({...eRefs, [path]: ref}));
  }, []);

  // This effect will ensure that all "expandedIds" whose value is a ref
  // have the ref added to the `expandedRefs` state.
  useEffect(() => {
    const expandRefsToAdd: {[path: string]: string} = {};
    const mapper = (context: TraverseContext) => {
      const contextPath = context.path.toString();
      if (
        expandedIds.includes(contextPath) &&
        isWeaveRef(context.value) &&
        expandedRefs[contextPath] == null
      ) {
        expandRefsToAdd[contextPath] = context.value;
      }
      return context.value;
    };
    mapObject(resolvedData, mapper);
    if (Object.keys(expandRefsToAdd).length > 0) {
      setExpandedRefs(eRefs => ({...eRefs, ...expandRefsToAdd}));
    }
  }, [resolvedData, expandedIds, expandedRefs, setExpandedRefs]);

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
      if (!r) {
        // Shouldn't be possible
        continue;
      }
      if (!v) {
        // Value for ref not found, must be deleted
        refValues[r] = deletedRefValuePlaceholder(r);
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
            [RESOLVED_REF_KEY]: r,
          };
        } else {
          // This makes it so that runs pointing to primitives can still be expanded in the table.
          val = {
            '': v,
            [RESOLVED_REF_KEY]: r,
          };
        }
      }
      refValues[r] = val;
    }
    let resolved = truncatedData;
    let dirty = true;
    const mapper = (context: TraverseContext) => {
      if (
        isWeaveRef(context.value) &&
        refValues[context.value] != null &&
        // Don't expand _ref keys
        context.path.tail() !== RESOLVED_REF_KEY
      ) {
        dirty = true;
        return refValues[context.value];
      }
      return _.clone(context.value);
    };
    while (dirty) {
      dirty = false;
      resolved = mapObject(resolved, mapper);
    }
    setResolvedData(resolved);
  }, [data, refs, refsData.loading, refsData.result, truncatedData]);

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
        const isNullDescriptionOrName =
          typeof contextTail === 'string' &&
          (contextTail === 'description' || contextTail === 'name') &&
          context.valueType === 'null';
        // For now we'll hide all keys that start with an underscore, is a name field, or is a null description.
        // Eventually we might offer a user toggle to display them.
        if (context.path.hasHiddenKey() || isNullDescriptionOrName) {
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
        display: 'flex',
        sortable: false,
        renderCell: ({row}) => {
          const isTruncated = row?.value?.[TRUNCATION_KEY];
          const parentPath = row?.parent?.path?.toString() ?? '';
          if (isTruncated && truncatedStore[parentPath]) {
            return (
              <ShowMoreButtons
                parentPath={parentPath}
                truncatedData={truncatedData}
                truncatedStore={truncatedStore}
                setTruncatedData={setTruncatedData}
                setTruncatedStore={setTruncatedStore}
              />
            );
          }
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
  }, [
    currentRefContext,
    expandedRefs,
    isExpanded,
    truncatedData,
    truncatedStore,
    setTruncatedData,
    setTruncatedStore,
  ]);

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
        const isTruncated = params.row?.value?.[TRUNCATION_KEY];
        if (isTruncated) {
          return null;
        }

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
              if (isWeaveRef(refToExpand)) {
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

  // Per https://mui.com/x/react-data-grid/row-height/#dynamic-row-height, always
  // memoize the getRowHeight function.
  const getRowHeight = useCallback((params: GridRowHeightParams) => {
    const isNonRefString =
      params.model.valueType === 'string' && !isWeaveRef(params.model.value);
    const isArray = params.model.valueType === 'array';
    const isTableRef =
      isWeaveRef(params.model.value) &&
      (parseRefMaybe(params.model.value) as any).weaveKind === 'table';
    const {isCode} = params.model;
    const isCustomWeaveType = isCustomWeaveTypePayload(params.model.value);
    if (!params.model.isLeaf) {
      // This is a group header, so we want to use the default height
      return DEFAULT_ROW_HEIGHT;
    } else if (isNonRefString) {
      // This is the only special case where we will allow for dynamic height.
      // Since strings have special renders that take up different amounts of
      // space, we will allow for dynamic height.
      return 'auto';
    } else if (isCustomWeaveType) {
      const type = (params.model.value as CustomWeaveTypePayload).weave_type
        .type;
      const preferredRowHeight = getCustomWeaveTypePreferredRowHeight(type);
      if (preferredRowHeight) {
        return preferredRowHeight;
      }
      return DEFAULT_ROW_HEIGHT;
    } else if ((isArray && USE_TABLE_FOR_ARRAYS) || isTableRef) {
      // Perfectly enough space for 1 page of data rows
      return TABLE_ROW_HEIGHT;
    } else if (isCode) {
      // Probably will get negative feedback here since code that is < 20 lines
      // will have some whitespace below the code. However, we absolutely need
      // to have static height for all cells else the MUI data grid will jump around
      // when cleaning up virtual rows.
      return CODE_ROW_HEIGHT;
    } else {
      return DEFAULT_ROW_HEIGHT;
    }
  }, []);

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
        rowHeight={DEFAULT_ROW_HEIGHT}
        getRowHeight={getRowHeight}
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

          // Honestly, this feels like a bug with MUI datagrid.
          // Normally, we would want autohieght as a prop as well as
          // a parent with adaptive hieght which would result in an
          // adaptive datagrid. However, that end up being very slow
          // when there are many rows.
          //
          // Instead, when autoheight is false, MUI datagrid will
          // retain the larget height, even after collapsing. It does
          // this by synthetically injecting a filler div and adding
          // a height to it. I don't quite understand why it does this,
          // but it does.
          //
          // This hack basically hides that dom element, resulting in a
          // performant, adaptive datagrid.
          '& .MuiDataGrid-filler': {
            height: '0px !important',
          },
        }}
      />
    );
  }, [apiRef, rows, columns, getRowHeight, groupingColDef, expandedIds]);

  // Return the inner data grid wrapped in a div with overflow hidden.
  return <div style={{overflow: 'hidden', height: '100%'}}>{inner}</div>;
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
        baseRef += '/' + OBJECT_ATTR_EDGE_NAME + '/' + encodeURIComponent(part);
      } else if (typeof part === 'number') {
        baseRef += '/' + LIST_INDEX_EDGE_NAME + '/' + part.toString();
      } else {
        console.error('Invalid path part:', part);
      }
    });
  }
  return baseRef;
};

// This function traverses the data and truncates the current node if it is an array and the length is greater than ARRAY_TRUNCATION_LENGTH(50)
const traverseAndTruncate = (data: Data): any => {
  const result = getValueType(data) === 'array' ? [] : {};

  const store: TruncatedStore = {};
  traverse(data, (context: TraverseContext) => {
    let value = context.value;

    // Truncates the value if it is an array and the length is greater than ARRAY_TRUNCATION_LENGTH
    if (Array.isArray(value) && value.length > ARRAY_TRUNCATION_LENGTH) {
      // Stores the truncated values in the store
      store[context.path.toString()] = {
        values: value.slice(ARRAY_TRUNCATION_LENGTH),
        index: ARRAY_TRUNCATION_LENGTH,
      };

      // Truncates and sets the value to ARRAY_TRUNCATION_LENGTH
      value = [
        ...value.slice(0, ARRAY_TRUNCATION_LENGTH),
        {
          [TRUNCATION_KEY]: true,
        },
      ];
      context.value = value;
    }

    // Passes the value to the result
    if (context.depth === 0) {
      // For the root object, we just want to assign the value to the result
      if (Array.isArray(result)) {
        result.push(...value);
      } else {
        Object.assign(result, value);
      }
    } else {
      // For all other objects, we want to assign the value to the result
      context.path.set(result, value);
    }
  });
  return {store, result};
};

// This function updates the truncatedData from the truncatedStore, adding more data to the truncatedData array, based on the parentID and truncatedCount
const updateTruncatedDataFromStore = (
  key: string,
  truncatedData: Data,
  truncatedStore: TruncatedStore,
  truncatedCount: number = ARRAY_TRUNCATION_LENGTH
) => {
  const store = {
    ...truncatedStore,
  };

  const newData = mapObject(truncatedData, (context: TraverseContext) => {
    // If the path is the key, we need to show more data
    if (context.path.toString() === key) {
      const storeValue = truncatedStore[key].values;
      // Depending on the length of the store value, we either add truncatedCount more, or the rest of the values
      if (storeValue.length > truncatedCount) {
        // Remove the truncated indicator
        context.value.pop();
        // Add the new values and truncated indicator
        context.value.push(...storeValue.slice(0, truncatedCount));
        context.value.push({
          [TRUNCATION_KEY]: true,
        });
        // Update the store
        store[key] = {
          values: storeValue.slice(truncatedCount),
          index: store[key].index + truncatedCount,
        };
      } else {
        // Remove the truncated indicator
        context.value.pop();
        // Add the new values
        context.value.push(...storeValue);
        // Update the store
        delete store[key];
      }
    }
    return context.value;
  });
  return {newData, store};
};

const ShowMoreButtons = ({
  parentPath,
  truncatedData,
  truncatedStore,
  setTruncatedData,
  setTruncatedStore,
}: {
  parentPath: string;
  truncatedData: Data;
  truncatedStore: TruncatedStore;
  setTruncatedData: (data: Data) => void;
  setTruncatedStore: (store: TruncatedStore) => void;
}) => {
  const truncatedCount = truncatedStore[parentPath]?.values.length ?? 0;
  return (
    <Box
      sx={{
        display: 'flex',
        width: '100%',
        justifyContent: 'flex-start',
        gap: 1,
      }}>
      {truncatedCount > ARRAY_TRUNCATION_LENGTH && (
        <Button
          variant="ghost"
          onClick={() => {
            const {newData, store} = updateTruncatedDataFromStore(
              parentPath,
              truncatedData,
              truncatedStore,
              ARRAY_TRUNCATION_LENGTH
            );
            setTruncatedData(newData);
            setTruncatedStore(store);
          }}>
          {`Show ${ARRAY_TRUNCATION_LENGTH} more rows`}
        </Button>
      )}
      <Button
        variant="ghost"
        onClick={() => {
          const {newData, store} = updateTruncatedDataFromStore(
            parentPath,
            truncatedData,
            truncatedStore,
            truncatedCount
          );
          setTruncatedData(newData);
          setTruncatedStore(store);
        }}>
        {`Show ${truncatedCount} more rows`}
      </Button>
    </Box>
  );
};

const useTruncatedData = (data: Data) => {
  const [truncatedData, setTruncatedData] = useState<Data>(data);
  const [truncatedStore, setTruncatedStore] = useState<TruncatedStore>({});

  useEffect(() => {
    const {store, result} = traverseAndTruncate(data);
    setTruncatedData(result);
    setTruncatedStore(store);
  }, [data]);

  return {truncatedData, truncatedStore, setTruncatedData, setTruncatedStore};
};

// Placeholder value for deleted refs
const DELETED_REF_KEY = '_weave_deleted_ref';
const deletedRefValuePlaceholder = (
  ref: string
): {[DELETED_REF_KEY]: string} => {
  const parsedRef = parseRef(ref);
  const refString = objectRefDisplayName(parsedRef).label;
  return {[DELETED_REF_KEY]: refString};
};
export const maybeGetDeletedRefValuePlaceholderFromRow = (
  row: any
): string | undefined => {
  return row.value?.[DELETED_REF_KEY];
};
