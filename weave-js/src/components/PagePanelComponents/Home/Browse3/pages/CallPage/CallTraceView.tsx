import {
  DataGridPro,
  DataGridProProps,
  useGridApiRef,
} from '@mui/x-data-grid-pro';
import _ from 'lodash';
import React, {FC, useCallback, useEffect, useMemo, useState} from 'react';
import {useHistory} from 'react-router-dom';
import styled from 'styled-components';

import {Button} from '../../../../../Button';
import {ErrorBoundary} from '../../../../../ErrorBoundary';
import {useWeaveflowCurrentRouteContext} from '../../context';
import {querySetBoolean} from '../../urlQueryUtil';
import {CallStatusType} from '../common/StatusChip';
import {useWFHooks} from '../wfReactInterface/context';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {CustomGridTreeDataGroupingCell} from './CustomGridTreeDataGroupingCell';

const CallTrace = styled.div`
  display: flex;
  flex-direction: column;
  height: 100%;
`;
CallTrace.displayName = 'S.CallTrace';

const CallTraceTree = styled.div`
  overflow: auto;
  flex: 1 1 auto;
`;
CallTraceTree.displayName = 'S.CallTraceTree';

const CallTraceHeader = styled.div`
  display: flex;
  align-items: center;
  padding: 8px 4px 8px 16px;
`;
CallTraceHeader.displayName = 'S.CallTraceHeader';

const CallTraceHeaderTitle = styled.div`
  font-weight: 600;
  font-size: 18px;
  flex: 1 1 auto;
`;
CallTraceHeaderTitle.displayName = 'S.CallTraceHeaderTitle';

export const CallTraceView: FC<{call: CallSchema}> = ({call}) => {
  const apiRef = useGridApiRef();
  const history = useHistory();
  const currentRouter = useWeaveflowCurrentRouteContext();
  const {
    rows,
    expandKeys: forcedExpandKeys,
    loading: treeLoading,
  } = useCallFlattenedTraceTree(call);
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
      renderCell: params => (
        <CustomGridTreeDataGroupingCell
          {...params}
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
    []
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
      setSuppressScroll(true);
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
      node => expandKeys.has(node.groupingKey?.toString() ?? 'INVALID'),
      [expandKeys]
    );

  // Informs DataGridPro how to style the rows. In this case, we highlight
  // the current call.
  const callClass = `.callId-${call.callId}`;
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
      '&>.MuiDataGrid-main': {
        '& div div div div >.MuiDataGrid-cell': {
          borderBottom: 'none',
        },
      },
      '& .MuiDataGrid-columnHeaders': {
        borderBottom: 'none',
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

  const onCloseTraceTree = () => {
    querySetBoolean(history, 'tracetree', false);
  };

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
      <CallTraceHeader>
        <CallTraceHeaderTitle>Trace tree</CallTraceHeaderTitle>
        <Button icon="close" variant="ghost" onClick={onCloseTraceTree} />
      </CallTraceHeader>
      <CallTraceTree>
        <ErrorBoundary>
          <DataGridPro
            apiRef={apiRef}
            rowHeight={38}
            columnHeaderHeight={0}
            treeData
            loading={treeLoading || animationBuffer}
            onRowClick={onRowClick}
            rows={treeLoading || animationBuffer ? [] : rows}
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
      </CallTraceTree>
    </CallTrace>
  );
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
  isTraceRootCall: boolean;
  isParentRow?: boolean;
};
type CountRow = {
  id: 'HIDDEN_SIBLING_COUNT';
  count: number;
  hierarchy: string[];
};
type Row = CallRow | CountRow;
const useCallFlattenedTraceTree = (call: CallSchema) => {
  const {useCalls} = useWFHooks();
  const traceCalls = useCalls(call.entity, call.project, {
    traceId: call.traceId,
  });
  const traceCallsResult = useMemo(
    () => traceCalls.result ?? [],
    [traceCalls.result]
  );
  const traceCallMap = useMemo(
    () => _.keyBy(traceCallsResult, 'callId'),
    [traceCallsResult]
  );
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
  return useMemo(() => {
    const rows: Row[] = [];
    const expandKeys = new Set<string>();
    // Ascend to the root
    let currentCall: CallSchema | null = call;
    let lastCall: CallSchema = call;

    while (currentCall != null) {
      lastCall = currentCall;
      expandKeys.add(currentCall.callId);
      currentCall = currentCall.parentId
        ? traceCallMap[currentCall.parentId]
        : null;
    }

    // Add a parent row
    const parentCall = call.parentId ? traceCallMap[call.parentId] : null;
    if (parentCall) {
      rows.push({
        id: parentCall.callId,
        call: parentCall,
        status: parentCall.rawSpan.status_code,
        hierarchy: [parentCall.callId],
        isTraceRootCall: parentCall.callId === lastCall.callId,
        isParentRow: true,
      });
    }

    // Descend to the leaves
    const queue: Array<{
      targetCall: CallSchema;
      parentHierarchy: string[];
    }> = [
      {
        targetCall: call,
        parentHierarchy: call.parentId ? [call.parentId] : [],
      },
    ];
    while (queue.length > 0) {
      const {targetCall, parentHierarchy} = queue.shift()!;
      const newHierarchy = [...parentHierarchy, targetCall.callId];
      rows.push({
        id: targetCall.callId,
        call: targetCall,
        status: targetCall.rawSpan.status_code,
        hierarchy: newHierarchy,
        isTraceRootCall: targetCall.callId === lastCall.callId,
      });
      const childIds = childCallLookup[targetCall.callId] ?? [];
      childIds.forEach(c => {
        const childCall = traceCallMap[c];
        if (!childCall) {
          return;
        }
        queue.push({targetCall: childCall, parentHierarchy: newHierarchy});
      });
    }

    if (parentCall) {
      const siblingCount = childCallLookup[parentCall.callId]?.length - 1 ?? 0;
      if (siblingCount) {
        rows.push({
          id: 'HIDDEN_SIBLING_COUNT',
          count: siblingCount,
          hierarchy: [call.parentId!, 'HIDDEN_SIBLING_COUNT'],
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

    return {rows, expandKeys, loading: traceCalls.loading};
  }, [
    call,
    childCallLookup,
    traceCallMap,
    traceCallsResult,
    traceCalls.loading,
  ]);
};
