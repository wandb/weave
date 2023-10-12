import * as _ from 'lodash';
import React, {FC, useCallback, useMemo, useState} from 'react';
import {
  Switch,
  Route,
  Link as RouterLink,
  useParams,
  useHistory,
} from 'react-router-dom';

import styled from 'styled-components';
import * as globals from '@wandb/weave/common/css/globals.styles';
import {URL_BROWSE2} from '../../../urls';
import * as query from './query';
import {isWandbArtifactRef, parseRef} from '@wandb/weave/react';
import {monthRoundedTime} from '@wandb/weave/time';
import {flatToTrees} from '../../Panel2/PanelTraceTree/util';
import {Call, CallFilter, Span, StreamId, TraceSpan} from './Browse2/callTree';

import {Link, Paper} from './Browse2/CommonLib';
import {useTraceSpans, useTraceSummaries} from './Browse2/callTreeHooks';
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
  Container,
  Chip,
  Tabs,
  Tab,
  TextField,
} from '@mui/material';
import {Home} from '@mui/icons-material';
import {LicenseInfo} from '@mui/x-license-pro';
import {AddRowToTable} from './Browse2/AddRow';
import {Browse2HomePage} from './Browse2/Browse2HomePage';
import {Browse2EntityPage} from './Browse2/Browse2EntityPage';
import {PageEl} from './Browse2/CommonLib';
import {PageHeader} from './Browse2/CommonLib';
import {LinkTable} from './Browse2/LinkTable';
import {Browse2ProjectPage} from './Browse2/Browse2ProjectPage';
import {Browse2ObjectTypePage} from './Browse2/Browse2ObjectTypePage';
import {Browse2ObjectVersionItemPage} from './Browse2/Browse2ObjectVersionItemPage';
import {useQuery} from './Browse2/CommonLib';

LicenseInfo.setLicenseKey(
  '7684ecd9a2d817a3af28ae2a8682895aTz03NjEwMSxFPTE3MjgxNjc2MzEwMDAsUz1wcm8sTE09c3Vic2NyaXB0aW9uLEtWPTI='
);

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
                backgroundColor:
                  call.status_code === 'ERROR' ? globals.warning : undefined,
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
        <Box mb={2}>
          <Box display="flex" justifyContent="space-between">
            <Typography variant="h5" gutterBottom>
              Function
            </Typography>
            {isOpenAIChatInput(inputs) && (
              <Button
                variant="outlined"
                sx={{backgroundColor: globals.lightYellow}}>
                Open in LLM Playground
              </Button>
            )}
          </Box>
          <Chip label={call.name} />
        </Box>
        <Typography variant="body2" gutterBottom>
          Status: {call.status_code}
        </Typography>
        {call.exception != null && (
          <Typography variant="body2" gutterBottom>
            {call.exception}
          </Typography>
        )}
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
  const simpleInputOutputValue = useMemo(() => {
    if (selectedSpan == null) {
      return undefined;
    }
    const simpleInputOrder =
      selectedSpan.inputs._input_order ??
      Object.keys(selectedSpan.inputs).filter(
        k => !k.startsWith('_') && k !== 'self'
      );
    const simpleInputs = _.fromPairs(
      simpleInputOrder
        .map(k => [k, selectedSpan.inputs[k]])
        .filter(([k, v]) => v != null)
    );

    let output = selectedSpan.output;
    if (output == null) {
      output = {_result: null};
    }
    const simpleOutput = _.fromPairs(
      Object.entries(output).filter(([k, v]) => v != null)
    );

    return {
      input: simpleInputs,
      output: simpleOutput,
    };
  }, [selectedSpan]);
  const [tabId, setTabId] = React.useState(0);
  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabId(newValue);
  };

  const [addRowToTableOpen, setAddRowToTableOpen] = useState(false);

  return (
    <Grid container spacing={2} alignItems="flex-start">
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
              <Tab label="Datasets" />
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
                  <Button
                    variant="outlined"
                    onClick={() => setAddRowToTableOpen(true)}>
                    Add to dataset
                  </Button>
                  {addRowToTableOpen && (
                    <AddRowToTable
                      entityName={streamId.entityName}
                      open={addRowToTableOpen}
                      handleClose={() => setAddRowToTableOpen(false)}
                      initialFormState={{
                        projectName: streamId.projectName,
                        row: simpleInputOutputValue,
                      }}
                    />
                  )}
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
        actions={
          <Box display="flex" alignItems="flex-start">
            <Button
              variant="outlined"
              sx={{marginRight: 3, backgroundColor: globals.lightYellow}}
              onClick={() => console.log('new board trace')}>
              Open in board
            </Button>
            <Button
              variant="outlined"
              sx={{backgroundColor: globals.lightYellow, marginRight: 3}}>
              Compare
            </Button>
          </Box>
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
  const traces = useTraceSummaries(streamId);
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

interface Browse2Params {
  entity?: string;
  project?: string;
  rootType?: string;
  objName?: string;
  objVersion?: string;
  refExtra?: string;
}

const AppBarLink = (props: React.ComponentProps<typeof RouterLink>) => (
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
  const refFields = params.refExtra?.split('/') ?? [];
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
      {refFields.map((field, idx) =>
        field === 'index' ? (
          <Typography>row</Typography>
        ) : field === 'pick' ? (
          <Typography>col</Typography>
        ) : (
          <AppBarLink
            to={`/${URL_BROWSE2}/${params.entity}/${params.project}/${
              params.rootType
            }/${params.objName}/${params.objVersion}/${refFields
              .slice(0, idx + 1)
              .join('/')}`}>
            {field}
          </AppBarLink>
        )
      )}
    </Breadcrumbs>
  );
};

export const Browse2: FC = props => {
  return (
    <div
      style={{
        height: '100vh',
        overflow: 'auto',
        backgroundColor: '#fafafa',
      }}>
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
            <Browse2HomePage />
          </Route>
        </Switch>
      </Container>
    </div>
  );
};
