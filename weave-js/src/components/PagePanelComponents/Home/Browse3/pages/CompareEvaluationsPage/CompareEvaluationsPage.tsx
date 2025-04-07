/**
 * This is the entrypoint for the Evaluation Comparison Page.
 */

import {Box} from '@material-ui/core';
import {Alert} from '@mui/material';
import {WaveLoader} from '@wandb/weave/components/Loaders/WaveLoader';
import React, {FC, useCallback, useContext} from 'react';
import {useHistory} from 'react-router-dom';
import {AutoSizer} from 'react-virtualized';

import {Button} from '../../../../../Button';
import {
  useWeaveflowCurrentRouteContext,
  WeaveflowPeekContext,
} from '../../context';
import {CustomWeaveTypeProjectContext} from '../../typeViews/CustomWeaveTypeDispatcher';
import {useEvaluationsFilter} from '../CallsPage/evaluationsFilter';
import {SimplePageLayout} from '../common/SimplePageLayout';
import {useWFHooks} from '../wfReactInterface/context';
import {
  CompareEvaluationsProvider,
  useCompareEvaluationsState,
} from './compareEvaluationsContext';
import {STANDARD_PADDING} from './ecpConstants';
import {ComparisonDimensionsType, EvaluationComparisonState} from './ecpState';
import {InvalidEvaluationBanner} from './InvalidEvaluationBanner';
import {HorizontalBox, VerticalBox} from './Layout';
import {ComparisonDefinitionSection} from './sections/ComparisonDefinitionSection/ComparisonDefinitionSection';
import {ExampleCompareSection} from './sections/ExampleCompareSection/ExampleCompareSection';
import {ExampleFilterSection} from './sections/ExampleFilterSection/ExampleFilterSection';
import {ScorecardSection} from './sections/ScorecardSection/ScorecardSection';
import {SummaryPlots} from './sections/SummaryPlotsSection/SummaryPlotsSection';
import {TraceCallsCompareEvaluationsPage} from './TraceCallsCompareEvaluationsPage';

type CompareEvaluationsPageProps = {
  entity: string;
  project: string;
  evaluationCallIds: string[];
  onEvaluationCallIdsUpdate: (newEvaluationCallIds: string[]) => void;
  selectedMetrics: Record<string, boolean> | null;
  setSelectedMetrics: (newModel: Record<string, boolean>) => void;
};

export const CompareEvaluationsPage: React.FC<
  CompareEvaluationsPageProps
> = props => {
  return (
    <SimplePageLayout
      title={
        props.evaluationCallIds.length === 1
          ? 'Evaluation Results'
          : 'Compare Evaluations'
      }
      hideTabsIfSingle
      tabs={[
        {
          label: 'All',
          content: (
            <CompareEvaluationsPageContent
              entity={props.entity}
              project={props.project}
              evaluationCallIds={props.evaluationCallIds}
              onEvaluationCallIdsUpdate={props.onEvaluationCallIdsUpdate}
              selectedMetrics={props.selectedMetrics}
              setSelectedMetrics={props.setSelectedMetrics}
            />
          ),
        },
      ]}
      headerExtra={<HeaderExtra {...props} />}
    />
  );
};

export const CompareEvaluationsPageContent: React.FC<
  CompareEvaluationsPageProps
> = props => {
  const [comparisonDimensions, setComparisonDimensions] =
    React.useState<ComparisonDimensionsType | null>(null);

  const [selectedInputDigest, setSelectedInputDigest] = React.useState<
    string | null
  >(null);

  const {useCalls} = useWFHooks();
  const childCalls = useCalls(props.entity, props.project, {
    parentIds: props.evaluationCallIds,
  });

  const traceCalls = childCalls.result
    ?.filter(call => call.traceCall?.op_name?.includes('predict_and_score'))
    ?.map(call => ({
      callId: call.callId,
      traceCall: call.traceCall,
    }));

  // Filter for summarize calls
  const summarizeCalls = childCalls.result
    ?.filter(
      call =>
        call.traceCall?.op_name?.includes('summarize') ||
        call.traceCall?.op_name?.includes('Evaluation.summarize')
    )
    ?.map(call => ({
      callId: call.callId,
      traceCall: call.traceCall,
    }));

  const setComparisonDimensionsAndClearInputDigest = useCallback(
    (
      dimensions:
        | ComparisonDimensionsType
        | null
        | ((
            prev: ComparisonDimensionsType | null
          ) => ComparisonDimensionsType | null)
    ) => {
      if (typeof dimensions === 'function') {
        dimensions = dimensions(comparisonDimensions);
      }
      setComparisonDimensions(dimensions);
      setSelectedInputDigest(null);
    },
    [comparisonDimensions]
  );

  if (props.evaluationCallIds.length === 0) {
    return <div>No evaluations to compare</div>;
  }

  return (
    <CompareEvaluationsProvider
      entity={props.entity}
      project={props.project}
      initialEvaluationCallIds={props.evaluationCallIds}
      selectedMetrics={props.selectedMetrics}
      setSelectedMetrics={props.setSelectedMetrics}
      comparisonDimensions={comparisonDimensions ?? undefined}
      onEvaluationCallIdsUpdate={props.onEvaluationCallIdsUpdate}
      setComparisonDimensions={setComparisonDimensionsAndClearInputDigest}
      selectedInputDigest={selectedInputDigest ?? undefined}
      setSelectedInputDigest={setSelectedInputDigest}>
      <CustomWeaveTypeProjectContext.Provider
        value={{entity: props.entity, project: props.project}}>
        <AutoSizer style={{height: '100%', width: '100%'}}>
          {({height, width}) => (
            <CompareEvaluationsPageInner
              height={height}
              traceCalls={traceCalls}
              summarizeCalls={summarizeCalls}
            />
          )}
        </AutoSizer>
      </CustomWeaveTypeProjectContext.Provider>
    </CompareEvaluationsProvider>
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

const CompareEvaluationsPageInner: React.FC<{
  height: number;
  traceCalls?: Array<{callId: string; traceCall: any}>;
  summarizeCalls?: Array<{callId: string; traceCall: any}>;
}> = props => {
  const {state, setSelectedMetrics} = useCompareEvaluationsState();
  const showExampleFilter =
    Object.keys(state.summary.evaluationCalls).length === 2;
  const showExamples = true;
  const resultsLoading = state.loadableComparisonResults.loading;

  // Check if we should show the traceCalls UI
  const isTraceCallsPath = props.traceCalls && props.traceCalls.length > 0;

  if (isTraceCallsPath) {
    // Use the new TraceCallsCompareEvaluationsPage component
    return (
      <TraceCallsCompareEvaluationsPage
        height={props.height}
        traceCalls={props.traceCalls || []}
        summarizeCalls={props.summarizeCalls || []}
        state={state}
      />
    );
  }

  // Original UI for regular comparison path
  return (
    <Box
      sx={{
        height: props.height,
        width: '100%',
        overflow: 'auto',
      }}>
      <VerticalBox
        sx={{
          paddingTop: STANDARD_PADDING,
          alignItems: 'flex-start',
          gridGap: STANDARD_PADDING * 2,
        }}>
        <InvalidEvaluationBanner
          evaluationCalls={Object.values(state.summary.evaluationCalls)}
        />
        <ComparisonDefinitionSection state={state} />
        <SummaryPlots state={state} setSelectedMetrics={setSelectedMetrics} />
        <ScorecardSection state={state} />
        {resultsLoading ? (
          <Box
            sx={{
              width: '100%',
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              height: '50px',
            }}>
            <WaveLoader size="small" />
          </Box>
        ) : showExamples ? (
          <>
            {showExampleFilter && <ExampleFilterSection state={state} />}
            <ResultExplorer state={state} height={props.height} />
          </>
        ) : (
          <VerticalBox
            sx={{
              paddingLeft: STANDARD_PADDING,
              paddingRight: STANDARD_PADDING,
              width: '100%',
              overflow: 'auto',
            }}>
            <Box
              sx={{
                fontSize: '1.5em',
                fontWeight: 'bold',
              }}>
              Examples
            </Box>
            <Alert severity="info">
              The selected evaluations' datasets have 0 rows in common, try
              comparing evaluations with datasets that have at least one row in
              common.
            </Alert>
          </VerticalBox>
        )}
      </VerticalBox>
    </Box>
  );
};

const ResultExplorer: React.FC<{
  state: EvaluationComparisonState;
  height: number;
}> = ({state, height}) => {
  // Get entity and project from context
  const projectContext = React.useContext(CustomWeaveTypeProjectContext);

  return (
    <VerticalBox
      sx={{
        width: '100%',
        overflow: 'hidden',
      }}>
      <HorizontalBox
        sx={{
          flex: '0 0 auto',
          paddingLeft: STANDARD_PADDING,
          paddingRight: STANDARD_PADDING,
          width: '100%',
          alignItems: 'center',
          justifyContent: 'flex-start',
        }}>
        <Box
          sx={{
            fontSize: '1.5em',
            fontWeight: 'bold',
          }}>
          Output Comparison
        </Box>
      </HorizontalBox>
      <Box
        sx={{
          height,
          overflow: 'auto',
        }}>
        <ExampleCompareSection state={state} />
      </Box>
    </VerticalBox>
  );
};
