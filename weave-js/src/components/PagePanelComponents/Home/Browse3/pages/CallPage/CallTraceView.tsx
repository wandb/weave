import {
  DataGridPro,
  DataGridProProps,
  useGridApiRef,
} from '@mui/x-data-grid-pro';
import _ from 'lodash';
import React, {FC, useCallback, useEffect, useMemo, useState} from 'react';
import {useHistory} from 'react-router-dom';
import styled from 'styled-components';

import * as userEvents from '../../../../../../integrations/analytics/userEvents';
import {ErrorBoundary} from '../../../../../ErrorBoundary';
import {useWeaveflowCurrentRouteContext} from '../../context';
import {CallStatusType} from '../common/StatusChip';
import {useWFHooks} from '../wfReactInterface/context';
import {
  CallFilter,
  CallSchema,
} from '../wfReactInterface/wfDataModelHooksInterface';
import {addCostsToCallResults} from './cost';
import {CustomGridTreeDataGroupingCell} from './CustomGridTreeDataGroupingCell';
import {scorePathSimilarity, updatePath} from './pathPreservation';

const CallTrace = styled.div`
  overflow: auto;
  height: 100%;
`;
CallTrace.displayName = 'S.CallTrace';

const MAX_CHILDREN_TO_SHOW = 50;

export const CallTraceView: FC<{
  call: CallSchema;
  selectedCall: CallSchema;
  rows: Row[];
  forcedExpandKeys: Set<string>;
  path?: string;
  costLoading: boolean;
}> = ({call, selectedCall, rows, forcedExpandKeys, path, costLoading}) => {
  const apiRef = useGridApiRef();
  const history = useHistory();
  const currentRouter = useWeaveflowCurrentRouteContext();
  const [expandKeys, setExpandKeys] = useState(forcedExpandKeys);
  useEffect(() => {
    setExpandKeys(curr => new Set([...curr, ...forcedExpandKeys]));
  }, [forcedExpandKeys]);

  // Informs DataGridPro where to lookup the hierarchy of a given row.
  const getTreeDataPath: DataGridProProps['getTreeDataPath'] = useCallback(
    row => row.hierarchy,
    []
  );

  // Informs DataGridPro how to render the grouping cell (this is where
  // the tree structure is rendered)
  const groupingColDef: DataGridProProps['groupingColDef'] = useMemo(
    () => ({
      headerName: 'Call Tree',
      headerAlign: 'center',
      flex: 1,
      display: 'flex',
      renderCell: params => (
        <CustomGridTreeDataGroupingCell
          {...params}
          costLoading={costLoading}
          onClick={event => {
            setExpandKeys(curr => {
              if (curr.has(params.row.id)) {
                const newSet = new Set(curr);
                newSet.delete(params.row.id);
                return newSet;
              } else {
                return new Set([...curr, params.row.id]);
              }
            });
          }}
        />
      ),
    }),
    [costLoading]
  );

  const [suppressScroll, setSuppressScroll] = useState(false);

  // Informs DataGridPro what to do when a row is clicked - in this case
  // use the current router to navigate to the call page for the clicked
  // call. Effectively this looks like expanding the clicked call.
  const onRowClick: DataGridProProps['onRowClick'] = useCallback(
    params => {
      if (!params.row.call) {
        return;
      }
      const rowCall = params.row.call as CallSchema;
      setSuppressScroll(true);
      if (params.row.isParentRow) {
        // Allow navigating up the tree
        history.push(
          currentRouter.callUIUrl(
            rowCall.entity,
            rowCall.project,
            '',
            rowCall.callId,
            '',
            true
          )
        );
      } else {
        // Browse within selected call
        history.replace(
          currentRouter.callUIUrl(
            call.entity,
            call.project,
            call.traceId,
            call.callId,
            params.row.path,
            true
          )
        );
      }
      userEvents.callTreeCellClicked({
        callId: rowCall.callId,
        entity: rowCall.entity,
        project: rowCall.project,
        traceId: rowCall.traceId,
        path: params.row.path,
        isParentRow: params.row.isParentRow,
        heirarchyDepth: params.row.hierarchy.length,
      });
    },
    [
      call.callId,
      call.entity,
      call.project,
      call.traceId,
      currentRouter,
      history,
    ]
  );
  const onRowDoubleClick: DataGridProProps['onRowDoubleClick'] = useCallback(
    params => {
      if (!params.row.call) {
        return;
      }
      const rowCall = params.row.call as CallSchema;
      history.push(
        currentRouter.callUIUrl(
          rowCall.entity,
          rowCall.project,
          '',
          rowCall.callId
        )
      );
    },
    [currentRouter, history]
  );

  // Informs DataGridPro which groups to expand by default. In this case,
  // we expand the groups for the current call.
  const isGroupExpandedByDefault: DataGridProProps['isGroupExpandedByDefault'] =
    useCallback(
      node => {
        const result = expandKeys.has(
          node.groupingKey?.toString() ?? 'INVALID'
        );
        return result;
      },
      [expandKeys]
    );

  // Informs DataGridPro how to style the rows. In this case, we highlight
  // the current call.
  const callClass = `.callId-${selectedCall.callId}`;
  const getRowClassName: DataGridProProps['getRowClassName'] = useCallback(
    params => {
      if (!params.row.call) {
        // Special case for the sibling count row
        return '';
      }
      const rowCall = params.row.call as CallSchema;
      return `callId-${rowCall.callId}`;
    },
    []
  );

  // Informs DataGridPro how to style the table. In this case, we remove
  // the borders between the cells.
  const sx: DataGridProProps['sx'] = useMemo(
    () => ({
      border: 0,
      fontFamily: 'Source Sans Pro',
      '&>.MuiDataGrid-main': {
        '& div div div div >.MuiDataGrid-cell': {
          borderTop: 'none',
        },
        '& div div div div >.MuiDataGrid-cell:focus': {
          outline: 'none',
        },
      },
      '& .MuiDataGrid-topContainer': {
        display: 'none',
      },
      '& .MuiDataGrid-columnHeaders': {
        borderBottom: 'none',
      },
      '& .MuiDataGrid-filler': {
        display: 'none',
      },
      [callClass]: {
        backgroundColor: '#a9edf252',
      },
    }),
    [callClass]
  );

  // Scroll selected call into view
  const callId = call.callId;
  useEffect(() => {
    // The setTimeout here is a hack; without it scrollToIndexes will throw an error
    // because virtualScrollerRef.current inside the grid is undefined.
    // See https://github.com/mui/mui-x/issues/6411#issuecomment-1271556519
    const t = setTimeout(() => {
      if (suppressScroll) {
        setSuppressScroll(false);
        return;
      }
      const rowElement = apiRef.current.getRowElement(callId);
      if (rowElement) {
        rowElement.scrollIntoView();
      } else {
        // Grid is virtualized, use api to make row visible.
        // Unfortunately, MUI doesn't offer something like alignToTop
        const rowIndex =
          apiRef.current.getRowIndexRelativeToVisibleRows(callId);
        apiRef.current.scrollToIndexes({rowIndex});
      }
      setSuppressScroll(false);
    }, 0);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiRef, callId]);

  // This is used because when we first load the trace view in a drawer, the animation cant handle all the rows
  // so we delay for the first render
  const [animationBuffer, setAnimationBuffer] = useState(true);
  useEffect(() => {
    setTimeout(() => {
      setAnimationBuffer(false);
    }, 0);
  }, []);

  return (
    <CallTrace>
      <ErrorBoundary>
        <DataGridPro
          apiRef={apiRef}
          rowHeight={64}
          columnHeaderHeight={0}
          treeData
          loading={animationBuffer}
          onRowClick={onRowClick}
          onRowDoubleClick={onRowDoubleClick}
          rows={animationBuffer ? [] : rows}
          columns={[]}
          getTreeDataPath={getTreeDataPath}
          groupingColDef={groupingColDef}
          isGroupExpandedByDefault={isGroupExpandedByDefault}
          getRowClassName={getRowClassName}
          hideFooter
          rowSelection={false}
          sx={sx}
        />
      </ErrorBoundary>
    </CallTrace>
  );
};

const RE_TRAILING_INT = /\d+$/;

// Sorting evaluation calls by dataset row.
// Because of async they may have been processed in a different order.
const getCallSortExampleRow = (call: CallSchema): number => {
  const {example} = call.rawSpan.inputs;
  if (example) {
    // If not a string, we don't know how to sort.
    if (!_.isString(example)) {
      return Number.POSITIVE_INFINITY;
    }
    const match = example.match(RE_TRAILING_INT);
    if (match) {
      return parseInt(match[0], 10);
    }
  }
  return Number.POSITIVE_INFINITY;
};
const getCallSortStartTime = (call: CallSchema): number => {
  return call.rawSpan.start_time_ms;
};

/**
 * Returns the flattened trace tree for a given call. Specifically,
 * it will find the trace root for a call, then find all the descendants
 * of the root, filtering by selected call. The flattened order is depth-first,
 * so that when listed in a table, the children of each call will be listed
 * immediately after the parent call. The structure of the returned rows conforms
 * to `GridValidRowModel`, but is specifically:
 * {
 *  id: string;
 *  call: WFCall;
 *  status: CallStatusType;
 *  hierarchy: string[];
 *  isTraceRootCall: boolean;
 *  isParentRow?: boolean;
 * }
 * where `hierarchy` is the list of call IDs from the root to the current.
 * isTraceRootCall indicates whether the row is the root call for the trace.
 * isParentRow indicates whether the row indicates the parent of the selected call.
 *
 * Furthermore, the `expandKeys` set contains the call IDs of all the calls
 * from the root to the current call, so that the tree can be expanded to
 * show the current call.
 */
type CallRow = {
  id: string;
  call: CallSchema;
  status: CallStatusType;
  hierarchy: string[];
  path: string;
  isTraceRootCall: boolean;
  isParentRow?: boolean;
};
type SiblingCountRow = {
  id: 'HIDDEN_SIBLING_COUNT';
  count: number;
  hierarchy: string[];
};
type HiddenChildrenCountRow = {
  id: 'HIDDEN_CHILDREN_COUNT';
  count: number;
  hierarchy: string[];
  parentId: string;
};
type Row = CallRow | SiblingCountRow | HiddenChildrenCountRow;

type CallMap = Record<string, CallSchema>;
type ChildCallLookup = Record<string, string[]>;

const getIndexWithinSameNameSiblings = (
  call: CallSchema,
  traceCallMap: CallMap,
  childCallLookup: ChildCallLookup
) => {
  const sameParentIds = call.parentId
    ? childCallLookup[call.parentId] ?? []
    : [];
  const sameParentCalls = _.sortBy(
    sameParentIds.map(c => traceCallMap[c]).filter(c => c),
    [getCallSortExampleRow, getCallSortStartTime]
  );
  const indexWithinSameNameSiblings =
    sameParentCalls.length > 0
      ? sameParentCalls
          .filter(c => c.spanName === call.spanName)
          .findIndex(c => c.callId === call.callId)
      : -1;
  return indexWithinSameNameSiblings;
};

export const useCallFlattenedTraceTree = (
  call: CallSchema,
  selectedPath: string | null
) => {
  const {useCalls} = useWFHooks();
  const columns = useMemo(
    () => [
      'parent_id',
      'started_at',
      'ended_at',
      'display_name',
      'summary',
      'exception',
    ],
    []
  );
  const traceCalls = useCalls(
    call.entity,
    call.project,
    {
      traceId: call.traceId,
    },
    undefined,
    undefined,
    undefined,
    undefined,
    columns,
    undefined,
    {refetchOnDelete: true}
  );

  const traceCallsResult = useMemo(() => {
    const result = traceCalls.result ?? [];
    return result;
  }, [traceCalls.result]);

  const costFilter: CallFilter = useMemo(
    () => ({
      callIds:
        traceCallsResult && traceCallsResult.length < 1000
          ? traceCallsResult.map(c => c.traceCall?.id || '')
          : undefined,
      traceId: call.traceId,
    }),
    [traceCallsResult, call.traceId]
  );

  const costCols = useMemo(() => ['id'], []);
  const costs = useCalls(
    call.entity,
    call.project,
    costFilter,
    undefined,
    undefined,
    undefined,
    undefined,
    costCols,
    undefined,
    {
      skip: traceCalls.loading,
      includeCosts: true,
    }
  );

  const costResult = useMemo(() => {
    return addCostsToCallResults(traceCallsResult, costs.result ?? []);
  }, [costs.result, traceCallsResult]);

  const traceCallMap = useMemo(() => {
    const result = costResult.length > 0 ? costResult : traceCallsResult;
    return _.keyBy(result, 'callId');
  }, [costResult, traceCallsResult]);

  const childCallLookup = useMemo(() => {
    const lookup: Record<string, string[]> = {};
    for (const c of traceCallsResult) {
      if (c.parentId) {
        if (!lookup[c.parentId]) {
          lookup[c.parentId] = [];
        }
        lookup[c.parentId].push(c.callId);
      }
    }
    return lookup;
  }, [traceCallsResult]);

  // Update the main call to the one with costs
  const mainCall = useMemo(() => {
    let mainCallTemp: CallSchema = call;
    for (const c of costResult) {
      if (c.callId === mainCallTemp.callId) {
        mainCallTemp = c;
      }
    }
    return mainCallTemp;
  }, [costResult, call]);

  return useMemo(() => {
    let selectedCall = null;
    let selectedCallSimilarity = Number.POSITIVE_INFINITY;

    const rows: Row[] = [];
    // Ascend to the root
    let currentCall: CallSchema | null = mainCall;
    let lastCall: CallSchema = mainCall;

    let pathPrefix = '';
    while (currentCall != null) {
      lastCall = currentCall;
      const idx = getIndexWithinSameNameSiblings(
        currentCall,
        traceCallMap,
        childCallLookup
      );
      pathPrefix = updatePath(pathPrefix, currentCall.spanName, idx);
      if (currentCall.parentId) {
        if (!traceCallMap[currentCall.parentId]) {
          // Cant find parent, assume it doesn't exist
          currentCall.parentId = null;
        } else {
          currentCall = traceCallMap[currentCall.parentId];
        }
      } else {
        currentCall = null;
      }
    }

    // Add a parent row
    const parentCall = mainCall.parentId
      ? traceCallMap[mainCall.parentId]
      : null;
    if (parentCall) {
      rows.push({
        id: parentCall.callId,
        call: parentCall,
        status: parentCall.rawSpan.status_code,
        hierarchy: [parentCall.callId],
        path: '',
        isTraceRootCall: parentCall.callId === lastCall.callId,
        isParentRow: true,
      });
    }

    // Descend to the leaves
    const queue: Array<{
      targetCall: CallSchema;
      parentHierarchy: string[];
      path: string;
    }> = [
      {
        targetCall: mainCall,
        parentHierarchy: mainCall.parentId ? [mainCall.parentId] : [],
        path: pathPrefix,
      },
    ];
    while (queue.length > 0) {
      const {targetCall, parentHierarchy, path} = queue.shift()!;
      const newHierarchy = [...parentHierarchy, targetCall.callId];
      const idx = getIndexWithinSameNameSiblings(
        targetCall,
        traceCallMap,
        childCallLookup
      );
      const newPath = updatePath(path, targetCall.spanName, idx);
      const similarity = scorePathSimilarity(newPath, selectedPath ?? '');
      if (similarity < selectedCallSimilarity) {
        selectedCall = targetCall;
        selectedCallSimilarity = similarity;
      }
      rows.push({
        id: targetCall.callId,
        call: targetCall,
        status: targetCall.rawSpan.status_code,
        hierarchy: newHierarchy,
        path: newPath,
        isTraceRootCall: targetCall.callId === lastCall.callId,
      });
      const childIds = childCallLookup[targetCall.callId] ?? [];
      const childCalls = _.sortBy(
        childIds.map(c => traceCallMap[c]).filter(c => c),
        [getCallSortExampleRow, getCallSortStartTime]
      );

      // Add hidden children count row if needed
      if (childCalls.length > MAX_CHILDREN_TO_SHOW) {
        const visibleChildren = childCalls.slice(0, MAX_CHILDREN_TO_SHOW);
        const hiddenCount = childCalls.length - MAX_CHILDREN_TO_SHOW;

        // First add all visible children to queue
        visibleChildren.forEach(c =>
          queue.push({
            targetCall: c,
            parentHierarchy: newHierarchy,
            path: newPath,
          })
        );

        // Process all children in the queue that belong to this parent
        const childrenToProcess = queue.filter(
          item =>
            item.parentHierarchy[item.parentHierarchy.length - 1] ===
            targetCall.callId
        );

        // Remove these children from the main queue
        queue.splice(0, childrenToProcess.length);

        // Process the children
        for (const next of childrenToProcess) {
          const {
            targetCall: childCall,
            parentHierarchy: childHierarchy,
            path: childPath,
          } = next;
          const childIdx = getIndexWithinSameNameSiblings(
            childCall,
            traceCallMap,
            childCallLookup
          );
          const childNewPath = updatePath(
            childPath,
            childCall.spanName,
            childIdx
          );
          const childSimilarity = scorePathSimilarity(
            childNewPath,
            selectedPath ?? ''
          );
          if (childSimilarity < selectedCallSimilarity) {
            selectedCall = childCall;
            selectedCallSimilarity = childSimilarity;
          }
          rows.push({
            id: childCall.callId,
            call: childCall,
            status: childCall.rawSpan.status_code,
            hierarchy: [...childHierarchy, childCall.callId],
            path: childNewPath,
            isTraceRootCall: childCall.callId === lastCall.callId,
          });
        }

        // Finally add the hidden children count row
        rows.push({
          id: 'HIDDEN_CHILDREN_COUNT',
          count: hiddenCount,
          hierarchy: [...newHierarchy, 'HIDDEN_CHILDREN_COUNT'],
          parentId: targetCall.callId,
        });
      } else {
        // Add all children to queue if under limit
        childCalls.forEach(c =>
          queue.push({
            targetCall: c,
            parentHierarchy: newHierarchy,
            path: newPath,
          })
        );
      }
    }

    if (parentCall) {
      const childrenOfParent = childCallLookup[parentCall.callId];
      const siblingCount = childrenOfParent ? childrenOfParent.length - 1 : 0;
      if (siblingCount) {
        rows.push({
          id: 'HIDDEN_SIBLING_COUNT',
          count: siblingCount,
          hierarchy: [mainCall.parentId!, 'HIDDEN_SIBLING_COUNT'],
        });
      }
    }

    // Update status indicators to reflect status of descendants.
    const errorCalls = traceCallsResult.filter(
      c => c.rawSpan.status_code === 'ERROR'
    );
    if (errorCalls.length) {
      const ancestors = new Set<string>();
      for (const errorCall of errorCalls) {
        let ancestorCall = errorCall.parentId
          ? traceCallMap[errorCall.parentId]
          : null;
        while (ancestorCall != null && !ancestors.has(ancestorCall.callId)) {
          ancestors.add(ancestorCall.callId);
          ancestorCall = ancestorCall.parentId
            ? traceCallMap[ancestorCall.parentId]
            : null;
        }
      }
      for (const row of rows) {
        if (
          'status' in row &&
          row.status === 'SUCCESS' &&
          ancestors.has(row.id)
        ) {
          row.status = 'DESCENDANT_ERROR';
        }
      }
    }

    if (!selectedCall) {
      selectedCall = mainCall;
    }

    // Expand the path to the selected call.
    const expandKeys = new Set<string>();
    let callToExpand: CallSchema | null = selectedCall;
    while (callToExpand != null) {
      expandKeys.add(callToExpand.callId);
      callToExpand = callToExpand.parentId
        ? traceCallMap[callToExpand.parentId]
        : null;
    }
    return {
      rows,
      selectedCall,
      expandKeys,
      loading: traceCalls.loading,
      costLoading: costs.loading,
    };
  }, [
    mainCall,
    childCallLookup,
    traceCallMap,
    traceCallsResult,
    selectedPath,
    traceCalls.loading,
    costs.loading,
  ]);
};
