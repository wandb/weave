import {Box} from '@material-ui/core';
import {
  DataGridProProps,
  GridApiPro,
  GridColDef,
  GridRowHeightParams,
} from '@mui/x-data-grid-pro';
import React, {
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
import {isRef} from '../common/util';
import {
  LIST_INDEX_EDGE_NAME,
  OBJECT_ATTR_EDGE_NAME,
} from '../wfReactInterface/constants';
import {
  USE_TABLE_FOR_ARRAYS,
  WeaveCHTableSourceRefContext,
} from './DataTableView';
import {ObjectViewerGroupingCell} from './ObjectViewerGroupingCell';
import {refIsExpandable, useRowsWithExpandedRefs} from './refExpansion';
import {ObjectPath, traverse, TraverseContext} from './traverse';
import {ValueView} from './ValueView';

type Data = Record<string, any>;

type ObjectViewerProps = {
  apiRef: React.MutableRefObject<GridApiPro>;
  data: Data;
  isExpanded: boolean;
};

// This is a general purpose object viewer that can be used to view any object.
export const ObjectViewer = ({apiRef, data, isExpanded}: ObjectViewerProps) => {
  const dataAsRows = useMemo(() => {
    return [data];
  }, [data]);
  const {resolvedRows, expandedRefs, addExpandedRef} = useRowsWithExpandedRefs(
    dataAsRows,
    true
  );
  const resolvedData = resolvedRows[0];

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
        if (refIsExpandable(context.value)) {
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
        } else {
          contexts.push(context);
        }
      }
      if (USE_TABLE_FOR_ARRAYS && context.valueType === 'array') {
        return 'skip';
      }
      if (context.value?._ref && context.value?.weave_type?.type === 'Op') {
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
            const ancestorExpandedRefSet =
              expandedRefs[ancestorPath.toString()];

            if (ancestorExpandedRefSet && ancestorExpandedRefSet.size === 1) {
              const ancestorExpandedRef = Array.from(ancestorExpandedRefSet)[0];
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
  const [expandedIds, setExpandedIds] = useState<Array<string | number>>(
    isExpanded ? rows.filter(r => !r.isExpandableRef).map(r => r.id) : []
  );
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
    [addExpandedRef]
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
          if (
            isNonRefString ||
            (isArray && USE_TABLE_FOR_ARRAYS) ||
            isTableRef ||
            isCode
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
