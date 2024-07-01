import {Box, BoxProps, FormControl} from '@material-ui/core';
import {Circle} from '@mui/icons-material';
import {Autocomplete} from '@mui/material';
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
import {Button} from '../../../../../Button';
import {Icon, IconNames} from '../../../../../Icon';
import {
  useWeaveflowCurrentRouteContext,
  WeaveflowPeekContext,
} from '../../context';
import {StyledTextField} from '../../StyledTextField';
import {useEvaluationsFilter} from '../CallsPage/CallsPage';
import {CallLink, ObjectVersionLink} from '../common/Links';
import {SimplePageLayout} from '../common/SimplePageLayout';
import {
  CompareEvaluationsProvider,
  EvaluationComparisonState,
  useCompareEvaluationsState,
} from './compareEvaluationsContext';
import {evaluationMetrics} from './evaluations';
import {PlotlyBarPlot} from './PlotlyBarPlot';
import {PlotlyRadarPlot, RadarPlotData} from './PlotlyRadarPlot';
import {ScoreCard} from './Scorecard';

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

export const CompareEvaluationsPage: React.FC<
  CompareEvaluationsPageProps
> = props => {
  return (
    <SimplePageLayout
      title={'Compare Evaluations'}
      hideTabsIfSingle
      tabs={[
        {
          label: 'All',
          content: (
            <CompareEvaluationsProvider
              entity={props.entity}
              project={props.project}
              evaluationCallIds={props.evaluationCallIds}
              baselineEvaluationCallId={props.evaluationCallIds[0]}>
              <CompareEvaluationsPageInner />
            </CompareEvaluationsProvider>
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
        flex: '0 0 auto',
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
        flex: '0 0 auto',
        ...props.sx,
      }}
    />
  );
};

const CompareEvaluationsPageInner: React.FC = props => {
  const state = useCompareEvaluationsState();
  return (
    <Box
      sx={{
        height: '100%',
        width: '100%',
        overflow: 'auto',
      }}>
      <VerticalBox
        sx={{
          paddingTop: STANDARD_PADDING,
          alignItems: 'flex-start',
        }}>
        <ComparisonDefinition state={state} />
        <SummaryPlots state={state} />
        <ScoreCard state={state} />
        <ScatterFilter state={state} />
        <CompareEvaluationsCallsTable state={state} />
      </VerticalBox>
    </Box>
  );
};

const ScatterFilter: React.FC<{state: EvaluationComparisonState}> = props => {
  return (
    <VerticalBox
      sx={{
        width: '100%',
        paddingLeft: STANDARD_PADDING,
        paddingRight: STANDARD_PADDING,
      }}>
      <VerticalBox
        sx={{
          width: '100%',
          paddingLeft: STANDARD_PADDING,
          paddingRight: STANDARD_PADDING,
          borderRadius: BOX_RADIUS,
          border: STANDARD_BORDER,
        }}>
        <ScatterDefinition {...props} />
        <PlotlyScatterPlot />
      </VerticalBox>
    </VerticalBox>
  );
};

const ScatterDefinition: React.FC<{
  state: EvaluationComparisonState;
}> = props => {
  return (
    <HorizontalBox
      sx={{
        alignItems: 'center',
        paddingTop: STANDARD_PADDING,
      }}>
      <DefinitionText text="Plot" />
      <DimensionPicker {...props} />
      <DefinitionText text="against" />
      <DimensionPicker {...props} />
    </HorizontalBox>
  );
};

const SummaryPlots: React.FC<{state: EvaluationComparisonState}> = props => {
  const plotlyRadarData = useNormalizedRadarPlotDataFromMetrics(props.state);

  return (
    <HorizontalBox
      sx={{
        paddingLeft: STANDARD_PADDING,
        paddingRight: STANDARD_PADDING,
        flex: '1 1 auto',
        width: '100%',
      }}>
      <Box
        sx={{
          flex: '0 0 auto',
          height: PLOT_HEIGHT,
          width: PLOT_HEIGHT * 2,
          borderRadius: BOX_RADIUS,
          border: STANDARD_BORDER,
          overflow: 'hidden',
        }}>
        <PlotlyRadarPlot height={PLOT_HEIGHT} data={plotlyRadarData} />
        {/* <PlotlyRadarPlot /> */}
        {/* // <PlotlyRadialPlot /> */}
      </Box>
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
        <PlotlyBarPlot height={PLOT_HEIGHT} data={plotlyRadarData} />
      </Box>
      {/* <RadarPlot plotlyRadarData={plotlyRadarData} />
      <BarPlots plotlyRadarData={plotlyRadarData}} /> */}
    </HorizontalBox>
  );
};

const normalizeValues = (values: number[]): number[] => {
  // find the max value
  // find the power of 2 that is greater than the max value
  // divide all values by that power of 2
  const maxVal = Math.max(...values);
  const maxPower = Math.ceil(Math.log2(maxVal));
  return values.map(val => val / 2 ** maxPower);
};

const useNormalizedRadarPlotDataFromMetrics = (
  state: EvaluationComparisonState
): RadarPlotData => {
  const metrics = useMemo(() => {
    return evaluationMetrics(state);
  }, [state]);

  return useMemo(() => {
    const normalizedMetrics = metrics.map(metric => {
      const keys = Object.keys(metric.values);
      const values = keys.map(key => metric.values[key]);
      const normalizedValues = normalizeValues(values);

      return {
        ...metric,
        values: Object.fromEntries(
          keys.map((key, i) => [key, normalizedValues[i]])
        ),
      };
    });
    return Object.fromEntries(
      Object.values(state.data.evaluationCalls).map(evalCall => {
        return [
          evalCall.callId,
          {
            name: evalCall.name,
            color: evalCall.color,
            metrics: Object.fromEntries(
              normalizedMetrics.map(metric => {
                return [metric.path, metric.values[evalCall.callId]];
              })
            ),
          },
        ];
      })
    );
  }, [metrics, state.data.evaluationCalls]);
};

const ComparisonDefinition: React.FC<{
  state: EvaluationComparisonState;
}> = props => {
  return (
    <HorizontalBox
      sx={{
        alignItems: 'center',
        paddingLeft: STANDARD_PADDING,
        paddingRight: STANDARD_PADDING,
      }}>
      {Object.keys(props.state.data.evaluationCalls).map((key, ndx) => {
        return (
          <React.Fragment key={key}>
            {ndx !== 0 && <SwapPositionsButton />}
            <EvaluationDefinition state={props.state} callId={key} />
          </React.Fragment>
        );
      })}
    </HorizontalBox>
  );
};

const DefinitionText: React.FC<{text: string}> = props => {
  return <Box>{props.text}</Box>;
};

const DimensionPicker: React.FC<{state: EvaluationComparisonState}> = props => {
  const dimensions = useEvaluationCallDimensions(props.state);
  return (
    <FormControl>
      <Autocomplete
        size="small"
        limitTags={1}
        value={dimensions[0]}
        onChange={(event, newValue) => {
          // console.log('onChange', newValue);
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
  state: EvaluationComparisonState
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
  state: EvaluationComparisonState;
  callId: string;
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
      <EvaluationCallLink {...props} />
      <VerticalBar />
      <EvaluationModelLink {...props} />
    </HorizontalBox>
  );
};

const EvaluationCallLink: React.FC<{
  callId: string;
  state: EvaluationComparisonState;
}> = props => {
  // console.log(props.state, props.callId);
  const evaluationCall = props.state.data.evaluationCalls[props.callId];
  const [entity, project] =
    evaluationCall._rawEvaluationTraceData.project_id.split('/');
  return (
    <CallLink
      entityName={entity}
      projectName={project}
      opName={evaluationCall.name}
      callId={props.callId}
      icon={
        <Circle
          sx={{
            color: evaluationCall.color,
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
  callId: string;
  state: EvaluationComparisonState;
}> = props => {
  const evaluationCall = props.state.data.evaluationCalls[props.callId];
  const modelObj = props.state.data.models[evaluationCall.modelRef];
  console.log({modelObj});

  return (
    <ObjectVersionLink
      entityName={modelObj.entity}
      projectName={modelObj.project}
      objectName={modelObj._rawModelObject.object_id}
      version={modelObj._rawModelObject.digest}
      versionIndex={modelObj._rawModelObject.version_index}
      color={MOON_800}
      icon={<ModelIcon />}
    />
  );
};

const SwapPositionsButton: React.FC = () => {
  return (
    <Button size="medium" variant="quiet" onClick={console.log} icon="retry" />
  );
};

const CompareEvaluationsCallsTable: React.FC<{
  state: EvaluationComparisonState;
}> = props => {
  // const calls = useEvaluationCalls(
  //   props.entity,
  //   props.project,
  //   useMemo(() => [props.evaluationCallId1, props.evaluationCallId2], [props])
  // );
  // const callsFilter = useMemo(() => {
  //   return {
  //     parentId: calls[0] ? calls[0].id : null,
  //     opVersionRefs: [
  //       opVersionKeyToRefUri({
  //         entity: props.entity,
  //         project: props.project,
  //         opId: PREDICT_AND_SCORE_OP_NAME_POST_PYDANTIC,
  //         versionHash: '*',
  //       }),
  //     ],
  //   };
  // }, [calls, props.entity, props.project]);
  return (
    <Box sx={{height: '500px', width: '100%', overflow: 'hidden'}}>
      COMING SOON
      {/* <CallsTable
        entity={props.entity}
        project={props.project}
        frozenFilter={callsFilter}
        hideControls
      /> */}
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
        showlegend: false,
        title: '',
        margin: {
          l: 20, // legend
          r: 0,
          b: 30, // legend
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

/**
 * TOOD:
 * - [ ] Add action to swap the positions of the evaluations
 * - [ ] Add action to select the dimensions to compare
 * - [ ] Make colors parametric and dynamic
 * - [ ] Stop radial interactions
 * - [ ] Make metrics actually real
 */
