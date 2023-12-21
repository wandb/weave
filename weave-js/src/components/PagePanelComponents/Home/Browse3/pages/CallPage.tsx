import {Box, Button} from '@material-ui/core';
import {
  ArrowRight,
  Expand,
  ExpandLess,
  ExpandMore,
  KeyboardArrowRight,
} from '@mui/icons-material';
import {ButtonProps} from '@mui/material';
import {
  DataGridPro,
  DataGridProProps,
  GridColDef,
  gridFilteredDescendantCountLookupSelector,
  GridRenderCellParams,
  GridRowsProp,
  GridValidRowModel,
  useGridApiContext,
  useGridSelector,
} from '@mui/x-data-grid-pro';
import _ from 'lodash';
import React, {useMemo} from 'react';
import {useHistory} from 'react-router-dom';

import {Browse2TraceComponent} from '../../Browse2/Browse2TracePage';
import {useWeaveflowRouteContext} from '../context';
import {CallsTable} from './CallsPage';
import {CenteredAnimatedLoader} from './common/Loader';
import {OpVersionCategoryChip} from './common/OpVersionCategoryChip';
import {
  SimplePageLayout,
  SimplePageLayoutContext,
} from './common/SimplePageLayout';
import {UnderConstruction} from './common/UnderConstruction';
import {truncateID} from './util';
import {useWeaveflowORMContext} from './wfInterface/context';
import {WFCall} from './wfInterface/types';
import {SpanDetails} from '../../Browse2/SpanDetails';
import {SmallRef} from '../../Browse2/SmallRef';
import {parseRef} from '../../../../../react';

export const CallPage: React.FC<{
  entity: string;
  project: string;
  callId: string;
}> = props => {
  const orm = useWeaveflowORMContext(props.entity, props.project);
  const call = orm.projectConnection.call(props.callId);
  if (!call) {
    return <CenteredAnimatedLoader />;
  }
  return <CallPageInner {...props} call={call} />;
};

const CallPageInner: React.FC<{
  call: WFCall;
}> = ({call}) => {
  const entityName = call.entity();
  const projectName = call.project();
  const traceId = call.traceID();
  const callId = call.callID();
  const spanName = call.spanName();

  // const params = useMemo(() => {
  //   return {
  //     entity: entityName,
  //     project: projectName,
  //     traceId,
  //     spanId: callId,
  //   };
  // }, [entityName, projectName, traceId, callId]);
  const title = `${spanName}: ${truncateID(callId)}`;
  const traceTitle = `Trace: ${truncateID(traceId)}`;
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
                  flex: '1 1 50px',
                  overflow: 'hidden',
                }}>
                <CallTraceView call={call} />
              </Box>
              <Box
                sx={{
                  borderTop: '1px solid #e0e0e0',
                  display: 'flex',
                  flexDirection: 'column',
                  flex: '1 1 50px',
                  overflow: 'hidden',
                }}>
                <SimplePageLayoutContext.Provider value={{}}>
                  <SimplePageLayout
                    title={title}
                    menuItems={[
                      {
                        label: '(Under Construction) Open in Board',
                        onClick: () => {
                          console.log('TODO: Open in Board');
                        },
                      },
                      {
                        label: '(Under Construction) Compare',
                        onClick: () => {
                          console.log('TODO: Compare');
                        },
                      },
                    ]}
                    tabs={[
                      {
                        label: 'Call',
                        content: (
                          <Box
                            sx={{
                              display: 'flex',
                              flexDirection: 'column',
                              flex: '1 1 auto',
                              overflow: 'auto',
                              p: 8,
                            }}>
                            <SpanDetails call={call.rawCallSpan()} />
                          </Box>
                        ),
                      },
                      {
                        label: 'Child Calls',
                        content: (
                          <CallsTable
                            entity={entityName}
                            project={projectName}
                            frozenFilter={{
                              parentId: callId,
                            }}
                          />
                        ),
                      },
                      {
                        label: 'Feedback',
                        content: (
                          <UnderConstruction
                            title="Feedback"
                            message={
                              <>
                                Allows users to add key-value pairs to the Call.
                                TODO: Bring over from browse2.
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
                              <>
                                Shows all the datasets which this Call has been
                                added to
                              </>
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
                                This page will show a "Record" DAG of Objects
                                and Calls centered at this particular Call.
                              </>
                            }
                          />
                        ),
                      },
                    ]}
                  />
                </SimplePageLayoutContext.Provider>
              </Box>
            </Box>
          ),
        },
        // {
        //   label: 'Trace',
        //   content: <Browse2TraceComponent params={params} />,
        // },
        // {
        //   label: 'Calls',
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
      ]}
    />
  );
};

const CallTraceView: React.FC<{call: WFCall}> = ({call}) => {
  const history = useHistory();
  const {peekingRouter} = useWeaveflowRouteContext();
  const {rowsAcc: rows, expandKeys} = useMemo(() => {
    const rowsAcc: GridValidRowModel = [];
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
      parentHierarchy: Array<string>;
    }> = [{targetCall: lastCall, parentHierarchy: []}];
    while (queue.length > 0) {
      const {targetCall, parentHierarchy} = queue.shift()!;
      const newHierarchy = [...parentHierarchy, targetCall.callID()];
      rowsAcc.push({
        id: targetCall.callID(),
        call: targetCall,
        hierarchy: newHierarchy,
      });
      for (const childCall of targetCall.childCalls()) {
        queue.push({targetCall: childCall, parentHierarchy: newHierarchy});
      }
    }

    return {rowsAcc, expandKeys};
  }, [call]);

  const columns: GridColDef[] = [
    // {field: 'opName', headerName: 'Op Name'},
    // {field: 'opVersion', headerName: 'Op Version'},
    // {field: 'opCategory', headerName: 'Op Category'},
    // {field: 'callDuration', headerName: 'Duration'},
    {
      field: 'inputs',
      headerName: 'Basic Inputs',
      flex: 1,
      renderCell: ({row}) => {
        const call = row.call as WFCall;
        return (
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'row',
            }}>
            {call.rawCallSpan().inputs._keys?.map((k, i) => {
              const v = call.rawCallSpan().inputs[k];
              let value: React.ReactNode = '';

              if (typeof v === 'string' && v.startsWith('wandb-artifact:///')) {
                value = <SmallRef objRef={parseRef(v)} />;
                return null;
              } else if (_.isArray(v)) {
                value = `${v.length} items`;
                return null;
              } else if (_.isObject(v)) {
                value = `${Object.keys(v).length} entries`;
                return null;
              } else {
                value = v + '';
              }

              return (
                <Box
                  key={i}
                  sx={{
                    display: 'flex',
                    flexDirection: 'row',
                    alignItems: 'center',
                    gap: '4px',
                  }}>
                  <Box>{k}</Box>
                  <ArrowRight />
                  <Box>{value}</Box>
                </Box>
              );
            })}
          </Box>
        );
      },
    },
    {
      field: 'outputs',
      flex: 1,
      headerName: 'Basic Output',
      renderCell: ({row}) => {
        const call = row.call as WFCall;
        return (
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'row',
            }}>
            {call.rawCallSpan().output?._keys?.map((k, i) => {
              const v = call.rawCallSpan().output![k];
              let value: React.ReactNode = '';

              if (typeof v === 'string' && v.startsWith('wandb-artifact:///')) {
                value = <SmallRef objRef={parseRef(v)} />;
                return null;
              } else if (_.isArray(v)) {
                if (v.length === 1 && typeof v[0] === 'string') {
                  value = v[0];
                } else {
                  value = `${v.length} items`;
                  return null;
                }
              } else if (_.isObject(v)) {
                value = `${Object.keys(v).length} entries`;
                return null;
              } else {
                value = v + '';
              }

              return (
                <Box
                  key={i}
                  sx={{
                    display: 'flex',
                    flexDirection: 'row',
                    alignItems: 'center',
                    gap: '4px',
                  }}>
                  {/* <Box>{k}</Box>
                  <ArrowRight /> */}
                  <Box>{value}</Box>
                </Box>
              );
            })}
          </Box>
        );
      },
    },
  ];

  const getTreeDataPath: DataGridProProps['getTreeDataPath'] = row =>
    row.hierarchy;

  const groupingColDef: DataGridProProps['groupingColDef'] = {
    headerName: '',
    flex: 1,
    renderCell: params => <CustomGridTreeDataGroupingCell {...params} />,
  };
  const callClass = `.callId-${call.callID()}`;
  return (
    <DataGridPro
      rowHeight={38}
      treeData
      onRowClick={params => {
        const call = params.row.call as WFCall;
        history.push(
          peekingRouter.callUIUrl(
            call.entity(),
            call.project(),
            '',
            call.callID()
          )
        );
      }}
      rows={rows as GridRowsProp}
      columns={columns}
      getTreeDataPath={getTreeDataPath}
      groupingColDef={groupingColDef}
      isGroupExpandedByDefault={node =>
        expandKeys.has(node.groupingKey?.toString() ?? 'INVALID')
      }
      getRowClassName={params => {
        const call = params.row.call as WFCall;
        return `callId-${call.callID()}`;
      }}
      hideFooter
      rowSelection={false}
      sx={{
        '&>.MuiDataGrid-main': {
          '& div div div div >.MuiDataGrid-cell': {
            borderBottom: 'none',
          },
        },
        [callClass]: {
          backgroundColor: '#a9edf252',
        },
      }}
    />
  );
};

const BORDER_STYLE = '1px solid rgb(34,34,34)';
const INSET_SPACING = 60;
function CustomGridTreeDataGroupingCell(props: GridRenderCellParams) {
  const {id, field, rowNode, row} = props;
  const call = row.call as WFCall;
  const apiRef = useGridApiContext();
  // const filteredDescendantCountLookup = useGridSelector(
  //   apiRef,
  //   gridFilteredDescendantCountLookupSelector
  // );

  // const filteredDescendantCount =
  //   filteredDescendantCountLookup[rowNode.id] ?? 0;

  const handleClick: ButtonProps['onClick'] = event => {
    if (rowNode.type !== 'group') {
      return;
    }

    apiRef.current.setRowChildrenExpansion(id, !rowNode.childrenExpanded);
    apiRef.current.setCellFocus(id, field);
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
        // ml: rowNode.depth * INSET_SPACING,
        height: '100%',
        display: 'flex',
        flexDirection: 'row',
        alignItems: 'center',
        // gap: '8px',
        justifyContent: 'left',
      }}>
      {_.range(rowNode.depth).map(i => {
        return (
          <Box
            key={i}
            sx={{
              // ml: `${INSET_SPACING / 2}px`,
              flex: `0 0 ${INSET_SPACING / 2}px`,
              width: `${INSET_SPACING / 2}px`,
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              // borderRight: BORDER_STYLE,
            }}>
            <Box
              sx={{
                width: '100%',
                height: '100%',
                // borderBottom: BORDER_STYLE,
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
          // ml: `${INSET_SPACING / 2}px`,
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
              borderRadius: '50%',
            }}>
            {rowNode.childrenExpanded ? <ExpandMore /> : <KeyboardArrowRight />}
          </Button>
        ) : (
          <>
            <Box
              sx={{
                width: '100%',
                height: '100%',
                borderBottom: BORDER_STYLE,
              }}></Box>
            <Box sx={{width: '100%', height: '100%'}}></Box>
          </>
        )}
      </Box>
      <Box
        sx={{
          ml: 1,
        }}>
        {call.spanName() + ': ' + truncateID(call.callID())}
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
}
