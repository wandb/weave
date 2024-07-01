import {Box, FormControl} from '@material-ui/core';
import {Autocomplete} from '@mui/material';
import React, {FC, useCallback, useContext, useMemo} from 'react';
import {useHistory} from 'react-router-dom';

import {MOON_500} from '../../../../../../common/css/color.styles';
import {Button} from '../../../../../Button';
import {
  useWeaveflowCurrentRouteContext,
  WeaveflowPeekContext,
} from '../../context';
import {StyledTextField} from '../../StyledTextField';
import {useEvaluationsFilter} from '../CallsPage/CallsPage';
import {SimplePageLayout} from '../common/SimplePageLayout';
import {
  CompareEvaluationsProvider,
  EvaluationComparisonState,
  useCompareEvaluationsState,
} from './compareEvaluationsContext';
import {
  BOX_RADIUS,
  PLOT_HEIGHT,
  PLOT_PADDING,
  STANDARD_BORDER,
  STANDARD_PADDING,
} from './constants';
import {EvaluationDefinition} from './EvaluationDefinition';
import {evaluationMetrics} from './evaluations';
import {HorizontalBox, VerticalBox} from './Layout';
import {PlotlyBarPlot} from './PlotlyBarPlot';
// import {PlotlyBarPlot} from './PlotlyBarPlot';
import {PlotlyRadarPlot, RadarPlotData} from './PlotlyRadarPlot';
import {PlotlyScatterPlot, ScatterPlotData} from './PlotlyScatterPlot';
import {ScoreCard} from './Scorecard';

type CompareEvaluationsPageProps = {
  entity: string;
  project: string;
  evaluationCallIds: string[];
};

export const CompareEvaluationsPage: React.FC<
  CompareEvaluationsPageProps
> = props => {
  if (props.evaluationCallIds.length === 0) {
    return <div>No evaluations to compare</div>;
  }
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
        {Object.keys(state.data.models).length === 2 && (
          <ScatterFilter state={state} />
        )}
        <CompareEvaluationsCallsTable state={state} />
      </VerticalBox>
    </Box>
  );
};

const ScatterFilter: React.FC<{state: EvaluationComparisonState}> = props => {
  const data = useMemo(() => {
    // const primaryDimension = 'model_latency';
    const series: ScatterPlotData[number] = {
      x: [],
      y: [],
      color: MOON_500,
    };
    const modelRefs = Object.keys(props.state.data.models);
    const modelX = modelRefs[0];
    const modelY = modelRefs[1];
    Object.values(props.state.data.resultRows).forEach(row => {
      Object.values(row.models[modelX].predictAndScores).forEach(score => {
        series.x.push(score.predictCall?.latencyMs ?? 0);
      });
      Object.values(row.models[modelY].predictAndScores).forEach(score => {
        series.y.push(score.predictCall?.latencyMs ?? 0);
      });
    });
    return [series];
  }, [props.state]);
  console.log(data, props.state);
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
        {/* <ScatterDefinition {...props} /> */}
        <PlotlyScatterPlot height={PLOT_HEIGHT} data={data} />
      </VerticalBox>
    </VerticalBox>
  );
};

// const ScatterDefinition: React.FC<{
//   state: EvaluationComparisonState;
// }> = props => {
//   return (
//     <HorizontalBox
//       sx={{
//         alignItems: 'center',
//         paddingTop: STANDARD_PADDING,
//       }}>
//       <DefinitionText text="Plot" />
//       <DimensionPicker {...props} />
//       <DefinitionText text="against" />
//       <DimensionPicker {...props} />
//     </HorizontalBox>
//   );
// };

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
          flex: '1 0 auto',
          height: PLOT_HEIGHT,
          // width: PLOT_HEIGHT * 2,
          borderRadius: BOX_RADIUS,
          border: STANDARD_BORDER,
          overflow: 'hidden',
          alignContent: 'center',
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
      <DefinitionText text="target metric " />
      <DimensionPicker {...props} />
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
            sx={{width: '300px'}}
          />
        )}
      />
    </FormControl>
  );
};

const useEvaluationCallDimensions = (
  state: EvaluationComparisonState
): string[] => {
  return useMemo(() => {
    const availableScorers = Object.values(state.data.evaluationCalls)
      .map(evalCall =>
        Object.entries(evalCall.scores)
          .map(([k, v]) => Object.keys(v).map(innerKey => k + '.' + innerKey))
          .flat()
      )
      .flat();

    return [
      ...Array.from(new Set(availableScorers)),
      'model_latency',
      'total_tokens',
    ];
  }, [state.data.evaluationCalls]);
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

/**
 * TOOD:
 * - [ ] Allow user to select primary metric & save to local storage + URL
 * - [ ] Wireup the baseline replace button
 * - [ ] Fix Plot to show correct data
 * - [ ] Build grouping
 * - [ ] Add scorer links in scorecard
 * - [ ] Definition header does not scale small enough
 * - [ ] Auto-expand first-level properties (see prompt here: https://app.wandb.test/wandb-designers/signal-maven/weave/compare-evaluations?evaluationCallIds=%5B%22bf5188ba-48cd-4c6d-91ea-e25464570c13%22%2C%222f4544f3-9649-487e-b083-df6985e21b12%22%2C%228cbeccd6-6ff7-4eac-a305-6fb6450530f1%22%5D)
 * TEST:
 * - [ ] Single Case
 * - [ ] Dual Case
 * - [ ] Multi Case
 */
