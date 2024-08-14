import {
  DataGridProProps,
  GridColDef,
  GridRowHeightParams,
  GridRowId,
  useGridApiRef,
} from '@mui/x-data-grid-pro';
import React, {useCallback, useEffect, useMemo, useState} from 'react';

import {isRef} from '../pages/common/util';
import {StyledDataGrid} from '../StyledDataGrid';
import {DiffValue} from './DiffValue';
import {DiffViewerGroupingCell} from './DiffViewerGroupingCell';
import {RowData} from './types';

type DiffGridProps = {
  rows: RowData[];
  isExpanded?: boolean;
};

export const DiffGrid = ({rows, isExpanded}: DiffGridProps) => {
  const apiRef = useGridApiRef();

  const columns: GridColDef[] = [
    {
      field: 'value',
      headerName: 'Value',
      flex: 1,
      sortable: false,
      renderCell: ({row}) => {
        return (
          <DiffValue
            type={row.type}
            left={row.left}
            right={row.right}
            panels={row.panels}
          />
        );
      },
    },
  ];

  const [expandedIds, setExpandedIds] = useState<GridRowId[]>([]);

  // Expanded refs are the explicit set of refs that have been expanded by the user. Note that
  // this might contain nested refs not in the `dataRefs` set. The keys are refs and the values
  // are the paths at which the refs were expanded.
  const [expandedRefs, setExpandedRefs] = useState<{[ref: string]: string}>({});

  // `addExpandedRef` is a function that can be used to add an expanded ref to the `expandedRefs` state.
  const addExpandedRef = useCallback((path: string, ref: string) => {
    setExpandedRefs(eRefs => ({...eRefs, [path]: ref}));
  }, []);

  // Here, we setup the `Path` column which acts as a grouping column. This
  // column is responsible for showing the expand/collapse icons and handling
  // the expansion. Importantly, when the column is clicked, we do some
  // bookkeeping to add the expanded ref to the `expandedRefs` state. This
  // triggers a set of state updates to populate the expanded data.

  const groupingColDef: DataGridProProps['groupingColDef'] = useMemo(
    () => ({
      headerName: 'Path',
      hideDescendantCount: true,
      width: 300,
      renderCell: params => {
        const refToExpand = params.row.value;
        return (
          <DiffViewerGroupingCell
            {...params}
            onClick={() => {
              const pathId = params.row.path.toString();
              setExpandedIds(eIds => {
                if (eIds.includes(pathId)) {
                  return eIds.filter(id => id !== pathId);
                }
                return [...eIds, pathId];
              });
              if (isRef(refToExpand)) {
                addExpandedRef(pathId, refToExpand);
              }
            }}
          />
        );
      },
    }),
    [addExpandedRef, setExpandedIds]
  );

  const getRowId = row => {
    return row.path.toString();
  };

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

  const getGroupIds = useCallback(() => {
    const rowIds = apiRef.current.getAllRowIds();
    return rowIds.filter(rowId => {
      const rowNode = apiRef.current.getRowNode(rowId);
      return rowNode && rowNode.type === 'group';
    });
  }, [apiRef]);

  // On first render and when data changes, recompute expansion state
  useEffect(() => {
    // const isSimple = isSimpleData(data);
    // const newMode = isSimple || isExpanded ? 'expanded' : 'collapsed';
    // if (newMode === 'expanded') {
    //   onClickExpanded();
    // } else {
    //   onClickCollapsed();
    // }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    setExpandedIds(getGroupIds());
  }, []);

  return (
    <StyledDataGrid
      apiRef={apiRef}
      getRowId={getRowId}
      treeData
      groupingColDef={groupingColDef}
      getTreeDataPath={row => row.path.toStringArray()}
      columns={columns}
      rows={rows}
      isGroupExpandedByDefault={node => {
        return expandedIds.includes(node.id);
      }}
      columnHeaderHeight={38}
      disableColumnReorder={true}
      disableColumnMenu={true}
      getRowHeight={(params: GridRowHeightParams) => {
        // const isNonRefString =
        //   params.model.valueType === 'string' && !isRef(params.model.value);
        // const isArray = params.model.valueType === 'array';
        // const isTableRef =
        //   isRef(params.model.value) &&
        //   (parseRefMaybe(params.model.value) as any).weaveKind === 'table';
        // const {isCode} = params.model;
        // if (
        //   isNonRefString ||
        //   (isArray && USE_TABLE_FOR_ARRAYS) ||
        //   isTableRef ||
        //   isCode
        // ) {
        //   return 'auto';
        // }
        return 38;
        // return 'auto';
      }}
      rowSelection={false}
      hideFooter
    />
  );
};
