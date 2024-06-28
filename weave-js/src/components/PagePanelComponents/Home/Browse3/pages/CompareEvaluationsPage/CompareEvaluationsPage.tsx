import {Box, BoxProps, FormControl} from '@material-ui/core';
import {Circle} from '@mui/icons-material';
import {Alert, Autocomplete, Skeleton} from '@mui/material';
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

import {
  CACTUS_500,
  MOON_300,
  MOON_600,
  MOON_800,
  TEAL_500,
} from '../../../../../../common/css/color.styles';
import {hexToRGB} from '../../../../../../common/css/utils';
import {parseRef, WeaveObjectRef} from '../../../../../../react';
import {Button} from '../../../../../Button';
import {Icon, IconNames} from '../../../../../Icon';
import {
  useWeaveflowCurrentRouteContext,
  WeaveflowPeekContext,
} from '../../context';
import {StyledTextField} from '../../StyledTextField';
import {ObjectViewerSection} from '../CallPage/ObjectViewerSection';
import {useEvaluationsFilter} from '../CallsPage/CallsPage';
import {CallsTable} from '../CallsPage/CallsTable';
import {
  EVALUATE_OP_NAME_POST_PYDANTIC,
  PREDICT_AND_SCORE_OP_NAME_POST_PYDANTIC,
} from '../common/heuristics';
import {CallLink, ObjectVersionLink, opNiceName} from '../common/Links';
import {SimplePageLayout} from '../common/SimplePageLayout';
import {useWFHooks} from '../wfReactInterface/context';
import {
  opVersionKeyToRefUri,
  opVersionRefOpName,
} from '../wfReactInterface/utilities';
import {
  ObjectVersionKey,
  ObjectVersionSchema,
} from '../wfReactInterface/wfDataModelHooksInterface';
import {
  EvaluationEvaluateCallSchema,
  evaluationMetrics,
  useEvaluationCall,
  useEvaluationCalls,
  useModelsFromEvaluationCalls,
} from './evaluations';
import MetricTile from './MetricTile';

const EVAL_DEF_HEIGHT = '45px';
const STANDARD_PADDING = '16px';
const CIRCLE_SIZE = '16px';
const BOX_RADIUS = '6px';
const STANDARD_BORDER = `1px solid ${MOON_300}`;
const PLOT_HEIGHT = 300;
const PLOT_PADDING = 30;

type CompareEvaluationsPageProps = {
  entity: string;
  project: string;
  evaluationCallIds: string[];
};

type CompareDualEvaluationsPageProps = {
  entity: string;
  project: string;
  evaluationCallId1: string;
  evaluationCallId2: string;
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
          content: (
            <CompareEvaluationsPageInner
              entity={props.entity}
              project={props.project}
              evaluationCallId1={props.evaluationCallIds[0]}
              evaluationCallId2={props.evaluationCallIds[1]}
            />
          ),
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

const VerticalBox: React.FC<BoxProps> = props => {
  return (
    <Box
      {...props}
      sx={{
        display: 'flex',
        flexDirection: 'column',
        gridGap: STANDARD_PADDING,
        overflow: 'hidden',
        ...props.sx,
      }}
    />
  );
};

const HorizontalBox: React.FC<BoxProps> = props => {
  return (
    <Box
      {...props}
      sx={{
        display: 'flex',
        flexDirection: 'row',
        gridGap: STANDARD_PADDING,
        overflow: 'hidden',
        ...props.sx,
      }}
    />
  );
};

const CompareEvaluationsPageInner: React.FC<
  CompareDualEvaluationsPageProps
> = props => {
  return (
    <VerticalBox
      sx={{
        paddingTop: STANDARD_PADDING,
        alignItems: 'flex-start',
      }}>
      <ComparisonDefinition {...props} />
      <SummaryPlots />
      <ScoreCard />
    </VerticalBox>
  );
};

const SummaryPlots: React.FC = () => {
  return (
    <HorizontalBox
      sx={{
        paddingLeft: STANDARD_PADDING,
        paddingRight: STANDARD_PADDING,
        flex: '1 1 auto',
        width: '100%',
      }}>
      <RadarPlot />
      <BarPlots />
    </HorizontalBox>
  );
};

const RadarPlot: React.FC = () => {
  return (
    <Box
      sx={{
        flex: '0 0 auto',
        height: PLOT_HEIGHT,
        width: PLOT_HEIGHT,
        borderRadius: BOX_RADIUS,
        border: STANDARD_BORDER,
        overflow: 'hidden',
      }}>
      <PlotlyRadialPlot />
    </Box>
  );
};

const BarPlots: React.FC = () => {
  return (
    <Box
      sx={{
        flex: '1 1 auto',
        height: PLOT_HEIGHT,
        width: '100%',
        overflow: 'hidden',
        borderRadius: BOX_RADIUS,
        border: STANDARD_BORDER,
        padding: PLOT_PADDING,
      }}>
      <PlotlyBarPlot />
    </Box>
  );
};

const ScoreCard: React.FC = () => {
  const modelRefs = ['Model:A', 'Model:B'];
  const scoreDefs = {
    score1: {metrics: [{key: 'score1.mean', unit: '', lowerIsBetter: true}]},
    score2: {
      metrics: [{key: 'score2.true_fraction', unit: '%', lowerIsBetter: true}],
    },
  };
  const scores = {
    'score1.mean': {
      'Model:A': 0.5,
      'Model:B': 0.6,
    },
    'score2.true_fraction': {
      'Model:A': 0.5,
      'Model:B': 0.6,
    },
  };
  return (
    <Box
      sx={{
        width: '100%',
        flex: '0 0 auto',
        paddingLeft: STANDARD_PADDING,
        paddingRight: STANDARD_PADDING,
      }}>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr 1fr 1fr 1fr',
        }}>
        {/* Header Row */}
        <div></div>
        <div></div>
        <div>Model A</div>
        <div>Model B</div>
        <div>Diff</div>
        {/* Score Rows */}
        {Object.entries(scoreDefs).map(([key, def]) => {
          return (
            <div
              key={key}
              style={{
                // vertical span length of metric
                gridRowEnd: `span ${def.metrics.length}`,
              }}>
              {key}
            </div>
          );
        })}
      </div>
    </Box>
  );
};

const ComparisonDefinition: React.FC<
  CompareDualEvaluationsPageProps
> = props => {
  return (
    <HorizontalBox
      sx={{
        alignItems: 'center',
        paddingLeft: STANDARD_PADDING,
        paddingRight: STANDARD_PADDING,
      }}>
      <EvaluationDefinition
        entity={props.entity}
        project={props.project}
        evaluationCallId={props.evaluationCallId1}
        color={TEAL_500}
      />
      <SwapPositionsButton />
      <EvaluationDefinition
        entity={props.entity}
        project={props.project}
        evaluationCallId={props.evaluationCallId2}
        color={CACTUS_500}
      />
      <DefinitionText text="compare" />
      <DimensionPicker {...props} />
      <DefinitionText text="by" />
      <DimensionPicker {...props} />
    </HorizontalBox>
  );
};

const DefinitionText: React.FC<{text: string}> = props => {
  return <Box>{props.text}</Box>;
};

const DimensionPicker: React.FC<CompareDualEvaluationsPageProps> = props => {
  const dimensions = useEvaluationCallDimensions(
    props.entity,
    props.project,
    useMemo(() => [props.evaluationCallId1, props.evaluationCallId2], [props])
  );
  return (
    <FormControl>
      <Autocomplete
        size="small"
        limitTags={1}
        value={dimensions[0]}
        onChange={(event, newValue) => {
          console.log('onChange', newValue);
        }}
        options={dimensions}
        renderInput={renderParams => (
          <StyledTextField
            {...renderParams}
            label={'Dimension'}
            sx={{minWidth: '200px'}}
          />
        )}
      />
    </FormControl>
  );
};

const useEvaluationCallDimensions = (
  entity: string,
  project: string,
  callIds: string[]
): string[] => {
  return ['dimension1', 'dimension2', 'dimension3'];
  // const calls = useEvaluationCalls(entity, project, callIds);
  // const dimensions = useMemo(() => {
  //   const allDims = calls.map(call => call.inputs.self.dimensions);
  //   const commonDims = allDims.reduce((acc, dims) => {
  //     return acc.filter(dim => dims.includes(dim));
  //   }, allDims[0]);
  //   return commonDims;
  // }, [calls]);
  // return dimensions;
};

const EvaluationDefinition: React.FC<{
  entity: string;
  project: string;
  evaluationCallId: string;
  color?: string;
}> = props => {
  return (
    <HorizontalBox
      sx={{
        height: EVAL_DEF_HEIGHT,
        borderRadius: BOX_RADIUS,
        border: STANDARD_BORDER,
        padding: '12px',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
      <EvaluationCallLink
        entity={props.entity}
        project={props.project}
        callId={props.evaluationCallId}
        color={props.color}
      />
      <VerticalBar />
      <EvaluationModelLink
        entity={props.entity}
        project={props.project}
        callId={props.evaluationCallId}
      />
    </HorizontalBox>
  );
};

const EvaluationCallLink: React.FC<{
  entity: string;
  project: string;
  callId: string;
  color?: string;
}> = props => {
  // TODO: Get user-defined name for the evaluation
  const name = 'Evaluation';
  return (
    <CallLink
      entityName={props.entity}
      projectName={props.project}
      opName={name}
      callId={props.callId}
      icon={
        <Circle
          sx={{
            color: props.color,
            height: CIRCLE_SIZE,
          }}
        />
      }
      color={MOON_800}
    />
  );
};

const VerticalBar: React.FC = () => {
  return (
    <div
      style={{
        width: '2px',
        height: '100%',
        backgroundColor: MOON_300,
      }}
    />
  );
};

const ModelIcon: React.FC = () => {
  return (
    <Box
      mr="4px"
      bgcolor={hexToRGB(MOON_300, 0.48)}
      sx={{
        height: '22px',
        width: '22px',
        borderRadius: '16px',
        display: 'flex',
        flex: '0 0 22px',
        justifyContent: 'center',
        alignItems: 'center',
        color: MOON_600,
      }}>
      <Icon name={IconNames.Model} width={14} height={14} />
    </Box>
  );
};

const EvaluationModelLink: React.FC<{
  entity: string;
  project: string;
  callId: string;
}> = props => {
  const call = useEvaluationCall(props.entity, props.project, props.callId);
  const parsed = useModelRefForEvaluationCall(call);
  const objectVersion = useObjectVersionForWeaveObjectRef(parsed);

  if (!objectVersion) {
    return <Skeleton variant="rectangular" width={210} />;
  }

  return (
    <ObjectVersionLink
      entityName={objectVersion.entity}
      projectName={objectVersion.project}
      objectName={objectVersion.objectId}
      version={objectVersion.versionHash}
      versionIndex={objectVersion.versionIndex}
      color={MOON_800}
      icon={<ModelIcon />}
    />
  );
};

const useModelRefForEvaluationCall = (
  call: EvaluationEvaluateCallSchema | null
): WeaveObjectRef | null => {
  return useMemo(() => {
    if (!call) {
      return null;
    }
    return parseRef(call.inputs.model) as WeaveObjectRef;
  }, [call]);
};

const useObjectVersionForWeaveObjectRef = (
  ref: WeaveObjectRef | null
): ObjectVersionSchema | null => {
  const {useObjectVersion} = useWFHooks();
  const objectKey: ObjectVersionKey | null = useMemo(() => {
    if (!ref) {
      return null;
    }
    return {
      scheme: 'weave',
      entity: ref.entityName,
      project: ref.projectName,
      weaveKind: ref.weaveKind,
      objectId: ref.artifactName,
      versionHash: ref.artifactVersion,
      path: '',
      refExtra: ref.artifactRefExtra,
    };
  }, [ref]);

  return useObjectVersion(objectKey).result;
};

const SwapPositionsButton: React.FC = () => {
  return (
    <Button size="medium" variant="quiet" onClick={console.log} icon="retry" />
  );
};

const CompareEvaluationsPageInner2: React.FC<
  CompareDualEvaluationsPageProps
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
    return {
      parentId: calls[0] ? calls[0].id : null,
      opVersionRefs: [
        opVersionKeyToRefUri({
          entity: props.entity,
          project: props.project,
          opId: PREDICT_AND_SCORE_OP_NAME_POST_PYDANTIC,
          versionHash: '*',
        }),
      ],
    };
  }, [calls, props.entity, props.project]);
  console.log(callsFilter);

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
  return <TitleWithDot title={'Baseline'} color={TEAL_500} />;
};

const ChallengerTitle: React.FC = () => {
  return <TitleWithDot title={'Challenger'} color={CACTUS_500} />;
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
      </TableHead>
      <TableBody>
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
        <TableRow sx={{'&:last-child td, &:last-child th': {border: 0}}}>
          <TableCell component="th" scope="row">
            Evaluation Details
          </TableCell>
          {props.calls.map((call, ndx) => {
            // TODO: make this a multi-viewer that only shows diffs
            return (
              <TableCell key={ndx}>
                <ObjectViewerSection
                  title=""
                  data={call.inputs.self ?? {}}
                  noHide
                  isExpanded
                />
              </TableCell>
            );
          })}
        </TableRow>
        <TableRow>
          <TableCell>Model Object</TableCell>
          {models.map((model, ndx) => {
            const parsed = parseRef(model.ref) as WeaveObjectRef;

            return (
              <TableCell align="right" key={ndx}>
                <ObjectVersionLink
                  entityName={parsed.entityName}
                  projectName={parsed.projectName}
                  objectName={parsed.artifactName}
                  version={parsed.artifactVersion}
                  versionIndex={0}
                  fullWidth={true}
                />
              </TableCell>
            );
          })}
        </TableRow>

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
                  data={model.data ?? {}}
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

const PlotlyScatterPlot: React.FC<{}> = () => {
  const divRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const trace2 = {
      x: [2, 3, 4, 5],
      y: [16, 5, 11, 9],
      mode: 'markers',
      type: 'scatter',
      marker: {color: TEAL_500, size: 12},
    };

    const trace3 = {
      x: [1, 2, 3, 4],
      y: [12, 9, 15, 12],
      mode: 'markers',
      type: 'scatter',
      marker: {color: CACTUS_500, size: 12},
    };

    const data = [trace2, trace3];
    Plotly.newPlot(
      divRef.current as any,
      data as any,
      {
        height: PLOT_HEIGHT,
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
        height: PLOT_HEIGHT,
        width: '100%',
      }}>
      <div ref={divRef}></div>
    </Box>
  );
};

const PlotlyRadialPlot: React.FC<{}> = () => {
  const divRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const data = [
      {
        type: 'scatterpolar',
        r: [39, 28, 8, 7, 28, 39],
        theta: ['A', 'B', 'C', 'D', 'E', 'A'],
        fill: 'toself',
        name: 'Group A',
        marker: {color: TEAL_500},
      },
      {
        type: 'scatterpolar',
        r: [1.5, 10, 39, 31, 15, 1.5],
        theta: ['A', 'B', 'C', 'D', 'E', 'A'],
        fill: 'toself',
        marker: {color: CACTUS_500},
      },
    ];

    const layout = {
      height: PLOT_HEIGHT,

      showlegend: false,
      margin: {
        l: 30, // legend
        r: 30,
        b: 30, // legend
        t: 30,
        pad: 0,
      },
      polar: {
        color: MOON_300,
        radialaxis: {
          linecolor: MOON_300,
          // color: MOON_300,
          visible: false,
          range: [0, 50],
          gridcolor: MOON_300, // Customize radial grid color
        },
        angularaxis: {
          linecolor: MOON_300,
          // color: MOON_300,
          gridcolor: MOON_300, // Customize angular grid color
        },
      },
    };
    Plotly.newPlot(divRef.current as any, data as any, layout, {
      displayModeBar: false,
      responsive: true,
      // staticPlot: true, // Disable all interactions
    });
  }, []);

  return (
    <Box
      sx={{
        height: '100%',
        width: '100%',
      }}>
      <div ref={divRef}></div>
    </Box>
  );
};

const PlotlyBarPlot: React.FC<{}> = () => {
  const divRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const trace1 = {
      x: ['A', 'B', 'C', 'D', 'E'],
      y: [20, 14, 23, 23, 43],
      type: 'bar',
      marker: {color: TEAL_500},
    };

    const trace2 = {
      x: ['A', 'B', 'C', 'D', 'E'],
      y: [12, 18, 29, 54, 23],
      type: 'bar',
      marker: {color: CACTUS_500},
    };

    const data = [trace1, trace2];
    Plotly.newPlot(
      divRef.current as any,
      data as any,
      {
        height: PLOT_HEIGHT - 2 * PLOT_PADDING,
        showlegend: false,
        title: '',
        margin: {
          l: 0,
          r: 0,
          b: 20,
          t: 0,
          pad: 0,
        },
        xaxis: {
          fixedrange: true,
          // showgrid: true,
          gridcolor: MOON_300, // Customize x-axis grid color
          // color: MOON_300, // Customize x-axis grid color
          linecolor: MOON_300, // Customize x-axis grid color
        },
        yaxis: {
          fixedrange: true,
          // showgrid: true,
          gridcolor: MOON_300, // Customize x-axis grid color
          // color: MOON_300, // Customize x-axis grid color
          linecolor: MOON_300, // Customize x-axis grid color
        },
      },
      {
        displayModeBar: false,
        responsive: true,

        // staticPlot: true, // Disable all interactions
      }
    );
  }, []);

  return (
    <Box
      sx={{
        height: '100%',
        width: '100%',
      }}>
      <div ref={divRef}></div>
    </Box>
  );
};

/**
 * TOOD:
 * - [ ] Add action to swap the positions of the evaluations
 * - [ ] Add action to select the dimensions to compare
 * - [ ] Make colors parametric and dynamic
 * - [ ] Stop radial interactions
 * - [ ] Make metrics actually real
 */
