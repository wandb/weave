/**
 * This file is primarily responsible for exporting `useCallsTableColumns` which is a hook that
 * returns the columns for the calls table.
 */

import {
  GridColDef,
  GridColumnGroupingModel,
  GridRenderCellParams,
} from '@mui/x-data-grid-pro';
import {Tooltip} from '@wandb/weave/components/Tooltip';
import {UserLink} from '@wandb/weave/components/UserLink';
import React, {useCallback, useEffect, useMemo, useState} from 'react';

import {monthRoundedTime} from '../../../../../../common/util/time';
import {isWeaveObjectRef, parseRef} from '../../../../../../react';
import {makeRefCall} from '../../../../../../util/refs';
import {Timestamp} from '../../../../../Timestamp';
import {Reactions} from '../../feedback/Reactions';
import {
  getTokensAndCostFromUsage,
  getUsageFromCellParams,
} from '../CallPage/TraceUsageStats';
import {CallLink} from '../common/Links';
import {StatusChip} from '../common/StatusChip';
import {buildDynamicColumns} from '../common/tabularListViews/columnBuilder';
import {allOperators} from '../common/tabularListViews/operators';
import {isRef} from '../common/util';
import {TraceCallSchema} from '../wfReactInterface/traceServerClientTypes';
import {
  convertISOToDate,
  traceCallLatencyS,
  traceCallStatusCode,
} from '../wfReactInterface/tsDataModelHooks';
import {opVersionRefOpName} from '../wfReactInterface/utilities';
import {OpVersionIndexText} from './CallsTable';
import {
  insertPath,
  isDynamicCallColumn,
  pathToString,
  stringToPath,
} from './callsTableColumnsUtil';
import {WFHighLevelCallFilter} from './callsTableFilter';

const HIDDEN_DYNAMIC_COLUMN_PREFIXES = ['summary.usage'];

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
  // Filters summary.usage. because we add a derived column for tokens and cost
  const filteredDynamicColumnNames = allDynamicColumnNames.filter(
    c => !HIDDEN_DYNAMIC_COLUMN_PREFIXES.some(p => c.startsWith(p + '.'))
  );

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
      valueGetter: rowParams => {
        const op_name = rowParams.row.op_name;
        if (!isRef(op_name)) {
          return op_name;
        }
        return opVersionRefOpName(op_name);
      },
      renderCell: rowParams => {
        const op_name = rowParams.row.op_name;
        if (!isRef(op_name)) {
          return op_name;
        }
        return (
          <CallLink
            entityName={entity}
            projectName={project}
            opName={rowParams.row.display_name ?? opVersionRefOpName(op_name)}
            callId={rowParams.row.id}
            fullWidth={true}
            preservePath={preservePath}
          />
        );
      },
    },
    {
      field: 'feedback',
      headerName: 'Feedback',
      width: 150,
      sortable: false,
      filterable: false,
      renderCell: (rowParams: GridRenderCellParams) => {
        const rowIndex = rowParams.api.getRowIndexRelativeToVisibleRows(
          rowParams.id
        );
        const callId = rowParams.row.id;
        const weaveRef = makeRefCall(entity, project, callId);
        return (
          <Reactions
            weaveRef={weaveRef}
            forceVisible={rowIndex === 0}
            twWrapperStyles={{
              width: '100%',
              height: '100%',
            }}
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
      field: 'summary.weave.status',
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
      valueGetter: cellParams => {
        return traceCallStatusCode(cellParams.row);
      },
      renderCell: cellParams => {
        return (
          <div style={{margin: 'auto'}}>
            <StatusChip value={traceCallStatusCode(cellParams.row)} iconOnly />
          </div>
        );
      },
    },
  ];

  const {cols: newCols, groupingModel} = buildDynamicColumns<TraceCallSchema>(
    filteredDynamicColumnNames,
    (row, key) => (row as any)[key],
    key => expandedRefCols.has(key),
    key => columnsWithRefs.has(key),
    onCollapse,
    onExpand,
    // TODO (Tim) - (BackendExpansion): This can be removed once we support backend expansion!
    key => !columnIsRefExpanded(key) && !columnsWithRefs.has(key),
    // TODO (Tim) - (BackendExpansion): This can be removed once we support backend expansion!
    key => !columnIsRefExpanded(key) && !columnsWithRefs.has(key)
  );
  cols.push(...newCols);

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
    renderCell: cellParams => {
      const userId = cellParams.row.wb_user_id;
      if (userId == null) {
        return null;
      }
      return <UserLink userId={userId} />;
    },
  });

  const startedAtCol: GridColDef<TraceCallSchema> = {
    field: 'started_at',
    headerName: 'Called',
    // Should have custom timestamp filter here.
    filterOperators: allOperators.filter(o => o.value.startsWith('(date)')),
    sortable: true,
    sortingOrder: ['desc', 'asc'],
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
    field: 'summary.weave.tokens',
    headerName: 'Tokens',
    width: 100,
    minWidth: 100,
    maxWidth: 100,
    // Should probably have a custom filter here.
    filterable: false,
    sortable: false,
    valueGetter: cellParams => {
      const usage = getUsageFromCellParams(cellParams.row);
      const {tokensNum} = getTokensAndCostFromUsage(usage);
      return tokensNum;
    },
    renderCell: cellParams => {
      const usage = getUsageFromCellParams(cellParams.row);
      const {tokens, tokenToolTip} = getTokensAndCostFromUsage(usage);
      return <Tooltip trigger={<div>{tokens}</div>} content={tokenToolTip} />;
    },
  });

  cols.push({
    field: 'summary.weave.cost',
    headerName: 'Cost',
    width: 100,
    minWidth: 100,
    maxWidth: 100,
    // Should probably have a custom filter here.
    filterable: false,
    sortable: false,
    valueGetter: cellParams => {
      const usage = getUsageFromCellParams(cellParams.row);
      const {costNum} = getTokensAndCostFromUsage(usage);
      return costNum;
    },
    renderCell: cellParams => {
      const usage = getUsageFromCellParams(cellParams.row);
      const {cost, costToolTip} = getTokensAndCostFromUsage(usage);
      return <Tooltip trigger={<div>{cost}</div>} content={costToolTip} />;
    },
  });

  cols.push({
    field: 'summary.weave.latency',
    headerName: 'Latency',
    width: 100,
    minWidth: 100,
    maxWidth: 100,
    // Should probably have a custom filter here.
    filterable: false,
    sortable: false,
    valueGetter: cellParams => {
      if (traceCallStatusCode(cellParams.row) === 'UNSET') {
        // Call is still in progress, latency will be 0.
        // Displaying nothing seems preferable to being misleading.
        return null;
      }
      return traceCallLatencyS(cellParams.row);
    },
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
