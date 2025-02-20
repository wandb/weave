/**
 * This file is primarily responsible for exporting `useCallsTableColumns` which is a hook that
 * returns the columns for the calls table.
 */

import {
  GridColDef,
  GridColumnGroupingModel,
  GridRenderCellParams,
} from '@mui/x-data-grid-pro';
import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import {Tooltip} from '@wandb/weave/components/Tooltip';
import {UserLink} from '@wandb/weave/components/UserLink';
import React, {useCallback, useEffect, useMemo, useState} from 'react';

import {TEAL_600} from '../../../../../../common/css/color.styles';
import {monthRoundedTime} from '../../../../../../common/util/time';
import {isWeaveObjectRef, parseRef} from '../../../../../../react';
import {makeRefCall} from '../../../../../../util/refs';
import {Timestamp} from '../../../../../Timestamp';
import {CellValue} from '../../../Browse2/CellValue';
import {CellValueString} from '../../../Browse2/CellValueString';
import {
  convertFeedbackFieldToBackendFilter,
  parseFeedbackType,
} from '../../feedback/HumanFeedback/tsHumanFeedback';
import {
  convertScorerFeedbackFieldToBackendFilter,
  parseScorerFeedbackField,
  RUNNABLE_FEEDBACK_IN_SUMMARY_PREFIX,
  RUNNABLE_FEEDBACK_OUTPUT_PART,
} from '../../feedback/HumanFeedback/tsScorerFeedback';
import {Reactions} from '../../feedback/Reactions';
import {CellFilterWrapper, OnAddFilter} from '../../filters/CellFilterWrapper';
import {isWeaveRef} from '../../filters/common';
import {
  getCostsFromCellParams,
  getTokensFromCellParams,
} from '../CallPage/cost';
import {isEvaluateOp} from '../common/heuristics';
import {CallLink} from '../common/Links';
import {StatusChip} from '../common/StatusChip';
import {buildDynamicColumns} from '../common/tabularListViews/columnBuilder';
import {TraceCallSchema} from '../wfReactInterface/traceServerClientTypes';
import {
  convertISOToDate,
  traceCallLatencyS,
  traceCallStatusCode,
} from '../wfReactInterface/tsDataModelHooks';
import {opVersionRefOpName} from '../wfReactInterface/utilities';
import {
  insertPath,
  isDynamicCallColumn,
  pathToString,
  stringToPath,
} from './callsTableColumnsUtil';
import {WFHighLevelCallFilter} from './callsTableFilter';
import {OpVersionIndexText} from './OpVersionIndexText';

const HIDDEN_DYNAMIC_COLUMN_PREFIXES = [
  'summary.usage',
  'summary.weave',
  'feedback',
];

export const useCallsTableColumns = (
  entity: string,
  project: string,
  effectiveFilter: WFHighLevelCallFilter,
  tableData: TraceCallSchema[],
  expandedRefCols: Set<string>,
  onCollapse: (col: string) => void,
  onExpand: (col: string) => void,
  columnIsRefExpanded: (col: string) => boolean,
  allowedColumnPatterns?: string[],
  onAddFilter?: OnAddFilter,
  costsLoading: boolean = false
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
        userDefinedColumnWidths,
        allowedColumnPatterns,
        onAddFilter,
        costsLoading
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
      allowedColumnPatterns,
      onAddFilter,
      costsLoading,
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
  userDefinedColumnWidths: Record<string, number>,
  allowedColumnPatterns?: string[],
  onAddFilter?: OnAddFilter,
  costsLoading: boolean = false
): {
  cols: Array<GridColDef<TraceCallSchema>>;
  colGroupingModel: GridColumnGroupingModel;
} {
  // Filters summary.usage. because we add a derived column for tokens and cost
  // Sort attributes after inputs and outputs.
  const filteredDynamicColumnNames = allDynamicColumnNames
    .filter(
      c => !HIDDEN_DYNAMIC_COLUMN_PREFIXES.some(p => c.startsWith(p + '.'))
    )
    .sort((a, b) => {
      const prefixes = ['inputs.', 'output.', 'attributes.'];
      const aPrefix =
        a === 'output' ? 'output.' : prefixes.find(p => a.startsWith(p)) ?? '';
      const bPrefix =
        b === 'output' ? 'output.' : prefixes.find(p => b.startsWith(p)) ?? '';
      if (aPrefix !== bPrefix) {
        return prefixes.indexOf(aPrefix) - prefixes.indexOf(bPrefix);
      }
      return a.localeCompare(b);
    });

  const cols: Array<GridColDef<TraceCallSchema>> = [
    {
      field: 'op_name',
      headerName: 'Trace',
      minWidth: 100,
      width: 250,
      hideable: false,
      display: 'flex',
      valueGetter: (unused: any, row: any) => {
        const op_name = row.op_name;
        if (!isWeaveRef(op_name)) {
          return op_name;
        }
        return opVersionRefOpName(op_name);
      },
      renderCell: rowParams => {
        const opName =
          rowParams.row.display_name ??
          opVersionRefOpName(rowParams.row.op_name) ??
          rowParams.row.op_name;
        const isEval = isEvaluateOp(opVersionRefOpName(rowParams.row.op_name));
        return (
          <CallLink
            entityName={entity}
            projectName={project}
            opName={opName}
            callId={rowParams.row.id}
            fullWidth={true}
            preservePath={preservePath}
            color={TEAL_600}
            isEval={isEval}
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
            type: 'number' as const,
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
      field: 'status',
      headerName: 'Status',
      headerAlign: 'center',
      sortable: false,
      // disableColumnMenu: true,
      resizable: false,
      width: 59,
      display: 'flex',
      valueGetter: (unused: any, row: any) => {
        return traceCallStatusCode(row);
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
    row => {
      const [rowEntity, rowProject] = row.project_id.split('/');
      return {entity: rowEntity, project: rowProject};
    },
    (row, key) => (row as any)[key],
    key => expandedRefCols.has(key),
    key => columnsWithRefs.has(key),
    onCollapse,
    onExpand,
    // TODO (Tim) - (BackendExpansion): This can be removed once we support backend expansion!
    key => !columnIsRefExpanded(key) && !columnsWithRefs.has(key),
    (key, operator, value, rowId) => {
      onAddFilter?.(key, operator, value, rowId);
    }
  );
  cols.push(...newCols);

  // Create special feedback columns with grouping model
  const annotationColNames = allDynamicColumnNames.filter(
    c =>
      c.startsWith('summary.weave.feedback.wandb.annotation') &&
      c.endsWith('payload.value')
  );
  if (annotationColNames.length > 0) {
    // Add feedback group to grouping model
    groupingModel.push({
      groupId: 'feedback',
      headerName: 'Annotations',
      children: annotationColNames.map(col => ({
        field: convertFeedbackFieldToBackendFilter(col),
      })),
    });

    // Add feedback columns
    const annotationColumns: Array<GridColDef<TraceCallSchema>> =
      annotationColNames.map(c => {
        const parsed = parseFeedbackType(c);
        return {
          field: convertFeedbackFieldToBackendFilter(c),
          headerName: parsed ? parsed.displayName : `${c}`,
          width: 150,
          renderHeader: () => {
            return <div>{parsed ? parsed.userDefinedType : c}</div>;
          },
          valueGetter: (unused: any, row: any) => {
            return row[c];
          },
          renderCell: (params: GridRenderCellParams<TraceCallSchema>) => {
            if (typeof params.value === 'boolean') {
              return <div>{params.value ? 'true' : 'false'}</div>;
            }
            if (typeof params.value === 'string') {
              return <CellValueString value={params.value} />;
            }
            return <div>{params.value}</div>;
          },
        };
      });
    cols.push(...annotationColumns);
  }

  const scoreColNames = allDynamicColumnNames.filter(
    c =>
      c.startsWith(RUNNABLE_FEEDBACK_IN_SUMMARY_PREFIX) &&
      c.includes(RUNNABLE_FEEDBACK_OUTPUT_PART)
  );
  if (scoreColNames.length > 0) {
    // Group scores by scorer name
    const scorerGroups = new Map<string, string[]>();
    scoreColNames.forEach(colName => {
      const parsed = parseScorerFeedbackField(colName);
      if (parsed) {
        const scorerName = parsed.scorerName;
        if (!scorerGroups.has(scorerName)) {
          scorerGroups.set(scorerName, []);
        }
        scorerGroups.get(scorerName)?.push(colName);
      }
    });

    // Create scorer groups in the grouping model for each scorer
    const scoreGroup = {
      groupId: 'scores',
      headerName: 'Scores',
      children: Array.from(scorerGroups.entries()).map(([scorerName, _]) => ({
        groupId: `scores.${scorerName}`,
        headerName: scorerName,
        children: [] as any[],
      })),
    };
    groupingModel.push(scoreGroup);

    // Create columns for each scorer's fields
    const scoreColumns: Array<GridColDef<TraceCallSchema>> = [];
    scorerGroups.forEach((colNames, scorerName) => {
      const scorerGroup = scoreGroup.children.find(
        g => g.groupId === `scores.${scorerName}`
      );

      colNames.forEach(colName => {
        const parsed = parseScorerFeedbackField(colName);
        const field = convertScorerFeedbackFieldToBackendFilter(colName);

        // Add to scorer's group
        scorerGroup?.children.push({field});
        // remove the leading dot from the score path
        const headerName = (parsed?.scorePath || colName).replace(/^\./, '');

        scoreColumns.push({
          field,
          headerName,
          width: 150,
          renderHeader: () => {
            return <div>{headerName}</div>;
          },
          valueGetter: (unused: any, row: any) => {
            return row[colName];
          },
          renderCell: (params: GridRenderCellParams<TraceCallSchema>) => {
            return (
              <CellFilterWrapper
                onAddFilter={onAddFilter}
                field={field}
                rowId={params.id.toString()}
                operation={null}
                value={params.value}>
                <CellValue value={params.value} />
              </CellFilterWrapper>
            );
          },
        });
      });
    });
    cols.push(...scoreColumns);
  }

  cols.push({
    field: 'wb_user_id',
    headerName: 'User',
    headerAlign: 'center',
    width: 50,
    align: 'center',
    sortable: false,
    resizable: false,
    display: 'flex',
    renderCell: cellParams => {
      const userId = cellParams.row.wb_user_id;
      if (userId == null) {
        return null;
      }
      return (
        <CellFilterWrapper
          onAddFilter={onAddFilter}
          field="wb_user_id"
          rowId={cellParams.id.toString()}
          operation="(string): equals"
          value={userId}>
          <UserLink userId={userId} />
        </CellFilterWrapper>
      );
    },
  });

  const startedAtCol: GridColDef<TraceCallSchema> = {
    field: 'started_at',
    headerName: 'Called',
    sortable: true,
    sortingOrder: ['desc', 'asc'],
    width: 100,
    minWidth: 100,
    maxWidth: 100,
    renderCell: cellParams => {
      // TODO: A better filter might be to be on the same day?
      const date = convertISOToDate(cellParams.row.started_at);
      const filterDate = new Date(date);
      filterDate.setSeconds(0, 0);
      const filterValue = filterDate.toISOString();
      const value = date.getTime() / 1000;
      return (
        <CellFilterWrapper
          onAddFilter={onAddFilter}
          field="started_at"
          rowId={cellParams.id.toString()}
          operation="(date): after"
          value={filterValue}>
          <Timestamp value={value} format="relative" />
        </CellFilterWrapper>
      );
    },
  };
  cols.push(startedAtCol);

  cols.push({
    field: 'tokens',
    headerName: 'Tokens',
    width: 100,
    minWidth: 100,
    maxWidth: 100,
    align: 'right',
    headerAlign: 'right',
    // Should probably have a custom filter here.
    filterable: false,
    sortable: false,
    valueGetter: (unused: any, row: any) => {
      const {tokensNum} = getTokensFromCellParams(row);
      return tokensNum;
    },
    renderCell: cellParams => {
      const {tokens, tokenToolTipContent} = getTokensFromCellParams(
        cellParams.row
      );
      return (
        <Tooltip trigger={<div>{tokens}</div>} content={tokenToolTipContent} />
      );
    },
  });
  cols.push({
    field: 'cost',
    headerName: 'Cost',
    width: 100,
    minWidth: 100,
    maxWidth: 100,
    align: 'right',
    headerAlign: 'right',
    // Should probably have a custom filter here.
    filterable: false,
    sortable: false,
    valueGetter: (unused: any, row: any) => {
      const {costNum} = getCostsFromCellParams(row);
      return costNum;
    },
    renderCell: cellParams => {
      if (costsLoading) {
        return <LoadingDots />;
      }
      const {cost, costToolTipContent} = getCostsFromCellParams(cellParams.row);
      return (
        <Tooltip trigger={<div>{cost}</div>} content={costToolTipContent} />
      );
    },
  });

  cols.push({
    field: 'latency',
    headerName: 'Latency',
    width: 100,
    minWidth: 100,
    maxWidth: 100,
    // Should probably have a custom filter here.
    filterable: false,
    sortable: false,
    valueGetter: (unused: any, row: any) => {
      if (traceCallStatusCode(row) === 'UNSET') {
        // Call is still in progress, latency will be 0.
        // Displaying nothing seems preferable to being misleading.
        return null;
      }
      return traceCallLatencyS(row);
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

  // TODO: It would be better to build up the cols rather than throwing away
  //       some at the end, but making simpler change for now.
  let orderedCols = cols;
  if (allowedColumnPatterns !== undefined) {
    orderedCols = allowedColumnPatterns.flatMap(shownCol => {
      if (shownCol.includes('*')) {
        const regex = new RegExp('^' + shownCol.replace('*', '.*') + '$');
        return cols.filter(col => regex.test(col.field));
      } else {
        return cols.filter(col => col.field === shownCol);
      }
    });
  }

  return {cols: orderedCols, colGroupingModel: groupingModel};
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
  if (!isWeaveRef(ref)) {
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
