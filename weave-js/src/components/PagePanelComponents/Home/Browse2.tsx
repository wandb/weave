import * as _ from 'lodash';
import React, {FC, useCallback, useEffect, useMemo, useState} from 'react';
import {
  Switch,
  Route,
  Link as RouterLink,
  useParams,
  useHistory,
  useLocation,
} from 'react-router-dom';

import styled from 'styled-components';
import * as globals from '@wandb/weave/common/css/globals.styles';
import {URL_BROWSE2} from '../../../urls';
import {useIsAuthenticated} from '@wandb/weave/context/WeaveViewerContext';
import * as query from './query';
import {
  callOpVeryUnsafe,
  constNumber,
  constString,
  opGet,
  Node,
  linearize,
  isConstNode,
} from '@wandb/weave/core';
import {ChildPanel, ChildPanelConfig, initPanel} from '../../Panel2/ChildPanel';
import {usePanelContext} from '../../Panel2/PanelContext';
import {useWeaveContext} from '@wandb/weave/context';
import {useMakeLocalBoardFromNode} from '../../Panel2/pyBoardGen';
import {SEED_BOARD_OP_NAME} from './HomePreviewSidebar';
import {isWandbArtifactRef, parseRef, useNodeValue} from '@wandb/weave/react';
import {monthRoundedTime} from '@wandb/weave/time';
import {flatToTrees} from '../../Panel2/PanelTraceTree/util';
import {
  Call,
  CallFilter,
  Span,
  StreamId,
  TraceSpan,
  callsTableFilter,
  callsTableNode,
  callsTableOpCounts,
  callsTableSelect,
  callsTableSelectTraces,
} from './Browse2/callTree';
import {
  useFirstCall,
  useOpSignature,
  useTraceSpans,
} from './Browse2/callTreeHooks';
import {
  OpenAIChatInputView,
  OpenAIChatOutputView,
  isOpenAIChatInput,
  isOpenAIChatOutput,
} from './Browse2/openai';
import {
  AppBar,
  IconButton,
  Link as MaterialLink,
  Button,
  Toolbar,
  Typography,
  Breadcrumbs,
  Box,
  Grid,
  Paper as MaterialPaper,
  Container,
  Chip,
  Tabs,
  Tab,
  TextField,
} from '@mui/material';
import {DataGridPro as DataGrid} from '@mui/x-data-grid-pro';
import {Home, FilterList} from '@mui/icons-material';
import {LicenseInfo} from '@mui/x-license-pro';

LicenseInfo.setLicenseKey(
  '7684ecd9a2d817a3af28ae2a8682895aTz03NjEwMSxFPTE3MjgxNjc2MzEwMDAsUz1wcm8sTE09c3Vic2NyaXB0aW9uLEtWPTI='
);

function useQuery() {
  const {search} = useLocation();

  return React.useMemo(() => new URLSearchParams(search), [search]);
}

const PageEl = styled.div``;

const PageHeader: FC<{objectType: string; objectName?: string}> = ({
  objectType,
  objectName,
}) => {
  return (
    <Box display="flex" alignItems="baseline" marginBottom={3}>
      <Typography variant="h4" component="span" style={{fontWeight: 'bold'}}>
        {objectType}
      </Typography>
      {objectName != null && (
        <Typography variant="h4" component="span" style={{marginLeft: '8px'}}>
          {objectName}
        </Typography>
      )}
    </Box>
  );
};

const opDisplayName = (opName: string) => {
  if (opName.startsWith('wandb-artifact:')) {
    const ref = parseRef(opName);
    if (isWandbArtifactRef(ref)) {
      let opName = ref.artifactName;
      if (opName.startsWith('op-')) {
        opName = opName.slice(3);
      }
      return opName + ':' + ref.artifactVersion;
    }
  }
  return opName;
};

const LinkTable = <RowType extends {[key: string]: any}>({
  rows,
  handleRowClick,
}: {
  rows: RowType[];
  handleRowClick: (row: RowType) => void;
}) => {
  const columns = useMemo(() => {
    const row0 = rows[0];
    if (row0 == null) {
      return [];
    }
    const cols = Object.keys(row0).filter(
      k => k !== 'id' && !k.startsWith('_')
    );
    return row0 == null
      ? []
      : cols.map((key, i) => ({
          field: key,
          headerName: key,
          flex: i === 0 ? 1 : undefined,
        }));
  }, [rows]);
  return (
    <Box
      sx={{
        height: 460,
        width: '100%',
        '& .MuiDataGrid-root': {
          border: 'none',
        },
        '& .MuiDataGrid-row': {
          cursor: 'pointer',
        },
      }}>
      <DataGrid
        density="compact"
        rows={rows}
        columns={columns}
        autoPageSize
        // initialState={{
        //   pagination: {
        //     paginationModel: {
        //       pageSize: 10,
        //     },
        //   },
        // }}
        disableRowSelectionOnClick
        onRowClick={params => handleRowClick(params.row as RowType)}
      />
    </Box>
  );
};

const Browse2Home: FC = props => {
  const isAuthenticated = useIsAuthenticated();
  const userEntities = query.useUserEntities(isAuthenticated);
  const rows = useMemo(
    () =>
      userEntities.result.map((entityName, i) => ({
        id: i,
        name: entityName,
      })),
    [userEntities.result]
  );
  const history = useHistory();
  const handleRowClick = useCallback(
    (row: any) => {
      const entityName = row.name;
      history.push(`/${URL_BROWSE2}/${entityName}`);
    },
    [history]
  );
  return (
    <PageEl>
      <PageHeader objectType="Home" />
      <Paper>
        <Typography variant="h6" gutterBottom>
          Entities
        </Typography>
        <LinkTable rows={rows} handleRowClick={handleRowClick} />
      </Paper>
    </PageEl>
  );
};

interface Browse2EntityParams {
  entity: string;
}

const Browse2EntityPage: FC = props => {
  const params = useParams<Browse2EntityParams>();
  const entityProjects = query.useProjectsForEntity(params.entity);
  const rows = useMemo(
    () =>
      entityProjects.result.map((entityProject, i) => ({
        id: i,
        name: entityProject,
      })),
    [entityProjects.result]
  );
  const history = useHistory();
  const handleRowClick = useCallback(
    (row: any) => {
      const projectName = row.name;
      history.push(`/${URL_BROWSE2}/${params.entity}/${projectName}`);
    },
    [history, params.entity]
  );
  return (
    <PageEl>
      <PageHeader objectType="Entity" objectName={params.entity} />
      <Paper>
        <Typography variant="h6" gutterBottom>
          Projects
        </Typography>
        <LinkTable rows={rows} handleRowClick={handleRowClick} />
      </Paper>
    </PageEl>
  );
};

interface Browse2ProjectParams {
  entity: string;
  project: string;
}

const Browse2ProjectPage: FC = props => {
  const params = useParams<Browse2ProjectParams>();
  const rootTypeCounts = query.useProjectAssetCountGeneral(
    params.entity,
    params.project
  );
  const rows = useMemo(
    () =>
      (rootTypeCounts.result ?? [])
        .filter(
          typeInfo =>
            // typeInfo.name !== 'stream_table' &&
            typeInfo.name !== 'OpDef' && typeInfo.name !== 'wandb-history'
        )
        .map((row, i) => ({
          id: i,
          ...row,
        })),
    [rootTypeCounts.result]
  );
  const history = useHistory();
  const handleRowClick = useCallback(
    (row: any) => {
      history.push(
        `/${URL_BROWSE2}/${params.entity}/${params.project}/${row.name}`
      );
    },
    [history, params.entity, params.project]
  );
  return (
    <PageEl>
      <PageHeader objectType="Project" objectName={params.project} />
      <Grid container spacing={3}>
        <Grid item xs={12} sm={6}>
          <Paper>
            <Typography variant="h6" gutterBottom>
              Object Types
            </Typography>
            <LinkTable rows={rows} handleRowClick={handleRowClick} />
          </Paper>
        </Grid>
        <Grid item xs={12} sm={6}>
          <Paper>
            <Typography
              variant="h6"
              gutterBottom
              display="flex"
              justifyContent="space-between">
              Functions
              <Typography variant="h6" component="span">
                <Link
                  to={`/${URL_BROWSE2}/${params.entity}/${params.project}/trace`}>
                  [See all runs]
                </Link>
              </Typography>
            </Typography>
            <Browse2RootObjectType
              entity={params.entity}
              project={params.project}
              rootType="OpDef"
            />
          </Paper>
        </Grid>
      </Grid>
      <div style={{marginBottom: 12}}></div>
      <div style={{marginBottom: 12}}></div>
    </PageEl>
  );
};

interface Browse2RootObjectTypeParams {
  entity: string;
  project: string;
  rootType: string;
}

const Browse2RootObjectType: FC<Browse2RootObjectTypeParams> = ({
  entity,
  project,
  rootType,
}) => {
  const objectsInfo = query.useProjectObjectsOfType(entity, project, rootType);
  const rows = useMemo(
    () =>
      (objectsInfo.result ?? []).map((row, i) => ({
        id: i,
        ...row,
      })),
    [objectsInfo.result]
  );
  const history = useHistory();
  const handleRowClick = useCallback(
    (row: any) => {
      history.push(
        `/${URL_BROWSE2}/${entity}/${project}/${rootType}/${row.name}`
      );
    },
    [history, entity, project, rootType]
  );
  return (
    <>
      <LinkTable rows={rows} handleRowClick={handleRowClick} />
    </>
  );
};

const Browse2ObjectTypePage: FC = props => {
  const params = useParams<Browse2RootObjectTypeParams>();
  return (
    <PageEl>
      <PageHeader objectType="Object Type" objectName={params.rootType} />
      <Paper>
        <Typography variant="h6" gutterBottom>
          {params.rootType + 's'}
        </Typography>
        <Browse2RootObjectType {...params} />
      </Paper>
    </PageEl>
  );
};

interface Browse2RootObjectParams {
  entity: string;
  project: string;
  rootType: string;
  objName: string;
  objVersion: string;
}

const Browse2ObjectPage: FC = props => {
  const params = useParams<Browse2RootObjectParams>();
  // const aliases = query.useObjectAliases(
  //   params.entity,
  //   params.project,
  //   params.objName
  // );
  const versionNames = query.useObjectVersions(
    params.entity,
    params.project,
    params.objName
  );
  const rows = useMemo(
    () =>
      (versionNames.result ?? []).map((row, i) => ({
        id: i,
        name: row,
      })),
    [versionNames.result]
  );
  const history = useHistory();
  const handleRowClick = useCallback(
    (row: any) => {
      history.push(
        `/${URL_BROWSE2}/${params.entity}/${params.project}/${params.rootType}/${params.objName}/${row.name}`
      );
    },
    [history, params.entity, params.objName, params.project, params.rootType]
  );
  return (
    <PageEl>
      <PageHeader objectType={params.rootType} objectName={params.objName} />
      {/* <div>
        Aliases
        {aliases.result.map(alias => (
          <div key={alias}>
            <Link
              to={`/${URL_BROWSE2}/${params.entity}/${params.project}/${params.rootType}/${params.objName}/${alias}`}>
              {alias}
            </Link>
          </div>
        ))}
      </div> */}
      <div>
        <Paper>
          <Typography variant="h6" gutterBottom>
            Versions
          </Typography>
          <LinkTable rows={rows} handleRowClick={handleRowClick} />
        </Paper>
        {/* {versionNames.result.map(version => (
          <div key={version}>
            <Link
              to={`/${URL_BROWSE2}/${params.entity}/${params.project}/${params.rootType}/${params.objName}/${version}`}>
              {version}
            </Link>
          </div>
        ))} */}
      </div>
    </PageEl>
  );
};

interface ObjPath {
  entity: string;
  project: string;
  objName: string;
  objVersion: string;
}

const makeObjRefUri = (objPath: ObjPath) => {
  return `wandb-artifact:///${objPath.entity}/${objPath.project}/${objPath.objName}:${objPath.objVersion}/obj`;
};

interface Browse2RootObjectVersionItemParams {
  entity: string;
  project: string;
  rootType: string;
  objName: string;
  objVersion: string;
  refExtra?: string;
}

const nodeFromExtra = (node: Node, extra: string[]): Node => {
  if (extra.length === 0) {
    return node;
  }
  if (extra[0] === 'index') {
    return nodeFromExtra(
      callOpVeryUnsafe('index', {
        arr: node,
        index: constNumber(parseInt(extra[1])),
      }) as Node,
      extra.slice(2)
    );
  } else if (extra[0] === 'pick') {
    return nodeFromExtra(
      callOpVeryUnsafe('pick', {
        obj: node,
        key: constString(extra[1]),
      }) as Node,
      extra.slice(2)
    );
  }
  return nodeFromExtra(
    callOpVeryUnsafe('Object-__getattr__', {
      self: node,
      name: constString(extra[0]),
    }) as Node,
    extra.slice(1)
  );
};

const callOpName = (call: Call) => {
  if (!call.name.startsWith('wandb-artifact:')) {
    return call.name;
  }
  const ref = parseRef(call.name);
  if (!isWandbArtifactRef(ref)) {
    return call.name;
  }
  return ref.artifactName;
};

const CallEl = styled.div`
  display: flex;
  white-space: nowrap;
  text-overflow: ellipsis;
  overflow: hidden;
  align-items: center;
  cursor: pointer;
`;

const CallViewSmall: FC<{
  call: Call;
  // selected: boolean;
  onClick?: () => void;
}> = ({call, onClick}) => {
  return (
    <Box mb={1}>
      <Typography>
        <CallEl
          onClick={() => {
            if (onClick) {
              onClick();
            }
          }}>
          <Box mr={1}>
            <Chip
              variant="outlined"
              label={callOpName(call)}
              sx={{
                maxWidth: '200px',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            />
          </Box>
          <Typography variant="body2" component="span">
            {monthRoundedTime(call.summary.latency_s, true)}
          </Typography>
        </CallEl>
      </Typography>
    </Box>
  );
};

export const SidebarWrapper = styled.div`
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  box-shadow: 0px 0px 10px rgba(0, 0, 0, 0.2);
  z-index: 100;
`;
SidebarWrapper.displayName = 'S.SidebarWrapper';

type SpanWithChildren = Span & {child_spans: SpanWithChildren[]};

export const SpanTreeDetailsEl = styled.div`
  padding-left: 18px;
`;

const SpanDetails: FC<{call: Call}> = ({call}) => {
  const actualInputs = Object.entries(call.inputs).filter(
    ([k, c]) => c != null && !k.startsWith('_')
  );
  const inputs = _.fromPairs(actualInputs);
  return (
    <div style={{width: '100%'}}>
      <div style={{marginBottom: 24}}>
        <Typography variant="h5" gutterBottom>
          Function
        </Typography>
        <Chip label={call.name} />
      </div>
      <div style={{marginBottom: 24}}>
        <Typography variant="h5" gutterBottom>
          Inputs
        </Typography>
        {isOpenAIChatInput(inputs) ? (
          <OpenAIChatInputView chatInput={inputs} />
        ) : (
          <pre style={{fontSize: 12}}>
            {JSON.stringify(inputs, undefined, 2)}
          </pre>
        )}
      </div>
      <div style={{marginBottom: 24}}>
        <Typography variant="h6" gutterBottom>
          Output
        </Typography>
        {isOpenAIChatOutput(call.output) ? (
          <OpenAIChatOutputView chatOutput={call.output} />
        ) : (
          <pre style={{fontSize: 12}}>
            {JSON.stringify(call.output, undefined, 2)}
          </pre>
        )}
      </div>
      {call.attributes != null && (
        <div style={{marginBottom: 12}}>
          <div>
            <b>Attributes</b>
          </div>
          <pre style={{fontSize: 12}}>
            {JSON.stringify(call.attributes, undefined, 2)}
          </pre>
        </div>
      )}
      <div style={{marginBottom: 12}}>
        <Typography variant="h6" gutterBottom>
          Summary
        </Typography>
        <pre style={{fontSize: 12}}>
          {JSON.stringify(call.summary, undefined, 2)}
        </pre>
      </div>
    </div>
  );
};

const SpanTreeNode: FC<{
  level?: number;
  call: SpanWithChildren;
  selectedSpanId?: string;
  setSelectedSpanId: (spanId: string) => void;
}> = ({call, selectedSpanId, setSelectedSpanId, level}) => {
  const isSelected = selectedSpanId === call.span_id;
  const curLevel = level ?? 0;
  const childLevel = curLevel + 1;
  return (
    <>
      <Box
        ml={-1}
        pl={1 + curLevel * 2}
        mr={-1}
        pr={1}
        sx={{
          '& *:hover': {
            backgroundColor: globals.lightSky,
          },
          backgroundColor: isSelected ? globals.sky : 'inherit',
        }}>
        <CallViewSmall
          call={call}
          onClick={() => setSelectedSpanId(call.span_id)}
        />
      </Box>
      {call.child_spans.map(child => (
        <SpanTreeNode
          level={childLevel}
          call={child}
          selectedSpanId={selectedSpanId}
          setSelectedSpanId={setSelectedSpanId}
        />
      ))}
    </>
  );
};

const VerticalTraceView: FC<{
  traceSpans: Span[];
  selectedSpanId?: string;
  setSelectedSpanId: (spanId: string) => void;
  callStyle: 'full' | 'short';
}> = ({traceSpans, selectedSpanId, setSelectedSpanId}) => {
  const tree = useMemo(
    () => flatToTrees(traceSpans),
    [traceSpans]
  ) as SpanWithChildren[];

  return tree[0] == null ? (
    <div>No trace spans found</div>
  ) : (
    <SpanTreeNode
      call={tree[0]}
      selectedSpanId={selectedSpanId}
      setSelectedSpanId={setSelectedSpanId}
    />
  );
};

type DataGridColumnGroupingModel = Exclude<
  React.ComponentProps<typeof DataGrid>['columnGroupingModel'],
  undefined
>;

const RunsTable: FC<{
  spans: Span[];
}> = ({spans}) => {
  const params = useParams<Browse2RootObjectVersionItemParams>();
  const history = useHistory();
  const tableData = useMemo(() => {
    return spans.map((call: Call) => {
      const argOrder = call.inputs._input_order;
      let args = _.fromPairs(
        Object.entries(call.inputs).filter(
          ([k, c]) => c != null && !k.startsWith('_')
        )
      );
      if (argOrder) {
        args = _.fromPairs(argOrder.map((k: string) => [k, args[k]]));
      }

      return {
        id: call.span_id,
        trace_id: call.trace_id,
        timestamp: call.timestamp,
        latency: monthRoundedTime(call.summary.latency_s, true),
        ..._.mapKeys(
          _.omitBy(args, v => v == null),
          (v, k) => {
            return 'input_' + k;
          }
        ),
        ..._.mapValues(
          _.mapKeys(
            _.omitBy(call.output, v => v == null),
            (v, k) => {
              return 'output_' + k;
            }
          ),
          JSON.stringify
        ),
      };
    });
  }, [spans]);
  const columns = useMemo(() => {
    const cols = [
      {
        field: 'timestamp',
        headerName: 'Timestamp',
      },
      {
        field: 'latency',
        headerName: 'Latency',
      },
    ];
    const colGroupingModel: DataGridColumnGroupingModel = [
      {
        headerName: '',
        groupId: 'timestamp',
        children: [{field: 'timestamp'}],
      },
      {
        headerName: '',
        groupId: 'latency',
        children: [{field: 'latency'}],
      },
    ];
    const row0 = spans[0];
    if (row0 == null) {
      return {cols: [], colGroupingModel: []};
    }

    const inputOrder =
      row0.inputs._arg_order ??
      Object.keys(_.omitBy(row0.inputs, v => v == null)).filter(
        k => !k.startsWith('_')
      );
    const inputGroup: Exclude<
      React.ComponentProps<typeof DataGrid>['columnGroupingModel'],
      undefined
    >[number] = {
      groupId: 'inputs',
      children: [],
    };
    for (const key of inputOrder) {
      cols.push({
        field: 'input_' + key,
        headerName: key,
        flex: 1,
      });
      inputGroup.children.push({field: 'input_' + key});
    }
    colGroupingModel.push(inputGroup);

    const outputOrder = Object.keys(_.omitBy(row0.output, v => v == null));
    const outputGroup: Exclude<
      React.ComponentProps<typeof DataGrid>['columnGroupingModel'],
      undefined
    >[number] = {
      groupId: 'output',
      children: [],
    };
    for (const key of outputOrder) {
      cols.push({
        field: 'output_' + key,
        headerName: key,
        flex: 1,
      });
      outputGroup.children.push({field: 'output_' + key});
    }
    colGroupingModel.push(outputGroup);

    return {cols, colGroupingModel};
  }, [spans]);
  console.log('COL GROUPING MODEL', columns);
  return (
    <Box
      sx={{
        height: 460,
        width: '100%',
        '& .MuiDataGrid-root': {
          border: 'none',
        },
        '& .MuiDataGrid-row': {
          cursor: 'pointer',
        },
      }}>
      <DataGrid
        density="compact"
        experimentalFeatures={{columnGrouping: true}}
        rows={tableData}
        columns={columns.cols}
        columnGroupingModel={columns.colGroupingModel}
        initialState={{
          pagination: {
            paginationModel: {
              pageSize: 10,
            },
          },
        }}
        disableRowSelectionOnClick
        onRowClick={rowParams =>
          history.push(
            `/${URL_BROWSE2}/${params.entity}/${params.project}/trace/${rowParams.row.trace_id}/${rowParams.row.id}`
          )
        }
      />
    </Box>
  );
};

const Browse2Calls: FC<{
  streamId: StreamId;
  filters: CallFilter;
}> = ({streamId, filters}) => {
  const selected = useMemo(() => {
    const streamTableRowsNode = callsTableNode(streamId);
    const filtered = callsTableFilter(streamTableRowsNode, filters);
    return callsTableSelect(filtered);
  }, [filters, streamId]);

  const selectedQuery = useNodeValue(selected);

  const selectedData = selectedQuery.result ?? [];

  return (
    <div style={{width: '100%', height: 500}}>
      <Paper>
        <Typography variant="h6" gutterBottom>
          Runs
        </Typography>
        {filters.inputUris != null && (
          <div
            style={{
              display: 'flex',
              whiteSpace: 'nowrap',
              textOverflow: 'ellipsis',
              overflow: 'hidden',
            }}>
            <FilterList />
            <i>Showing runs where input is one of: </i>
            {filters.inputUris.map((inputUri, i) => (
              <div key={i}>{inputUri}</div>
            ))}
          </div>
        )}
        <RunsTable spans={selectedData} />
      </Paper>
    </div>
  );
};

const Browse2CallsPage: FC = () => {
  const params = useParams<Browse2RootObjectVersionItemParams>();
  const filters: CallFilter = {};
  const query = useQuery();
  let selectedSpan: TraceSpan | undefined = undefined;
  query.forEach((val, key) => {
    if (key === 'op') {
      filters.opUri = val;
    } else if (key === 'inputUri') {
      if (filters.inputUris == null) {
        filters.inputUris = [];
      }
      filters.inputUris.push(val);
    } else if (key === 'traceSpan') {
      const [traceId, spanId] = val.split(',', 2);
      selectedSpan = {traceId, spanId};
    }
  });
  console.log('URL SEL SPAN', selectedSpan);
  return (
    <Browse2Calls
      streamId={{
        entityName: params.entity,
        projectName: params.project,
        streamName: 'stream',
      }}
      filters={filters}
    />
  );
};

const SpanFeedback: FC<{streamId: string; traceId: string; spanId: string}> = ({
  streamId,
  traceId,
  spanId,
}) => {
  return (
    <>
      <TextField
        label="feedback"
        multiline
        fullWidth
        minRows={10}
        maxRows={20}
        sx={{
          backgroundColor: globals.lightYellow,
        }}
      />
      <Box display="flex" justifyContent="flex-end" pt={2}>
        <Button sx={{backgroundColor: globals.lightYellow}}>Update</Button>
      </Box>
    </>
  );
};

const Browse2Trace: FC<{
  streamId: StreamId;
  traceId: string;
  spanId?: string;
  setSelectedSpanId: (spanId: string) => void;
}> = ({streamId, traceId, spanId, setSelectedSpanId}) => {
  const traceSpans = useTraceSpans(streamId, traceId);
  const selectedSpanId = spanId;
  const selectedSpan = useMemo(() => {
    if (selectedSpanId == null) {
      return undefined;
    }
    return traceSpans.filter(ts => ts.span_id === selectedSpanId)[0];
  }, [selectedSpanId, traceSpans]);
  const [tabId, setTabId] = React.useState(0);
  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabId(newValue);
  };
  return (
    <Grid container spacing={1} alignItems="flex-start">
      <Grid xs={3} item>
        <Paper>
          <VerticalTraceView
            traceSpans={traceSpans}
            selectedSpanId={selectedSpanId}
            setSelectedSpanId={setSelectedSpanId}
            callStyle="short"
          />
        </Paper>
      </Grid>
      <Grid xs={9} item>
        {selectedSpanId != null && (
          <Paper>
            <Tabs value={tabId} onChange={handleTabChange}>
              <Tab label="Run" />
              <Tab
                label="Feedback"
                sx={{backgroundColor: globals.lightYellow}}
              />
              <Tab
                label="Datasets"
                sx={{backgroundColor: globals.lightYellow}}
              />
            </Tabs>
            <Box pt={2}>
              {tabId === 0 &&
                (selectedSpan == null ? (
                  <div>Span not found</div>
                ) : (
                  <SpanDetails call={selectedSpan} />
                ))}
              {tabId === 1 && (
                <SpanFeedback
                  streamId={streamId.streamName}
                  traceId={traceId}
                  spanId={selectedSpanId}
                />
              )}
              {tabId === 2 && (
                <>
                  <Typography variant="h6" gutterBottom>
                    Appears in datasets
                  </Typography>
                  <Box
                    mb={4}
                    sx={{
                      background: globals.lightYellow,
                      height: 200,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}>
                    Placeholder
                  </Box>
                  <Button sx={{backgroundColor: globals.lightYellow}}>
                    Add to dataset
                  </Button>
                </>
              )}
            </Box>
          </Paper>
        )}
      </Grid>
    </Grid>
  );
};

interface Browse2TracePageParams {
  entity: string;
  project: string;
  traceId: string;
  spanId?: string;
}

const Browse2TracePage: FC = () => {
  const params = useParams<Browse2TracePageParams>();
  const history = useHistory();
  const setSelectedSpanId = useCallback(
    (spanId: string) =>
      history.push(
        `/${URL_BROWSE2}/${params.entity}/${params.project}/trace/${params.traceId}/${spanId}`
      ),
    [history, params.entity, params.project, params.traceId]
  );
  return (
    <PageEl>
      <PageHeader
        objectType="Trace"
        objectName={
          params.traceId + params.spanId != null ? '/' + params.spanId : ''
        }
      />
      <Browse2Trace
        streamId={{
          entityName: params.entity,
          projectName: params.project,
          streamName: 'stream',
        }}
        traceId={params.traceId}
        spanId={params.spanId}
        setSelectedSpanId={setSelectedSpanId}
      />
    </PageEl>
  );
};

const Browse2Traces: FC<{
  streamId: StreamId;
  selectedSpan?: TraceSpan;
}> = ({streamId, selectedSpan}) => {
  const tracesNode = useMemo(() => {
    const callsRowsNode = callsTableNode(streamId);
    return callsTableSelectTraces(callsRowsNode);
  }, [streamId]);
  const tracesQuery = useNodeValue(tracesNode);
  const traces = tracesQuery.result ?? [];
  return (
    <div>
      {traces.map(trace => (
        <div>
          <Link
            to={`/${URL_BROWSE2}/${streamId.entityName}/${streamId.projectName}/trace/${trace.trace_id}`}>
            {trace.trace_id}
          </Link>
          : {trace.span_count}
        </div>
      ))}
    </div>
  );
};

interface Browse2TracesPageParams {
  entity: string;
  project: string;
}

const Browse2TracesPage: FC = () => {
  const params = useParams<Browse2TracesPageParams>();
  const filters: CallFilter = {};
  const query = useQuery();
  let selectedSpan: TraceSpan | undefined = undefined;
  query.forEach((val, key) => {
    if (key === 'op') {
      filters.opUri = val;
    } else if (key === 'inputUri') {
      if (filters.inputUris == null) {
        filters.inputUris = [];
      }
      filters.inputUris.push(val);
    } else if (key === 'traceSpan') {
      const [traceId, spanId] = val.split(',', 2);
      selectedSpan = {traceId, spanId};
    }
  });
  return (
    <PageEl>
      <Browse2Traces
        streamId={{
          entityName: params.entity,
          projectName: params.project,
          streamName: 'stream',
        }}
        selectedSpan={selectedSpan}
      />
    </PageEl>
  );
};

const Browse2OpDefPage: FC = () => {
  const params = useParams<Browse2RootObjectVersionItemParams>();
  const uri = makeObjRefUri(params);
  const query = useQuery();
  const filters = useMemo(() => {
    const filt: CallFilter = {opUri: uri};
    query.forEach((val, key) => {
      if (key === 'op') {
        filt.opUri = val;
      } else if (key === 'inputUri') {
        if (filt.inputUris == null) {
          filt.inputUris = [];
        }
        filt.inputUris.push(val);
      }
    });
    return filt;
  }, [query, uri]);
  const streamId = useMemo(
    () => ({
      entityName: params.entity,
      projectName: params.project,
      streamName: 'stream',
    }),
    [params.entity, params.project]
  );

  const firstCall = useFirstCall(streamId, uri);
  const opSignature = useOpSignature(streamId, uri);

  // const firstCall = useMemo(() => {
  //   const streamTableRowsNode = callsTableNode(streamId);
  //   const filtered = callsTableFilter(streamTableRowsNode, {opUri: uri});
  //   const selected = callsTableSelect(filtered);
  //   return opIndex({arr: selected, index: constNumber(0)});
  // }, [streamId, uri]);
  return (
    <div>
      <Box marginBottom={2}>
        <Paper>
          <Typography variant="h6" gutterBottom>
            Call
          </Typography>
          <Box sx={{width: 400}}>
            {opSignature.result != null &&
              Object.keys(opSignature.result.inputTypes).map(k => (
                <Box mb={2}>
                  <TextField
                    label={k}
                    fullWidth
                    value={
                      firstCall.result != null
                        ? firstCall.result.inputs[k]
                        : undefined
                    }
                  />
                </Box>
              ))}
          </Box>
          <Box pt={1}>
            <Button
              variant="outlined"
              sx={{backgroundColor: globals.lightYellow}}>
              Execute
            </Button>
          </Box>
        </Paper>
      </Box>
      <Browse2Calls streamId={streamId} filters={filters} />
    </div>
  );
};

const opPageUrl = (opUri: string) => {
  const parsed = parseRef(opUri);
  if (!isWandbArtifactRef(parsed)) {
    throw new Error('non wandb artifact ref not yet handled');
  }
  return `/${URL_BROWSE2}/${parsed.entityName}/${parsed.projectName}/OpDef/${parsed.artifactName}/${parsed.artifactVersion}`;
};

const Browse2RootObjectVersionUsers: FC<{uri: string}> = ({uri}) => {
  const params = useParams<Browse2RootObjectVersionItemParams>();
  const calledOpCountsNode = useMemo(() => {
    const streamTableRowsNode = callsTableNode({
      entityName: params.entity,
      projectName: params.project,
      streamName: 'stream',
    });
    const filtered = callsTableFilter(streamTableRowsNode, {
      inputUris: [uri],
    });
    return callsTableOpCounts(filtered);
  }, [params.entity, params.project, uri]);
  const calledOpCountsQuery = useNodeValue(calledOpCountsNode);

  const rows = useMemo(() => {
    const calledOpCounts = calledOpCountsQuery.result ?? [];
    return calledOpCounts.map((row: any, i: number) => ({
      id: i,
      _name: row.name,
      name: opDisplayName(row.name),
      count: row.count,
    }));
  }, [calledOpCountsQuery]);
  const history = useHistory();
  const handleRowClick = useCallback(
    (row: any) => {
      history.push(
        `${opPageUrl(row._name)}?inputUri=${encodeURIComponent(uri)}`
      );
    },
    [history, uri]
  );

  return <LinkTable rows={rows} handleRowClick={handleRowClick} />;
};

const Browse2ObjectVersionItemPage: FC = props => {
  const params = useParams<Browse2RootObjectVersionItemParams>();
  const uri = makeObjRefUri(params);
  const history = useHistory();
  const itemNode = useMemo(() => {
    const objNode = opGet({uri: constString(uri)});
    if (params.refExtra == null) {
      return objNode;
    }
    const extraFields = params.refExtra.split('/');
    return nodeFromExtra(objNode, extraFields);
  }, [uri, params.refExtra]);
  const weave = useWeaveContext();
  const {stack} = usePanelContext();
  const [panel, setPanel] = React.useState<ChildPanelConfig | undefined>();

  const makeBoardFromNode = useMakeLocalBoardFromNode();

  const [isGenerating, setIsGenerating] = useState(false);

  // console.log('ITEM QUERY', useNodeValue(itemNode));

  const onNewBoard = useCallback(async () => {
    setIsGenerating(true);
    const refinedItemNode = await weave.refineNode(itemNode, stack);
    makeBoardFromNode(SEED_BOARD_OP_NAME, refinedItemNode, newDashExpr => {
      setIsGenerating(false);
      window.open('/?exp=' + weave.expToString(newDashExpr), '_blank');
    });
  }, [itemNode, makeBoardFromNode, stack, weave]);

  useEffect(() => {
    const doInit = async () => {
      const panel = await initPanel(
        weave,
        itemNode,
        undefined,
        undefined,
        stack
      );
      setPanel(panel);
    };
    doInit();
  }, [itemNode, stack, weave]);
  const handleUpdateInput = useCallback(
    (newExpr: Node) => {
      const linearNodes = linearize(newExpr);
      if (linearNodes == null) {
        console.log("Can't linearize nodes for updateInput", newExpr);
        return;
      }
      let newExtra: string[] = [];
      for (const subNode of linearNodes) {
        if (subNode.fromOp.name === 'Object-__getattr__') {
          if (!isConstNode(subNode.fromOp.inputs.name)) {
            console.log('updateInput can only handle const keys for now');
            return;
          }
          newExtra.push(subNode.fromOp.inputs.name.val);
        } else if (subNode.fromOp.name === 'index') {
          if (!isConstNode(subNode.fromOp.inputs.index)) {
            console.log('updateInput can only handle const index for now');
            return;
          }
          newExtra.push('index');
          newExtra.push(subNode.fromOp.inputs.index.val.toString());
        } else if (subNode.fromOp.name === 'pick') {
          if (!isConstNode(subNode.fromOp.inputs.key)) {
            console.log('updateInput can only handle const keys for now');
            return;
          }
          newExtra.push('pick');
          newExtra.push(subNode.fromOp.inputs.key.val);
        }
      }
      let newUri = `/${URL_BROWSE2}/${params.entity}/${params.project}/${params.rootType}/${params.objName}/${params.objVersion}`;
      if (params.refExtra != null) {
        newUri += `/${params.refExtra}`;
      }
      newUri += `/${newExtra.join('/')}`;
      history.push(newUri);
    },
    [
      history,
      params.entity,
      params.objName,
      params.objVersion,
      params.project,
      params.rootType,
      params.refExtra,
    ]
  );
  return (
    <PageEl>
      <PageHeader
        objectType={
          params.rootType === 'OpDef'
            ? 'Op'
            : params.rootType === 'stream_table'
            ? 'Traces'
            : params.rootType
        }
        objectName={
          params.objName +
          ':' +
          params.objVersion +
          (params.refExtra ? '/' + params.refExtra : '')
        }
      />
      <Box marginBottom={2}>
        <Paper>
          <Grid container spacing={1} alignItems="center">
            <Grid xs={10} item>
              <TextField
                label="Weave Expression"
                value={weave.expToString(itemNode)}
                fullWidth
              />
            </Grid>
            <Grid xs={2} item>
              <Button style={{marginLeft: 12}} onClick={onNewBoard}>
                Open in board
              </Button>
            </Grid>
          </Grid>
          {/* <FormControl>
          <InputLabel>Expr</InputLabel>
          <Input value={weave.expToString(itemNode)} />
        </FormControl> */}
        </Paper>
      </Box>
      {params.rootType === 'stream_table' ? (
        <Browse2CallsPage />
      ) : params.rootType === 'OpDef' ? (
        <Browse2OpDefPage />
      ) : (
        <Grid container spacing={3}>
          <Grid item xs={8}>
            <Paper>
              <Typography variant="h6" gutterBottom>
                Value
              </Typography>
              <Box p={2}>
                {panel != null && (
                  <ChildPanel
                    config={panel}
                    updateConfig={newConfig => setPanel(newConfig)}
                    updateInput={handleUpdateInput}
                    passthroughUpdate
                  />
                )}
              </Box>
            </Paper>
          </Grid>
          <Grid item xs={4}>
            <Paper>
              <Typography variant="h6" gutterBottom>
                Used in runs
              </Typography>
              <Browse2RootObjectVersionUsers uri={uri} />
            </Paper>
          </Grid>
        </Grid>
      )}
    </PageEl>
  );
};

interface Browse2Params {
  entity?: string;
  project?: string;
  rootType?: string;
  objName?: string;
  objVersion?: string;
  refExtra?: string;
}

const Link = props => <MaterialLink {...props} component={RouterLink} />;

const AppBarLink = props => (
  <MaterialLink
    sx={{
      color: theme => theme.palette.getContrastText(theme.palette.primary.main),
      '&:hover': {
        color: theme =>
          theme.palette.getContrastText(theme.palette.primary.dark),
      },
    }}
    {...props}
    component={RouterLink}
  />
);

const Browse2Breadcrumbs: FC = props => {
  const params = useParams<Browse2Params>();
  return (
    <Breadcrumbs>
      {params.entity && (
        <AppBarLink to={`/${URL_BROWSE2}/${params.entity}`}>
          {params.entity}
        </AppBarLink>
      )}
      {params.project && (
        <AppBarLink to={`/${URL_BROWSE2}/${params.entity}/${params.project}`}>
          {params.project}
        </AppBarLink>
      )}
      {params.rootType && (
        <AppBarLink
          to={`/${URL_BROWSE2}/${params.entity}/${params.project}/${params.rootType}`}>
          {params.rootType}
        </AppBarLink>
      )}
      {params.objName && (
        <AppBarLink
          to={`/${URL_BROWSE2}/${params.entity}/${params.project}/${params.rootType}/${params.objName}`}>
          {params.objName}
        </AppBarLink>
      )}
      {params.objVersion && (
        <AppBarLink
          to={`/${URL_BROWSE2}/${params.entity}/${params.project}/${params.rootType}/${params.objName}/${params.objVersion}`}>
          {params.objVersion}
        </AppBarLink>
      )}
    </Breadcrumbs>
  );
};

const RefExtraBreadCrumbs: FC<{refExtra: string}> = ({refExtra}) => {
  const params = useParams<Browse2Params>();
  const refFields = refExtra.split('/');
  return (
    <>
      {refFields.map((field, idx) => {
        return (
          <>
            {' / '}
            {field === 'index' ? (
              <span>row</span>
            ) : field === 'pick' ? (
              <span>col</span>
            ) : (
              <Link
                to={`/${URL_BROWSE2}/${params.entity}/${params.project}/${
                  params.rootType
                }/${params.objName}/${params.objVersion}/${refFields
                  .slice(0, idx + 1)
                  .join('/')}`}>
                {field}
              </Link>
            )}
          </>
        );
      })}
    </>
  );
};

const Paper = (props: React.ComponentProps<typeof MaterialPaper>) => {
  return (
    <MaterialPaper
      sx={{
        padding: theme => theme.spacing(2),
      }}
      {...props}>
      {props.children}
    </MaterialPaper>
  );
};

export const Browse2: FC = props => {
  return (
    <div
      style={{height: '100vh', overflow: 'auto', backgroundColor: '#fafafa'}}>
      <AppBar position="static">
        <Toolbar>
          <IconButton
            component={RouterLink}
            to={`/${URL_BROWSE2}`}
            sx={{
              color: theme =>
                theme.palette.getContrastText(theme.palette.primary.main),
              '&:hover': {
                color: theme =>
                  theme.palette.getContrastText(theme.palette.primary.dark),
              },
              marginRight: theme => theme.spacing(2),
            }}>
            <Home />
          </IconButton>
          <Browse2Breadcrumbs />
        </Toolbar>
      </AppBar>
      <Container maxWidth="xl">
        <Box sx={{height: 40}} />
        <Switch>
          <Route
            path={`/${URL_BROWSE2}/:entity/:project/trace/:traceId/:spanId?`}>
            <Browse2TracePage />
          </Route>
          <Route path={`/${URL_BROWSE2}/:entity/:project/trace`}>
            <Browse2TracesPage />
          </Route>
          <Route
            path={`/${URL_BROWSE2}/:entity/:project/:rootType/:objName/:objVersion/:refExtra*`}>
            <Browse2ObjectVersionItemPage />
          </Route>
          <Route path={`/${URL_BROWSE2}/:entity/:project/:rootType/:objName`}>
            <Browse2ObjectPage />
          </Route>
          <Route path={`/${URL_BROWSE2}/:entity/:project/:rootType`}>
            <Browse2ObjectTypePage />
          </Route>
          <Route path={`/${URL_BROWSE2}/:entity/:project`}>
            <Browse2ProjectPage />
          </Route>
          <Route path={`/${URL_BROWSE2}/:entity`}>
            <Browse2EntityPage />
          </Route>
          <Route path={`/${URL_BROWSE2}`}>
            <Browse2Home />
          </Route>
        </Switch>
      </Container>
    </div>
  );
};
