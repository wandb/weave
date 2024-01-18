import {Box, Button, Typography} from '@material-ui/core';
import {ExpandMore, KeyboardArrowRight} from '@mui/icons-material';
import {ButtonProps} from '@mui/material';
import {
  DataGridPro,
  DataGridProProps,
  GridColDef,
  GridRenderCellParams,
  useGridApiContext,
} from '@mui/x-data-grid-pro';
import _ from 'lodash';
import React, {useCallback, useEffect, useMemo} from 'react';
import {useHistory} from 'react-router-dom';

import {parseRef} from '../../../../../react';
import {Call} from '../../Browse2/callTree';
import {SmallRef} from '../../Browse2/SmallRef';
import {SpanDetails, SpanDetails2} from '../../Browse2/SpanDetails';
import {useWeaveflowCurrentRouteContext} from '../context';
import {CenteredAnimatedLoader} from './common/Loader';
import {OpVersionCategoryChip} from './common/OpVersionCategoryChip';
import {
  SimplePageLayout,
  SimplePageLayoutContext,
} from './common/SimplePageLayout';
import {UnderConstruction} from './common/UnderConstruction';
import {GroupedCalls} from './ObjectVersionPage';
import {truncateID} from './util';
import {useWeaveflowORMContext} from './wfInterface/context';
import {WFCall} from './wfInterface/types';

// % of screen to give the trace view in horizontal mode
const TRACE_PCT = 40;

// Whether to show complex inputs/outputs in the table
const SHOW_COMPLEX_IO = true;

export const CallPage: React.FC<{
  entity: string;
  project: string;
  callId: string;
}> = props => {
  const orm = useWeaveflowORMContext(props.entity, props.project);
  const call = orm.projectConnection.call(props.callId);
  const [verticalLayout, setVerticalLayout] = React.useState(true);
  if (!call) {
    return <CenteredAnimatedLoader />;
  }
  if (verticalLayout) {
    return (
      <CallPageInnerVertical
        {...props}
        setVerticalLayout={setVerticalLayout}
        call={call}
      />
    );
  }
  return (
    <CallPageInnerHorizontal
      {...props}
      setVerticalLayout={setVerticalLayout}
      call={call}
    />
  );
};

const useCallTabs = (call: WFCall) => {
  return [
    {
      label: 'Call',
      content: <SpanDetails2 wfCall={call} />,
    },
    // {
    //   label: 'Child Calls',
    //   content: (
    //     <CallsTable
    //       entity={entityName}
    //       project={projectName}
    //       frozenFilter={{
    //         parentId: callId,
    //       }}
    //     />
    //   ),
    // },
    {
      label: 'Feedback',
      content: (
        <UnderConstruction
          title="Feedback"
          message={
            <>
              Allows users to add key-value pairs to the Call. TODO: Bring over
              from browse2.
            </>
          }
        />
      ),
    },
    {
      label: 'Datasets',
      content: (
        <UnderConstruction
          title="Datasets"
          message={
            <>Shows all the datasets which this Call has been added to</>
          }
        />
      ),
    },
    {
      label: 'DAG',
      content: (
        <UnderConstruction
          title="Record DAG"
          message={
            <>
              This page will show a "Record" DAG of Objects and Calls centered
              at this particular Call.
            </>
          }
        />
      ),
    },
  ];
};

// const callMenuItems = [
//   {
//     label: '(Under Construction) Open in Board',
//     onClick: () => {
//       console.log('TODO: Open in Board');
//     },
//   },
//   {
//     label: '(Under Construction) Compare',
//     onClick: () => {
//       console.log('TODO: Compare');
//     },
//   },
// ];

const CallPageInnerHorizontal: React.FC<{
  call: WFCall;
  setVerticalLayout: (vertical: boolean) => void;
}> = ({call, setVerticalLayout}) => {
  const traceId = call.traceID();
  const callId = call.callID();
  const spanName = call.spanName();

  const title = `${spanName}: ${truncateID(callId)}`;
  const traceTitle = `Trace: ${truncateID(traceId)}`;

  const callTabs = useCallTabs(call);

  return (
    <SimplePageLayout
      title={traceTitle}
      menuItems={[
        {
          label: 'View Vertical',
          onClick: () => {
            setVerticalLayout(true);
          },
        },
      ]}
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

const CallPageInnerVertical: React.FC<{
  call: WFCall;
  setVerticalLayout: (vertical: boolean) => void;
}> = ({call, setVerticalLayout}) => {
  const callId = call.callID();
  const spanName = call.spanName();
  const title = `${spanName} (${truncateID(callId)})`;
  const callTabs = useCallTabs(call);
  return (
    <SimplePageLayout
      title={title}
      // menuItems={[
      //   {
      //     label: 'View Horizontal',
      //     onClick: () => {
      //       setVerticalLayout(false);
      //     },
      //   },
      //   // ...callMenuItems,
      // ]}
      leftSidebar={<CallTraceView call={call} treeOnly />}
      tabs={callTabs}
    />
  );
};

const CallTraceView: React.FC<{call: WFCall; treeOnly?: boolean}> = ({
  call,
  treeOnly,
}) => {
  const history = useHistory();
  const currentRouter = useWeaveflowCurrentRouteContext();
  const {rows, expandKeys: forcedExpandKeys} = useCallFlattenedTraceTree(call);
  const [expandKeys, setExpandKeys] = React.useState(forcedExpandKeys);
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
        const rowCall = row.call as WFCall;
        return (
          <BasicInputOutputRenderer ioData={rowCall.rawCallSpan().inputs} />
        );
      },
    },

    // Somewhat experimental field designed to show the primitive outputs
    // Feel free to remove this if it's not useful.
    {
      field: 'outputs',
      flex: 1,
      headerName: 'Output',
      renderCell: ({row}) => {
        const rowCall = row.call as WFCall;
        return (
          <BasicInputOutputRenderer ioData={rowCall.rawCallSpan().output} />
        );
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

  // Informs DataGridPro what to do when a row is clicked - in this case
  // use the current router to navigate to the call page for the clicked
  // call. Effectively this looks like expanding the clicked call.
  const onRowClick: DataGridProProps['onRowClick'] = useCallback(
    params => {
      const rowCall = params.row.call as WFCall;
      history.push(
        currentRouter.callUIUrl(
          rowCall.entity(),
          rowCall.project(),
          '',
          rowCall.callID()
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
  const callClass = `.callId-${call.callID()}`;
  const getRowClassName: DataGridProProps['getRowClassName'] = useCallback(
    params => {
      const rowCall = params.row.call as WFCall;
      return `callId-${rowCall.callID()}`;
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
      [callClass]: {
        backgroundColor: '#a9edf252',
      },
    }),
    [callClass]
  );

  return (
    <DataGridPro
      rowHeight={38}
      columnHeaderHeight={treeOnly ? 0 : 56}
      treeData
      onRowClick={onRowClick}
      rows={rows}
      columns={treeOnly ? [] : columns}
      getTreeDataPath={getTreeDataPath}
      groupingColDef={groupingColDef}
      isGroupExpandedByDefault={isGroupExpandedByDefault}
      getRowClassName={getRowClassName}
      hideFooter
      rowSelection={false}
      sx={sx}
    />
  );
};

const INSET_SPACING = 54;
const TREE_COLOR = '#aaaeb2';
const BORDER_STYLE = `1px solid ${TREE_COLOR}`;

/**
 * Utility component to render the grouping cell for the trace tree.
 * Most of the work here is to rendering the tree structure (i.e. the
 * lines connecting the cells, expanding/collapsing the tree, etc).
 */
const CustomGridTreeDataGroupingCell: React.FC<
  GridRenderCellParams & {onClick?: (event: React.MouseEvent) => void}
> = props => {
  const {id, field, rowNode, row} = props;
  const call = row.call as WFCall;
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

  const opCategory = call.opVersion()?.opCategory();
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
  }, [apiRef, rowNode.id, rowNode.parent]);
  return (
    <Box
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
          <Button
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
          </Button>
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
      <Box
        sx={{
          // ml: 1,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          flex: '1 1 auto',
          fontWeight: 'bold',
        }}>
        {/* {call.spanName() + ': ' + truncateID(call.callID())} */}
        {call.spanName().split('-').slice(-1)[0]}
      </Box>
      {opCategory && (
        <Box
          sx={{
            ml: 4,
          }}>
          <OpVersionCategoryChip opCategory={opCategory} />
        </Box>
      )}
    </Box>
  );
};

const BasicInputOutputRenderer: React.FC<{
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
        let value: React.ReactNode = '';

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
 * it will find the trace root for a call, then find all the ancestors
 * of the root. The flattened order is depth-first, so that when listed
 * in a a table, the children of each call will be listed immediately
 * after the parent call. The structure of the returned rows conforms to
 * `GridValidRowModel`, but is specifically:
 * {
 *  id: string;
 *  call: WFCall;
 *  hierarchy: string[];
 * }
 * where `hierarchy` is the list of call IDs from the root to the current.
 *
 * Furthermore, the `expandKeys` set contains the call IDs of all the calls
 * from the root to the current call, so that the tree can be expanded to
 * show the current call.
 */
const useCallFlattenedTraceTree = (call: WFCall) => {
  return useMemo(() => {
    const rows: Array<{
      id: string;
      call: WFCall;
      hierarchy: string[];
    }> = [];
    const expandKeys = new Set<string>();
    // Ascend to the root
    let currentCall: WFCall | null = call;
    let lastCall: WFCall = call;

    while (currentCall != null) {
      lastCall = currentCall;
      expandKeys.add(currentCall.callID());
      currentCall = currentCall.parentCall();
    }

    // Descend to the leaves
    const queue: Array<{
      targetCall: WFCall;
      parentHierarchy: string[];
    }> = [{targetCall: lastCall, parentHierarchy: []}];
    while (queue.length > 0) {
      const {targetCall, parentHierarchy} = queue.shift()!;
      const newHierarchy = [...parentHierarchy, targetCall.callID()];
      rows.push({
        id: targetCall.callID(),
        call: targetCall,
        hierarchy: newHierarchy,
      });
      for (const childCall of targetCall.childCalls()) {
        queue.push({targetCall: childCall, parentHierarchy: newHierarchy});
      }
    }

    return {rows, expandKeys};
  }, [call]);
};
