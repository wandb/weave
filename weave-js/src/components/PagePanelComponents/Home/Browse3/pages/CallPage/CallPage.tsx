import {Box, Button as MuiButton} from '@material-ui/core';
import {ExpandMore, KeyboardArrowRight} from '@mui/icons-material';
import {ButtonProps} from '@mui/material';
import {
  DataGridPro,
  DataGridProProps,
  GridColDef,
  GridRenderCellParams,
  useGridApiContext,
  useGridApiRef,
} from '@mui/x-data-grid-pro';
import _ from 'lodash';
import React, {
  FC,
  MouseEvent,
  ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react';
import {useHistory} from 'react-router-dom';
import styled from 'styled-components';

import {MOON_500} from '../../../../../../common/css/color.styles';
import {parseRef} from '../../../../../../react';
import {Button} from '../../../../../Button';
import {ErrorBoundary} from '../../../../../ErrorBoundary';
import {IconParentBackUp} from '../../../../../Icon';
import {Tooltip} from '../../../../../Tooltip';
import {Browse2OpDefCode} from '../../../Browse2/Browse2OpDefCode';
import {Call} from '../../../Browse2/callTree';
import {SmallRef} from '../../../Browse2/SmallRef';
import {useWeaveflowCurrentRouteContext} from '../../context';
import {
  queryGetBoolean,
  querySetBoolean,
  queryToggleBoolean,
} from '../../urlQueryUtil';
import {opNiceName} from '../common/Links';
import {CenteredAnimatedLoader} from '../common/Loader';
import {
  SimplePageLayout,
  SimplePageLayoutContext,
  SimplePageLayoutWithHeader,
} from '../common/SimplePageLayout';
import {CallStatusType, StatusChip} from '../common/StatusChip';
import {truncateID} from '../util';
import {CallSchema, useCall, useCalls} from '../wfReactInterface/interface';
import {CallDetails} from './CallDetails';
import {CallOverview} from './CallOverview';
import {CallSummary} from './CallSummary';

// % of screen to give the trace view in horizontal mode
const TRACE_PCT = 40;

// Whether to show complex inputs/outputs in the table
const SHOW_COMPLEX_IO = true;

export const CallPage: FC<{
  entity: string;
  project: string;
  callId: string;
}> = props => {
  const call = useCall({
    entity: props.entity,
    project: props.project,
    callId: props.callId,
  });
  const [verticalLayout, setVerticalLayout] = useState(true);
  if (call.loading) {
    return <CenteredAnimatedLoader />;
  } else if (call.result === null) {
    return <div>Call not found</div>;
  }
  if (verticalLayout) {
    return (
      <CallPageInnerVertical
        {...props}
        setVerticalLayout={setVerticalLayout}
        call={call.result}
      />
    );
  }
  return (
    <CallPageInnerHorizontal
      {...props}
      setVerticalLayout={setVerticalLayout}
      call={call.result}
    />
  );
};

const useCallTabs = (call: CallSchema) => {
  const codeURI = call.opVersionRef;
  return [
    {
      label: 'Call',
      content: <CallDetails call={call} />,
    },
    ...(codeURI
      ? [
          {
            label: 'Code',
            content: <Browse2OpDefCode uri={codeURI} />,
          },
        ]
      : []),
    {
      label: 'Summary',
      content: <CallSummary call={call} />,
    },
  ];
};

const CallPageInnerHorizontal: FC<{
  call: CallSchema;
  setVerticalLayout: (vertical: boolean) => void;
}> = ({call, setVerticalLayout}) => {
  const {traceId, callId, spanName} = call;

  const title = `${spanName}: ${truncateID(callId)}`;
  const traceTitle = `Trace: ${truncateID(traceId)}`;

  const callTabs = useCallTabs(call);

  return (
    <SimplePageLayout
      title={traceTitle}
      tabs={[
        {
          label: 'Trace',
          content: (
            <Box
              sx={{
                display: 'flex',
                flexDirection: 'column',
                flex: '1 1 auto',
                overflow: 'hidden',
              }}>
              <Box
                sx={{
                  display: 'flex',
                  flexDirection: 'column',
                  flex: `1 1 ${TRACE_PCT}%`,
                  height: TRACE_PCT,
                  overflow: 'hidden',
                }}>
                <CallTraceView call={call} />
              </Box>
              <Box
                sx={{
                  borderTop: '1px solid #e0e0e0',
                  display: 'flex',
                  flexDirection: 'column',
                  flex: `1 1 ${100 - TRACE_PCT}%`,
                  height: 100 - TRACE_PCT,
                  overflow: 'hidden',
                }}>
                <SimplePageLayoutContext.Provider value={{}}>
                  <SimplePageLayout
                    title={title}
                    // menuItems={callMenuItems}
                    tabs={callTabs}
                  />
                </SimplePageLayoutContext.Provider>
              </Box>
            </Box>
          ),
        },
      ]}
    />
  );
};

const CallPageInnerVertical: FC<{
  call: CallSchema;
  setVerticalLayout: (vertical: boolean) => void;
}> = ({call, setVerticalLayout}) => {
  const {callId} = call;
  const spanName = opNiceName(call.spanName);
  const title = `${spanName} (${truncateID(callId)})`;
  const callTabs = useCallTabs(call);
  const history = useHistory();
  const showTraceTree = queryGetBoolean(history, 'tracetree', true);
  const onToggleTraceTree = () => {
    queryToggleBoolean(history, 'tracetree', true);
  };
  return (
    <SimplePageLayoutWithHeader
      title={title}
      headerExtra={
        <Box
          sx={{
            height: '47px',
          }}>
          <Button
            icon="layout-tabs"
            tooltip={`${showTraceTree ? 'Hide' : 'Show'} trace tree`}
            variant="ghost"
            active={showTraceTree ?? false}
            onClick={onToggleTraceTree}
          />
        </Box>
      }
      isSidebarOpen={showTraceTree}
      headerContent={<CallOverview call={call} />}
      leftSidebar={<CallTraceView call={call} treeOnly />}
      tabs={callTabs}
    />
  );
};

const CallTrace = styled.div`
  display: flex;
  flex-direction: column;
  height: 100%;
`;
CallTrace.displayName = 'S.CallTrace';

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

const CallTraceTree = styled.div`
  overflow: auto;
  flex: 1 1 auto;
`;
CallTraceTree.displayName = 'S.CallTraceTree';

const CallOrCountRow = styled.div`
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  gap: 4px;
`;
CallOrCountRow.displayName = 'S.CallOrCountRow';

const CallTraceView: FC<{call: CallSchema; treeOnly?: boolean}> = ({
  call,
  treeOnly,
}) => {
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

  const columns: GridColDef[] = [
    // probably want to add more details like the following in the future.
    // {field: 'opName', headerName: 'Op Name'},
    // {field: 'opVersion', headerName: 'Op Version'},
    // {field: 'opCategory', headerName: 'Op Category'},
    // {field: 'callDuration', headerName: 'Duration'},

    // Somewhat experimental field designed to show the primitive inputs
    // Feel free to remove this if it's not useful.
    {
      field: 'inputs',
      headerName: 'Inputs',
      flex: 1,
      renderCell: ({row}) => {
        const rowCall = row.call as CallSchema;
        return <BasicInputOutputRenderer ioData={rowCall.rawSpan.inputs} />;
      },
    },

    // Somewhat experimental field designed to show the primitive outputs
    // Feel free to remove this if it's not useful.
    {
      field: 'outputs',
      flex: 1,
      headerName: 'Output',
      renderCell: ({row}) => {
        const rowCall = row.call as CallSchema;
        return <BasicInputOutputRenderer ioData={rowCall.rawSpan.output} />;
      },
    },
  ];

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
        borderBottom: treeOnly ? 'none' : undefined,
      },
      [callClass]: {
        backgroundColor: '#a9edf252',
      },
    }),
    [callClass, treeOnly]
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
            columnHeaderHeight={treeOnly ? 0 : 56}
            treeData
            loading={treeLoading || animationBuffer}
            onRowClick={onRowClick}
            rows={treeLoading || animationBuffer ? [] : rows}
            columns={treeOnly ? [] : columns}
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

const INSET_SPACING = 54;
const TREE_COLOR = '#aaaeb2';
const BORDER_STYLE = `1px solid ${TREE_COLOR}`;

// MUI Box doesn't support cursor
// https://github.com/mui/material-ui/issues/19983
const CursorBox = styled(Box)<{$isClickable: boolean}>`
  cursor: ${p => (p.$isClickable ? 'pointer' : 'default')};
`;
CursorBox.displayName = 'S.CursorBox';

/**
 * Utility component to render the grouping cell for the trace tree.
 * Most of the work here is to rendering the tree structure (i.e. the
 * lines connecting the cells, expanding/collapsing the tree, etc).
 */
const CustomGridTreeDataGroupingCell: FC<
  GridRenderCellParams & {onClick?: (event: MouseEvent) => void}
> = props => {
  const {id, field, rowNode, row} = props;
  const {isParentRow} = row;
  const call = row.call as CallSchema;
  const apiRef = useGridApiContext();
  const handleClick: ButtonProps['onClick'] = event => {
    if (rowNode.type !== 'group') {
      return;
    }

    apiRef.current.setRowChildrenExpansion(id, !rowNode.childrenExpanded);
    apiRef.current.setCellFocus(id, field);

    if (props.onClick) {
      props.onClick(event);
    }

    event.stopPropagation();
  };

  const hasCountRow = apiRef.current.getRowNode('HIDDEN_SIBLING_COUNT') != null;
  const isLastChild = useMemo(() => {
    if (rowNode.parent == null) {
      return false;
    }
    const parentRow = apiRef.current.getRowNode(rowNode.parent);
    if (parentRow == null) {
      return false;
    }
    const childrenIds = apiRef.current.getRowGroupChildren({
      groupId: parentRow.id,
    });
    if (childrenIds == null) {
      return false;
    }
    const lastChildId = childrenIds[childrenIds.length - 1];
    return rowNode.id === lastChildId;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiRef, rowNode.id, rowNode.parent, hasCountRow]);

  const tooltip = isParentRow
    ? 'This is the parent of the currently viewed call. Click to view.'
    : undefined;
  const rowTypeIndicator = isParentRow ? (
    <IconParentBackUp color={MOON_500} width={18} height={18} />
  ) : null;

  const isHiddenCount = id === 'HIDDEN_SIBLING_COUNT';

  const box = (
    <CursorBox
      $isClickable={!isHiddenCount}
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'left',
        width: '100%',
      }}>
      {_.range(rowNode.depth).map(i => {
        return (
          <Box
            key={i}
            sx={{
              flex: `0 0 ${INSET_SPACING / 2}px`,
              width: `${INSET_SPACING / 2}px`,
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
            <Box
              sx={{
                width: '100%',
                height: '100%',
                borderRight: BORDER_STYLE,
              }}></Box>
            <Box
              sx={{
                width: '100%',
                height: '100%',
                borderRight:
                  isLastChild && i === rowNode.depth - 1 ? '' : BORDER_STYLE,
              }}></Box>
          </Box>
        );
      })}
      <Box
        sx={{
          flex: `0 0 ${INSET_SPACING}px`,
          width: `${INSET_SPACING}px`,
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
        }}>
        {rowNode.type === 'group' ? (
          <MuiButton
            onClick={handleClick}
            tabIndex={-1}
            size="small"
            style={{
              height: '26px',
              width: '26px',
              minWidth: '26px',
              borderRadius: '50%',
              color: TREE_COLOR,
            }}>
            {rowNode.childrenExpanded ? <ExpandMore /> : <KeyboardArrowRight />}
          </MuiButton>
        ) : (
          <Box
            sx={{
              width: '100%',
              height: '100%',
              pr: 2,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
            <Box
              sx={{
                width: '100%',
                height: '100%',
                borderBottom: BORDER_STYLE,
              }}></Box>
            <Box sx={{width: '100%', height: '100%'}}></Box>
          </Box>
        )}
      </Box>
      <CallOrCountRow>
        {isHiddenCount ? (
          <Box>{row.count.toLocaleString()} hidden calls</Box>
        ) : (
          <>
            <Box
              sx={{
                mr: 1,
              }}>
              <StatusChip value={row.status} iconOnly />
            </Box>
            <Box
              sx={{
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                flex: '1 1 auto',
              }}>
              {opNiceName(call.spanName)}
            </Box>
          </>
        )}
        {rowTypeIndicator && <Box>{rowTypeIndicator}</Box>}
      </CallOrCountRow>
    </CursorBox>
  );

  return tooltip ? <Tooltip content={tooltip} trigger={box} /> : box;
};

const BasicInputOutputRenderer: FC<{
  ioData: Call['inputs'] | Call['output'];
}> = ({ioData}) => {
  return (
    <Box
      sx={{
        height: '100%',
        width: '100%',
        overflow: 'auto',
        display: 'flex',
        flexDirection: 'column',
      }}>
      {ioData?._keys?.map((k, i) => {
        const v = ioData![k];
        let value: ReactNode = '';

        if (typeof v === 'string' && v.startsWith('wandb-artifact:///')) {
          value = <SmallRef objRef={parseRef(v)} />;
          if (!SHOW_COMPLEX_IO) {
            return null;
          }
        } else if (_.isArray(v)) {
          if (v.length === 1 && typeof v[0] === 'string') {
            value = v[0];
          } else {
            value = `List of ${v.length} items`;
            if (!SHOW_COMPLEX_IO) {
              return null;
            }
          }
        } else if (_.isObject(v)) {
          value = `Object with ${Object.keys(v).length} entries`;
          if (!SHOW_COMPLEX_IO) {
            return null;
          }
        } else {
          value = v + '';
        }

        return (
          <Box
            key={i}
            gridGap={4}
            sx={{
              display: 'flex',
              flexDirection: 'row',
              alignItems: 'center',
              height: '38px',
              flex: '0 0 auto',
            }}>
            {k !== '_result' && (
              <>
                <Box
                  sx={{
                    fontWeight: 'bold',
                  }}>
                  {k}
                </Box>
                <span>:</span>
              </>
            )}
            <Box>{value}</Box>
          </Box>
        );
      })}
    </Box>
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
