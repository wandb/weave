/**
 * This is the entrypoint for the Evaluation Comparison Page.
 */

import {Box} from '@material-ui/core';
import {Alert} from '@mui/material';
import {WaveLoader} from '@wandb/weave/components/Loaders/WaveLoader';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {maybePluralizeWord} from '@wandb/weave/core/util/string';
import React, {FC, useCallback, useContext, useMemo, useState} from 'react';
import {useHistory} from 'react-router-dom';
import {AutoSizer} from 'react-virtualized';

import {Button} from '../../../../../Button';
import {
  useWeaveflowCurrentRouteContext,
  WeaveflowPeekContext,
} from '../../context';
import {CustomWeaveTypeProjectContext} from '../../typeViews/CustomWeaveTypeDispatcher';
import {SimplePageLayout, SimpleTabView} from '../common/SimplePageLayout';
import {
  CompareEvaluationsProvider,
  useCompareEvaluationsState,
} from './compareEvaluationsContext';
import {STANDARD_PADDING} from './ecpConstants';
import {EvaluationComparisonState} from './ecpState';
import {ComparisonDimensionsType} from './ecpState';
import {EvaluationCall} from './ecpTypes';
import {EVALUATION_NAME_DEFAULT} from './ecpUtil';
import {VerticalBox} from './Layout';
import {ComparisonDefinitionSection} from './sections/ComparisonDefinitionSection/ComparisonDefinitionSection';
import {ExampleCompareSectionDetail} from './sections/ExampleCompareSection/ExampleCompareSectionDetail';
import {ExampleCompareSectionTable} from './sections/ExampleCompareSection/ExampleCompareSectionTable';
import {ExampleFilterSection} from './sections/ExampleFilterSection/ExampleFilterSection';
import {ScorecardSection} from './sections/ScorecardSection/ScorecardSection';
import {SummaryPlots} from './sections/SummaryPlotsSection/SummaryPlotsSection';

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
          {({height, width}) => <CompareEvaluationsPageInner height={height} />}
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
  const onClick = useCallback(() => {
    history.push(router.evaluationsUIUrl(entity, project));
  }, [entity, history, project, router]);
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
}> = props => {
  const {state, setSelectedMetrics} = useCompareEvaluationsState();
  const showExampleFilter = false;
  // Keeping this here in case we want to bring it back
  // Object.keys(state.summary.evaluationCalls).length === 2;
  const showExamples =
    Object.keys(state.loadableComparisonResults.result?.resultRows ?? {})
      .length > 0;
  const resultsLoading = state.loadableComparisonResults.loading;
  const [tabValue, setTabValue] = useState('summary');

  return (
    <Box
      sx={{
        height: props.height,
        width: '100%',
        overflow: 'auto',
      }}>
      <SimpleTabView
        headerContent={
          <>
            <InvalidEvaluationBanner
              evaluationCalls={Object.values(state.summary.evaluationCalls)}
            />
            <ComparisonDefinitionSection state={state} />
          </>
        }
        headerContainerSx={{
          // Nice scrolling behavior
          pr: 0,
          pl: 0,
        }}
        tabs={[
          {
            value: 'summary',
            label: 'Summary',
            content: (
              <VerticalBox
                sx={{
                  height: '100%',
                  overflow: 'auto',
                  paddingTop: STANDARD_PADDING / 2,
                  alignItems: 'flex-start',
                  gridGap: STANDARD_PADDING,
                }}>
                <SummaryPlots
                  state={state}
                  setSelectedMetrics={setSelectedMetrics}
                />
                <ScorecardSection state={state} />
              </VerticalBox>
            ),
          },
          {
            value: 'results',
            label: 'Results',
            content: (
              <VerticalBox
                sx={{
                  height: '100%',
                  overflow: 'auto',
                  alignItems: 'flex-start',
                  gridGap: STANDARD_PADDING * 2,
                }}>
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
                    {showExampleFilter && (
                      <ExampleFilterSection state={state} />
                    )}
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
                        fontWeight: 'bold',
                      }}>
                      Examples
                    </Box>
                    <Alert severity="info">
                      The selected evaluations' datasets have 0 rows in common,
                      try comparing evaluations with datasets that have at least
                      one row in common.
                    </Alert>
                  </VerticalBox>
                )}
              </VerticalBox>
            ),
          },
        ]}
        tabValue={tabValue}
        handleTabChange={setTabValue}
      />
    </Box>
  );
};

const ResultExplorer: React.FC<{
  state: EvaluationComparisonState;
  height: number;
}> = ({state, height}) => {
  const [viewMode, setViewMode] = useState<'detail' | 'table' | 'split'>(
    'split'
  );

  return (
    <VerticalBox
      sx={{
        height: '100%',
        width: '100%',
        overflow: 'hidden',
      }}>
      <Box
        style={{
          display: 'flex',
          flexDirection: 'row',
          height: '100%',
          borderTop: '1px solid #e0e0e0',
        }}>
        <Box
          style={{
            flex: 1,
            width: '50%',
            display: viewMode !== 'detail' ? 'block' : 'none',
          }}>
          <ExampleCompareSectionTable
            state={state}
            shouldHighlightSelectedRow={viewMode === 'split'}
            onShowSplitView={() => setViewMode('split')}
          />
        </Box>

        <Box
          style={{
            flex: 1,
            width: '50%',
            borderLeft: '1px solid #e0e0e0',
            display: viewMode !== 'table' ? 'block' : 'none',
          }}>
          <ExampleCompareSectionDetail
            state={state}
            onClose={() => setViewMode('table')}
            onExpandToggle={() =>
              setViewMode(viewMode === 'detail' ? 'split' : 'detail')
            }
            isExpanded={viewMode === 'detail'}
          />
        </Box>
      </Box>
    </VerticalBox>
  );
};

/*
 * Returns true if the evaluation call has summary metrics.
 */
const isValidEval = (evalCall: EvaluationCall) => {
  return Object.keys(evalCall.summaryMetrics).length > 0;
};

const InvalidEvaluationBanner: React.FC<{
  evaluationCalls: EvaluationCall[];
}> = ({evaluationCalls}) => {
  const [dismissed, setDismissed] = useState(false);
  const invalidEvals = useMemo(() => {
    return Object.values(evaluationCalls)
      .filter(call => !isValidEval(call))
      .map(call =>
        call.name !== EVALUATION_NAME_DEFAULT
          ? call.name
          : call.callId.slice(-4)
      );
  }, [evaluationCalls]);
  if (invalidEvals.length === 0 || dismissed) {
    return null;
  }
  return (
    <Box
      sx={{
        width: '100%',
        paddingLeft: STANDARD_PADDING,
        paddingRight: STANDARD_PADDING,
      }}>
      <Tailwind>
        <Alert
          severity="info"
          classes={{
            root: 'bg-teal-300/[0.30] text-teal-600',
            action: 'text-teal-600',
          }}
          action={
            <Button
              // override the default tailwind classes for text and background hover
              className="text-override hover:bg-override"
              variant="ghost"
              onClick={() => setDismissed(true)}>
              Dismiss
            </Button>
          }>
          <span style={{fontWeight: 'bold'}}>
            No summary information found for{' '}
            {maybePluralizeWord(invalidEvals.length, 'evaluation')}:{' '}
            {invalidEvals.join(', ')}.
          </span>
        </Alert>
      </Tailwind>
    </Box>
  );
};
