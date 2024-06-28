import {Box, FormControl} from '@material-ui/core';
import {Circle} from '@mui/icons-material';
import {Alert, Autocomplete} from '@mui/material';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import * as Plotly from 'plotly.js';
import React, {
  FC,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
} from 'react';
import {useHistory} from 'react-router-dom';

import {Button} from '../../../../../Button';
import {
  useWeaveflowCurrentRouteContext,
  WeaveflowPeekContext,
} from '../../context';
import {StyledTextField} from '../../StyledTextField';
import {ObjectViewerSection} from '../CallPage/ObjectViewerSection';
import {useEvaluationsFilter} from '../CallsPage/CallsPage';
import {CallsTable} from '../CallsPage/CallsTable';
import {CallLink, ObjectVersionLink, opNiceName} from '../common/Links';
import {SimplePageLayout} from '../common/SimplePageLayout';
import {opVersionRefOpName} from '../wfReactInterface/utilities';
import {
  EvaluationEvaluateCallSchema,
  evaluationMetrics,
  useEvaluationCalls,
  useModelsFromEvaluationCalls,
} from './evaluations';
import MetricTile from './MetricTile';

type CompareEvaluationsPageProps = {
  entity: string;
  project: string;
  evaluationCallIds: string[];
};

export const CompareEvaluationsPage: React.FC<
  CompareEvaluationsPageProps
> = props => {
  if (props.evaluationCallIds.length !== 2) {
    return <div>Need exactly 2 evaluations to compare</div>;
  }
  return (
    <SimplePageLayout
      title={'Compare Evaluations'}
      hideTabsIfSingle
      tabs={[
        {
          label: 'All',
          content: <CompareEvaluationsPageInner {...props} />,
        },
      ]}
      headerExtra={<HeaderExtra {...props} />}
    />
  );
};

const HeaderExtra: React.FC<CompareEvaluationsPageProps> = props => {
  const {isPeeking} = useContext(WeaveflowPeekContext);
  return (
    <>
      {!isPeeking ? (
        <ReturnToEvaluationsButton
          entity={props.entity}
          project={props.project}
        />
      ) : null}
    </>
  );
};

const ReturnToEvaluationsButton: FC<{entity: string; project: string}> = ({
  entity,
  project,
}) => {
  const history = useHistory();
  const router = useWeaveflowCurrentRouteContext();
  const evaluationsFilter = useEvaluationsFilter(entity, project);
  const onClick = useCallback(() => {
    history.push(router.callsUIUrl(entity, project, evaluationsFilter));
  }, [entity, evaluationsFilter, history, project, router]);
  return (
    <Box
      sx={{
        height: '100%',
        display: 'flex',
        alignItems: 'center',
      }}>
      <Button
        className="mx-16"
        style={{
          marginLeft: '0px',
        }}
        size="medium"
        variant="secondary"
        onClick={onClick}
        icon="back">
        Return to Evaluations
      </Button>
    </Box>
  );
};

const PlotlyScatterPlot: React.FC<{}> = () => {
  const divRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const trace2 = {
      x: [2, 3, 4, 5],
      y: [16, 5, 11, 9],
      mode: 'markers',
      type: 'scatter',
      marker: {color: 'orange', size: 12},
    };

    const trace3 = {
      x: [1, 2, 3, 4],
      y: [12, 9, 15, 12],
      mode: 'markers',
      type: 'scatter',
      marker: {color: 'blue', size: 12},
    };

    const data = [trace2, trace3];
    Plotly.newPlot(
      divRef.current as any,
      data as any,
      {
        height: 300,
        title: '',
        margin: {
          l: 20, // legend
          r: 0,
          b: 20, // legend
          t: 0,
          pad: 0,
        },
      },
      {
        displayModeBar: false,
        responsive: true,
      }
    );
  }, []);

  return (
    <Box
      sx={{
        height: '300',
        width: '100%',
      }}>
      <div ref={divRef}></div>
    </Box>
  );
};

const CompareEvaluationsPageInner: React.FC<
  CompareEvaluationsPageProps
> = props => {
  const calls = useEvaluationCalls(
    props.entity,
    props.project,
    props.evaluationCallIds
  );
  const hasMoreThanOneEval = useMemo(() => {
    return new Set(calls.map(call => call.inputs.self)).size > 1;
  }, [calls]);
  const evalMetrics = useMemo(() => {
    return evaluationMetrics(calls).filter(
      metric => metric.values.filter(v => v != null).length === 2
    );
  }, [calls]);
  const callsFilter = useMemo(() => {
    return {parentId: calls[0] ? calls[0].id : null};
  }, [calls]);

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        gridGap: 10,
        height: '100%',
        width: '100%',
        overflow: 'auto',
      }}>
      <div
        style={{
          width: '100%',
          backgroundColor: '#eee',
          padding: '10px',
          overflowY: 'hidden',
          overflowX: 'auto',
          display: 'flex',
          flexDirection: 'row',
          gridGap: 10,
          flex: '0 0 auto',
        }}>
        {evalMetrics.map(metric => {
          const val = metric.values[1] - metric.values[0];
          const isGood = metric.lowerIsBetter ? val <= 0 : val >= 0;
          const pathParts = pathToParts(metric.path);
          return (
            <Box
              key={metric.path}
              sx={{
                width: '300px',
                flex: '1 0 auto',
              }}>
              <MetricTile
                title={pathParts.title}
                subtitle={pathParts.subtitle ?? ''}
                mainMetric={val}
                isGood={isGood}
                unit={metric.unit}
                subMetric1={{
                  label: 'Baseline',
                  value: metric.values[0],
                }}
                subMetric2={{
                  label: 'Challenger',
                  value: metric.values[1],
                }}
              />
            </Box>
          );
        })}
      </div>
      <Box
        sx={{
          display: 'grid',
          width: '100%',
          height: '100%',
          gridGap: 10,
          gridTemplateColumns: '230px auto',
          padding: 10,
          overflow: 'auto',
        }}>
        {hasMoreThanOneEval && (
          <Box
            sx={{
              gridColumn: '1 / span 2',
            }}>
            <Alert severity="warning">
              The selected evaluations have different Datasets and/or Scoring
              functions, therefore aggregate metrics may not be apples-to-apples
              comparisons.
            </Alert>
          </Box>
        )}
        {/* <Box
          sx={{
            fontWeight: 'bold',
            fontSize: 24,
            padding: 10,
            textAlign: 'center',
          }}>
          <h3>Summary Metrics</h3>
        </Box>
        <BasicTable /> */}
        <Box
          sx={{
            fontWeight: 'bold',
            fontSize: 24,
            padding: 10,
            textAlign: 'center',
          }}>
          <h3>Model Properties</h3>
        </Box>
        <BasicTable calls={calls} />
        {/* <Box></Box> */}
        <Box
          sx={{
            fontWeight: 'bold',
            fontSize: 24,
            padding: 10,
            textAlign: 'center',
            display: 'flex',
            flexDirection: 'column',
            gridGap: 10,
          }}>
          <h3>Compare Models</h3>
          <FormControl fullWidth>
            <Autocomplete
              // PaperComponent={paperProps => <StyledPaper {...paperProps} />}
              size="small"
              // Temp disable multiple for simplicity - may want to re-enable
              // multiple
              limitTags={1}
              // disabled={Object.keys(frozenFilter ?? {}).includes('opVersions')}
              value={''}
              onChange={(event, newValue) => {
                // console.log('onChange', newValue);
              }}
              options={[]}
              renderInput={renderParams => (
                <StyledTextField
                  {...renderParams}
                  label={'Dimension 1'}
                  sx={{maxWidth: '350px'}}
                />
              )}
              // getOptionLabel={option => {
              //   return opVersionOptions[option]?.title ?? 'loading...';
              // }}
              // disableClearable={
              //   selectedOpVersionOption === ALL_TRACES_OR_CALLS_REF_KEY
              // }
              // groupBy={option => opVersionOptions[option]?.group}
              // options={Object.keys(opVersionOptions)}
            />
          </FormControl>
          <FormControl fullWidth>
            <Autocomplete
              // PaperComponent={paperProps => <StyledPaper {...paperProps} />}
              size="small"
              // Temp disable multiple for simplicity - may want to re-enable
              // multiple
              limitTags={1}
              // disabled={Object.keys(frozenFilter ?? {}).includes('opVersions')}
              value={''}
              onChange={(event, newValue) => {
                // console.log('onChange', newValue);
              }}
              options={[]}
              renderInput={renderParams => (
                <StyledTextField
                  {...renderParams}
                  label={'Dimension 2'}
                  sx={{maxWidth: '350px'}}
                />
              )}
              // getOptionLabel={option => {
              //   return opVersionOptions[option]?.title ?? 'loading...';
              // }}
              // disableClearable={
              //   selectedOpVersionOption === ALL_TRACES_OR_CALLS_REF_KEY
              // }
              // groupBy={option => opVersionOptions[option]?.group}
              // options={Object.keys(opVersionOptions)}
            />
          </FormControl>
        </Box>
        <Box
          sx={{
            height: '300px',
            width: '100%',
          }}>
          <PlotlyScatterPlot />
        </Box>
        <Box>Model Predictions and Scores</Box>
        <Box sx={{height: '600px', width: '100%', overflow: 'hidden'}}>
          {calls[0] && (
            <CallsTable
              entity={props.entity}
              project={props.project}
              frozenFilter={callsFilter}
              hideControls
            />
          )}
        </Box>
      </Box>
    </Box>
  );
};

const pathToParts = (path: string) => {
  if (!path.includes('.')) {
    return {title: path, subtitle: null};
  }
  const parts = path.split('.');
  return {
    title: parts[parts.length - 1],
    subtitle: parts.slice(0, -1).join('.'),
  };
};

const TitleWithDot: React.FC<{title: string; color: string}> = ({
  title,
  color,
}) => {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'end',
      }}>
      {title}
      <Circle
        sx={{
          color: {color},
          height: '12px',
        }}
      />
    </Box>
  );
};

const BaselineTitle: React.FC = () => {
  return <TitleWithDot title={'Baseline'} color={'orange'} />;
};

const ChallengerTitle: React.FC = () => {
  return <TitleWithDot title={'Challenger'} color={'blue'} />;
};

const BasicTable: React.FC<{calls: EvaluationEvaluateCallSchema[]}> = props => {
  const models = useModelsFromEvaluationCalls(props.calls);
  // console.log(props.calls, models);
  return (
    // <TableContainer component={Paper}>
    <Table sx={{minWidth: 650}} size="small">
      <TableHead>
        <TableRow>
          <TableCell></TableCell>
          <TableCell align="right">
            <BaselineTitle />
          </TableCell>
          <TableCell align="right">
            <ChallengerTitle />
          </TableCell>
        </TableRow>
        <TableRow>
          <TableCell>Evaluation Run</TableCell>
          {props.calls.map(call => {
            return (
              <TableCell align="right">
                <CallLink
                  entityName={call.project_id.split('/')[0]}
                  projectName={call.project_id.split('/')[1]}
                  opName={opNiceName(opVersionRefOpName(call.op_name))}
                  callId={call.id}
                  fullWidth={true}
                />
              </TableCell>
            );
          })}
        </TableRow>
        <TableRow>
          <TableCell>Model Object</TableCell>
          <TableCell align="right">
            <ObjectVersionLink
              entityName={'wandb-smle'}
              projectName={'weave-rag-lc-demo'}
              objectName={'RagModel'}
              version={'j5VetZto0f9017qA8vzz6jox1Gs3n8wtAHGYUFXEQws'}
              versionIndex={8}
              fullWidth={true}
            />
          </TableCell>
          <TableCell align="right">
            <ObjectVersionLink
              entityName={'wandb-smle'}
              projectName={'weave-rag-lc-demo'}
              objectName={'RagModel'}
              version={'j5VetZto0f9017qA8vzz6jox1Gs3n8wtAHGYUFXEQws'}
              versionIndex={8}
              fullWidth={true}
            />
          </TableCell>
        </TableRow>
      </TableHead>
      <TableBody>
        <TableRow sx={{'&:last-child td, &:last-child th': {border: 0}}}>
          <TableCell component="th" scope="row">
            Model Details
          </TableCell>
          {models.map((model, ndx) => {
            // TODO: make this a multi-viewer that only shows diffs
            return (
              <TableCell key={ndx}>
                <ObjectViewerSection
                  title=""
                  data={models[0] ?? {}}
                  noHide
                  isExpanded
                />
              </TableCell>
            );
          })}
        </TableRow>
      </TableBody>
    </Table>
    // </TableContainer>
  );
};
