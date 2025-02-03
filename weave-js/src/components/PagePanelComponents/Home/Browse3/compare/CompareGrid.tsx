/**
 * This is similar to the ObjectViewer but allows for multiple objects
 * to be displayed side-by-side.
 */

import {
  DataGridProProps,
  GRID_TREE_DATA_GROUPING_FIELD,
  GridColDef,
  GridPinnedColumnFields,
  GridRowHeightParams,
  GridRowId,
  GridValidRowModel,
  useGridApiRef,
} from '@mui/x-data-grid-pro';
import React, {useCallback, useEffect, useMemo} from 'react';

import {WeaveObjectRef} from '../../../../../react';
import {ObjectVersionSchema} from '../pages/wfReactInterface/wfDataModelHooksInterface';
import {SmallRef} from '../smallRef/SmallRef';
import {StyledDataGrid} from '../StyledDataGrid';
import {RowDataWithDiff, UNCHANGED} from './compare';
import {CompareGridCell} from './CompareGridCell';
import {CompareGridGroupingCell} from './CompareGridGroupingCell';
import {ComparableObject, Mode} from './types';

type CompareGridProps = {
  objectType: 'object' | 'call';
  objectIds: string[];
  objects: ComparableObject[];
  rows: RowDataWithDiff[];
  mode: Mode;
  baselineEnabled: boolean;
  onlyChanged: boolean;

  expandedIds: GridRowId[];
  setExpandedIds: React.Dispatch<React.SetStateAction<GridRowId[]>>;
  addExpandedRefs: (path: string, refs: string[]) => void;
};

export const MAX_OBJECT_COLS = 6;

const objectVersionSchemaToRef = (
  objVersion: ObjectVersionSchema
): WeaveObjectRef => {
  return {
    scheme: 'weave',
    entityName: objVersion.entity,
    projectName: objVersion.project,
    weaveKind: 'object',
    artifactName: objVersion.objectId,
    artifactVersion: objVersion.versionHash,
  };
};

export const CompareGrid = ({
  objectType,
  objectIds,
  objects,
  rows,
  mode,
  baselineEnabled,
  onlyChanged,
  expandedIds,
  setExpandedIds,
  addExpandedRefs,
}: CompareGridProps) => {
  const apiRef = useGridApiRef();

  const filteredRows = onlyChanged
    ? rows.filter(row => row.changeType !== UNCHANGED)
    : rows;

  const pinnedColumns: GridPinnedColumnFields = {
    left: [
      GRID_TREE_DATA_GROUPING_FIELD,
      ...(baselineEnabled ? [objectIds[0]] : []),
    ],
  };
  const columns: GridColDef[] = [];
  if (mode === 'unified' && objectIds.length === 2) {
    columns.push({
      field: 'value',
      headerName: 'Value',
      flex: 1,
      display: 'flex',
      sortable: false,
      renderCell: cellParams => {
        const objId = objectIds[1];
        const compareIdx = baselineEnabled
          ? 0
          : Math.max(0, objectIds.indexOf(objId) - 1);
        const compareId = objectIds[compareIdx];
        const compareValue = cellParams.row.values[compareId];
        const compareValueType = cellParams.row.types[compareId];
        const value = cellParams.row.values[objId];
        const valueType = cellParams.row.types[objId];
        const rowChangeType = cellParams.row.changeType;
        return (
          <div className="w-full p-8">
            <CompareGridCell
              path={cellParams.row.path}
              displayType="both"
              value={value}
              valueType={valueType}
              compareValue={compareValue}
              compareValueType={compareValueType}
              rowChangeType={rowChangeType}
            />
          </div>
        );
      },
    });
  } else {
    const versionCols: GridColDef[] = objectIds
      .slice(0, MAX_OBJECT_COLS)
      .map(objId => ({
        field: objId,
        headerName: objId,
        flex: 1,
        display: 'flex',
        width: 500,
        sortable: false,
        valueGetter: (unused: any, row: any) => {
          return row.values[objId];
        },
        renderHeader: (params: any) => {
          if (objectType === 'call') {
            // TODO: Make this a peek drawer link
            return objId;
          }
          const idx = objectIds.indexOf(objId);
          const objVersion = objects[idx];
          const objRef = objectVersionSchemaToRef(
            objVersion as ObjectVersionSchema
          );
          return <SmallRef objRef={objRef} />;
        },
        renderCell: (cellParams: any) => {
          const compareIdx = baselineEnabled
            ? 0
            : Math.max(0, objectIds.indexOf(objId) - 1);
          const compareId = objectIds[compareIdx];
          const compareValue = cellParams.row.values[compareId];
          const compareValueType = cellParams.row.types[compareId];
          const value = cellParams.row.values[objId];
          const valueType = cellParams.row.types[objId];
          const rowChangeType = cellParams.row.changeType;
          return (
            <div className="w-full p-8">
              <CompareGridCell
                path={cellParams.row.path}
                displayType="diff"
                value={value}
                valueType={valueType}
                compareValue={compareValue}
                compareValueType={compareValueType}
                rowChangeType={rowChangeType}
              />
            </div>
          );
        },
      }));
    columns.push(...versionCols);
  }

  const groupingColDef: DataGridProProps['groupingColDef'] = useMemo(
    () => ({
      field: '__group__',
      hideDescendantCount: true,
      width: 300,
      renderHeader: () => {
        // Keep padding in sync with
        // INSET_SPACING (32) + left change indication border (3) - header padding (10)
        return <div className="pl-[25px]">Path</div>;
      },
      renderCell: params => {
        return (
          <CompareGridGroupingCell
            {...params}
            onClick={() => {
              setExpandedIds(eIds => {
                if (eIds.includes(params.row.id)) {
                  return eIds.filter(id => id !== params.row.id);
                }
                return [...eIds, params.row.id];
              });
              addExpandedRefs(params.row.id, params.row.expandableRefs);
            }}
          />
        );
      },
    }),
    [addExpandedRefs, setExpandedIds]
  );

  const getRowId = (row: GridValidRowModel) => {
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

  const getAutoexpandedGroupIds = useCallback(() => {
    const rowIds = apiRef.current.getAllRowIds();
    const filtered = rowIds.filter(rowId => {
      // Only consider group nodes
      const rowNode = apiRef.current.getRowNode(rowId);
      const isGroup = rowNode && rowNode.type === 'group';
      if (!isGroup) {
        return false;
      }

      // To help mitigate page freezes with large objects, limit
      // the depth we are willing to autoexpand.
      if (rowNode.depth >= 3) {
        return false;
      }

      // Don't autoexpand rows with no differences
      const rowData = apiRef.current.getRow(rowId);
      return rowData.changeType !== UNCHANGED;
    });
    return filtered;
  }, [apiRef]);

  // On first render autoexpand some groups
  useEffect(() => {
    setExpandedIds(getAutoexpandedGroupIds());
  }, [setExpandedIds, getAutoexpandedGroupIds]);

  return (
    <StyledDataGrid
      apiRef={apiRef}
      getRowId={getRowId}
      autoHeight
      treeData
      groupingColDef={groupingColDef}
      getTreeDataPath={row => row.path.toStringArray()}
      columns={columns}
      rows={filteredRows}
      isGroupExpandedByDefault={node => {
        return expandedIds.includes(node.id);
      }}
      columnHeaderHeight={38}
      disableColumnReorder={true}
      disableColumnMenu={true}
      getRowHeight={(params: GridRowHeightParams) => {
        return 'auto';
      }}
      rowSelection={false}
      hideFooter
      pinnedColumns={pinnedColumns}
      keepBorders
      sx={{
        '& .MuiDataGrid-cell': {
          alignItems: 'flex-start',
          padding: 0,
        },
      }}
    />
  );
};
