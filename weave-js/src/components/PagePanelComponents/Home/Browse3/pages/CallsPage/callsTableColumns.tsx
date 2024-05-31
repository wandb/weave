/**
 * This file is primarily responsible for exporting `useCallsTableColumns` which is a hook that
 * returns the columns for the calls table.
 */

import {
  GridColDef,
  GridColumnGroup,
  GridColumnGroupingModel,
  GridColumnNode,
} from '@mui/x-data-grid-pro';
import {UserLink} from '@wandb/weave/components/UserLink';
import React, {useCallback, useEffect, useMemo, useState} from 'react';

import {monthRoundedTime} from '../../../../../../common/util/time';
import {isWeaveObjectRef, parseRef} from '../../../../../../react';
import {ErrorBoundary} from '../../../../../ErrorBoundary';
import {Timestamp} from '../../../../../Timestamp';
import {CellValue} from '../../../Browse2/CellValue';
import {CollapseHeader} from '../../../Browse2/CollapseGroupHeader';
import {ExpandHeader} from '../../../Browse2/ExpandHeader';
import {NotApplicable} from '../../../Browse2/NotApplicable';
import {CallLink} from '../common/Links';
import {StatusChip} from '../common/StatusChip';
import {isRef} from '../common/util';
import {TraceCallSchema} from '../wfReactInterface/traceServerClient';
import {
  convertISOToDate,
  traceCallLatencyS,
  traceCallStatusCode,
} from '../wfReactInterface/tsDataModelHooks';
import {opVersionRefOpName} from '../wfReactInterface/utilities';
import {OpVersionIndexText} from './CallsTable';
import {buildTree} from './callsTableBuildTree';
import {
  insertPath,
  isDynamicCallColumn,
  pathToString,
  stringToPath,
} from './callsTableColumnsUtil';
import {WFHighLevelCallFilter} from './callsTableFilter';
import {allOperators} from './callsTableQuery';

export const useCallsTableColumns = (
  entity: string,
  project: string,
  effectiveFilter: WFHighLevelCallFilter,
  tableData: TraceCallSchema[],
  expandedRefCols: Set<string>,
  onCollapse: (col: string) => void,
  onExpand: (col: string) => void,
  columnIsRefExpanded: (col: string) => boolean
) => {
  const [userDefinedColumnWidths, setUserDefinedColumnWidths] = useState<
    Record<string, number>
  >({});

  // Determine which columns have refs to expand. Followup: this might want
  // to be an ever-growing list. Instead, this is recalculated on each page.
  // This is used to determine which columns should be expandable / collapsible.
  const columnsWithRefs = useMemo(() => {
    const refColumns = new Set<string>();
    tableData.forEach(row => {
      Object.keys(row).forEach(key => {
        if (refIsExpandable((row as any)[key])) {
          refColumns.add(key);
        }
      });
    });

    return refColumns;
  }, [tableData]);

  const shouldIgnoreColumn = useCallback(
    (col: string) => {
      const columnsWithRefsList = Array.from(columnsWithRefs);
      // Captures the case where the column has just been expanded.
      for (const refCol of columnsWithRefsList) {
        if (col.startsWith(refCol + '.')) {
          return true;
        }
      }
      return false;
    },
    [columnsWithRefs]
  );

  const allDynamicColumnNames = useAllDynamicColumnNames(
    tableData,
    shouldIgnoreColumn,
    effectiveFilter
  );

  // Determine what sort of view we are looking at based on the filter
  const isSingleOpVersion = useMemo(
    () => effectiveFilter.opVersionRefs?.length === 1,
    [effectiveFilter.opVersionRefs]
  );
  const isSingleOp = useMemo(
    () =>
      effectiveFilter.opVersionRefs?.length === 1 &&
      effectiveFilter.opVersionRefs[0].includes(':*'),
    [effectiveFilter.opVersionRefs]
  );
  const preservePath = useMemo(
    () =>
      effectiveFilter.opVersionRefs?.length === 1 &&
      effectiveFilter.opVersionRefs[0].includes('predict_and_score:'),
    [effectiveFilter.opVersionRefs]
  );

  const columns = useMemo(
    () =>
      buildCallsTableColumns(
        entity,
        project,
        preservePath,
        isSingleOp,
        isSingleOpVersion,
        allDynamicColumnNames,
        expandedRefCols,
        onCollapse,
        columnsWithRefs,
        onExpand,
        columnIsRefExpanded,
        userDefinedColumnWidths
      ),
    [
      entity,
      project,
      preservePath,
      isSingleOp,
      isSingleOpVersion,
      allDynamicColumnNames,
      expandedRefCols,
      onCollapse,
      columnsWithRefs,
      onExpand,
      columnIsRefExpanded,
      userDefinedColumnWidths,
    ]
  );

  return useMemo(() => {
    return {
      columns,
      setUserDefinedColumnWidths,
    };
  }, [columns, setUserDefinedColumnWidths]);
};
function buildCallsTableColumns(
  entity: string,
  project: string,
  preservePath: boolean,
  isSingleOp: boolean,
  isSingleOpVersion: boolean,
  allDynamicColumnNames: string[],
  expandedRefCols: Set<string>,
  onCollapse: (col: string) => void,
  columnsWithRefs: Set<string>,
  onExpand: (col: string) => void,
  columnIsRefExpanded: (col: string) => boolean,
  userDefinedColumnWidths: Record<string, number>
): {
  cols: Array<GridColDef<TraceCallSchema>>;
  colGroupingModel: GridColumnGroupingModel;
} {
  const cols: Array<GridColDef<TraceCallSchema>> = [
    {
      field: 'op_name',
      headerName: 'Trace',
      minWidth: 100,
      // This filter should be controlled by the custom filter
      // in the header
      filterable: false,
      width: 250,
      hideable: false,
      renderCell: rowParams => {
        const op_name = rowParams.row.op_name;
        if (!isRef(op_name)) {
          return op_name;
        }
        return (
          <CallLink
            entityName={entity}
            projectName={project}
            opName={opVersionRefOpName(op_name)}
            callId={rowParams.row.id}
            fullWidth={true}
            preservePath={preservePath}
          />
        );
      },
    },
    ...(isSingleOp && !isSingleOpVersion
      ? [
          {
            field: 'derived.op_version',
            headerName: 'Op Version',
            type: 'number',
            align: 'right' as const,
            disableColumnMenu: true,
            sortable: false,
            filterable: false,
            resizable: false,
            renderCell: (cellParams: any) => (
              <OpVersionIndexText opVersionRef={cellParams.row.op_name} />
            ),
          },
        ]
      : []),
    // {
    //   field: 'run_id',
    //   headerName: 'Run',
    //   disableColumnMenu: true,
    //   renderCell: cellParams => {
    //     return (
    //       <div style={{margin: 'auto'}}>
    //         {cellParams.row.call.runId ?? <NotApplicable />}
    //       </div>
    //     );
    //   },
    // },
    {
      field: 'derived.status_code',
      headerName: 'Status',
      headerAlign: 'center',
      sortable: false,
      disableColumnMenu: true,
      resizable: false,
      // Again, the underlying value is not obvious to the user,
      // so the default free-form filter is likely more confusing than helpful.
      filterable: false,
      // type: 'singleSelect',
      // valueOptions: ['SUCCESS', 'ERROR', 'PENDING'],
      width: 59,
      renderCell: cellParams => {
        return (
          <div style={{margin: 'auto'}}>
            <StatusChip value={traceCallStatusCode(cellParams.row)} iconOnly />
          </div>
        );
      },
    },
  ];

  const tree = buildTree([...allDynamicColumnNames]);
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
      if (expandedRefCols.has(key)) {
        node.renderHeaderGroup = () => {
          return (
            <CollapseHeader
              headerName={key.split('.').slice(-1)[0]}
              field={key}
              onCollapse={onCollapse}
            />
          );
        };
      } else if (columnsWithRefs.has(key)) {
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

  for (const key of allDynamicColumnNames) {
    const col: GridColDef<TraceCallSchema> = {
      flex: 1,
      minWidth: 150,
      field: key,
      // CPR (Tim) - (BackendExpansion): This can be removed once we support backend expansion!
      filterable: !columnIsRefExpanded(key) && !columnsWithRefs.has(key),
      // CPR (Tim) - (BackendExpansion): This can be removed once we support backend expansion!
      sortable: !columnIsRefExpanded(key) && !columnsWithRefs.has(key),
      filterOperators: allOperators,
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
      renderCell: cellParams => {
        const val = (cellParams.row as any)[key];
        if (val === undefined) {
          return <NotApplicable />;
        }
        return (
          <ErrorBoundary>
            <CellValue value={val} />
          </ErrorBoundary>
        );
      },
    };

    if (groupIds.has(key)) {
      col.renderHeader = () => {
        return <></>;
      };
    } else if (expandedRefCols.has(key)) {
      col.renderHeader = () => {
        return (
          <CollapseHeader
            headerName={key.split('.').slice(-1)[0]}
            field={key}
            onCollapse={onCollapse}
          />
        );
      };
    } else if (columnsWithRefs.has(key)) {
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

  cols.push({
    field: 'wb_user_id',
    headerName: 'User',
    headerAlign: 'center',
    width: 50,
    // Might be confusing to enable as-is, because the user sees name /
    // email but the underlying data is userId.
    filterable: false,
    align: 'center',
    sortable: false,
    resizable: false,
    disableColumnMenu: true,
    renderCell: cellParams => {
      const userId = cellParams.row.wb_user_id;
      if (userId == null) {
        return null;
      }
      return <UserLink username={userId} />;
    },
  });

  const startedAtCol: GridColDef<TraceCallSchema> = {
    field: 'started_at',
    headerName: 'Called',
    // Should have custom timestamp filter here.
    filterOperators: allOperators.filter(o => o.value.startsWith('(date)')),
    sortable: true,
    width: 100,
    minWidth: 100,
    maxWidth: 100,
    renderCell: cellParams => {
      return (
        <Timestamp
          value={convertISOToDate(cellParams.row.started_at).getTime() / 1000}
          format="relative"
        />
      );
    },
  };
  cols.push(startedAtCol);

  cols.push({
    field: 'derived.latency',
    headerName: 'Latency',
    width: 100,
    minWidth: 100,
    maxWidth: 100,
    // Should probably have a custom filter here.
    filterable: false,
    sortable: false,
    renderCell: cellParams => {
      if (traceCallStatusCode(cellParams.row) === 'UNSET') {
        // Call is still in progress, latency will be 0.
        // Displaying nothing seems preferable to being misleading.
        return null;
      }
      return monthRoundedTime(traceCallLatencyS(cellParams.row));
    },
  });

  cols.forEach(col => {
    if (col.field in userDefinedColumnWidths) {
      col.width = userDefinedColumnWidths[col.field];
      col.flex = 0;
    }
  });

  return {cols, colGroupingModel: groupingModel};
}
/**
 * This function maintains an ever-growing list of dynamic column names. It is used to
 * determine which dynamic columns (e.g. attributes, inputs, outputs) are present in the
 * table data. If we page/filter/sort we don't want to lose the columns that were present
 * in the previous data.
 */
const useAllDynamicColumnNames = (
  tableData: TraceCallSchema[],
  shouldIgnoreColumn: (col: string) => boolean,
  resetDep: any
) => {
  // TODO: Maintain user-defined order
  const [allDynamicColumnNames, setAllDynamicColumnNames] = useState<string[]>(
    []
  );

  useEffect(() => {
    setAllDynamicColumnNames(last => {
      let nextAsPaths = last
        .filter(c => !shouldIgnoreColumn(c))
        .map(stringToPath);
      tableData.forEach(row => {
        Object.keys(row).forEach(key => {
          const keyAsPath = stringToPath(key);
          if (isDynamicCallColumn(keyAsPath)) {
            nextAsPaths = insertPath(nextAsPaths, stringToPath(key));
          }
        });
      });

      return nextAsPaths.map(pathToString);
    });
  }, [shouldIgnoreColumn, tableData]);

  useEffect(() => {
    // Here, we reset the dynamic column names when the filter changes.
    // Both branches of the if statement are the same. I just wanted to
    // ensure that the `resetDep` is included in the dependency array.
    // Perhaps there is a better way to do this?
    if (resetDep) {
      setAllDynamicColumnNames([]);
    } else {
      setAllDynamicColumnNames([]);
    }
  }, [resetDep]);

  return allDynamicColumnNames;
};

const refIsExpandable = (ref: string): boolean => {
  if (!isRef(ref)) {
    return false;
  }
  const parsed = parseRef(ref);
  if (isWeaveObjectRef(parsed)) {
    return (
      parsed.weaveKind === 'object' ||
      // parsed.weaveKind === 'op' ||
      (parsed.weaveKind === 'table' &&
        parsed.artifactRefExtra != null &&
        parsed.artifactRefExtra.length > 0)
    );
  }
  return false;
};
