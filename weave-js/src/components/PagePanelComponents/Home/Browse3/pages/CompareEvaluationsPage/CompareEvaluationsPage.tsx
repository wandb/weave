/**
 * This is the entrypoint for the Evaluation Comparison Page.
 */

import {Box} from '@material-ui/core';
import {Alert} from '@mui/material';
import {Icon} from '@wandb/weave/components/Icon';
import {WaveLoader} from '@wandb/weave/components/Loaders/WaveLoader';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {maybePluralizeWord} from '@wandb/weave/core/util/string';
import React, {
  FC,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {useHistory} from 'react-router-dom';
import {AutoSizer} from 'react-virtualized';

import {Button} from '../../../../../Button';
import {
  usePeekLocation,
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
        <CompareEvaluationsPageInner />
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

const CompareEvaluationsPageInner: React.FC<{}> = props => {
  const {state, setSelectedMetrics} = useCompareEvaluationsState();
  const showExamples =
    Object.keys(state.loadableComparisonResults.result?.resultRows ?? {})
      .length > 0;
  const resultsLoading = state.loadableComparisonResults.loading;
  const [tabValue, setTabValue] = useState('summary');

  return (
    <Box
      sx={{
        height: '100%',
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
                <Tailwind style={{width: '100%'}}>
                  <div className="px-16">
                    <div className="flex w-full flex-col items-center gap-3 rounded-lg border border-dashed border-moon-300 bg-moon-50 p-16">
                      <Icon name="table" size="large" color="moon-500 mb-4" />
                      <div className="mb-4 flex flex-col items-center">
                        <p className="text-center font-semibold">
                          Looking for your evaluation results?
                        </p>
                        <p className="text-center text-moon-500">
                          You can find it in our new results tab.
                        </p>
                      </div>
                      <Button
                        variant="secondary"
                        onClick={() => setTabValue('results')}>
                        Review evaluation results
                      </Button>
                    </div>
                    <div className="h-16"></div>
                  </div>
                </Tailwind>
              </VerticalBox>
            ),
          },
          {
            value: 'results',
            label: 'Results',
            loading: resultsLoading,
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
                  <AutoSizer style={{height: '100%', width: '100%'}}>
                    {({height, width}) => {
                      return <ResultExplorer state={state} height={height} />;
                    }}
                  </AutoSizer>
                ) : (
                  <VerticalBox
                    sx={{
                      paddingLeft: STANDARD_PADDING,
                      paddingRight: STANDARD_PADDING,
                      paddingTop: STANDARD_PADDING,
                      width: '100%',
                      overflow: 'auto',
                    }}>
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
  const {hiddenEvaluationIds} = useCompareEvaluationsState();
  const peekLocation = usePeekLocation();
  const isPeekDrawerOpen = peekLocation != null;

  const [viewMode, setViewMode] = useState<'detail' | 'table' | 'split'>(
    'table'
  );
  const [sidebarWidth, setSidebarWidth] = useState<number | null>(null); // null means use default calc(100% - 160px)
  const [previousSidebarWidth, setPreviousSidebarWidth] = useState<
    number | null
  >(null); // Store width before expanding
  const [isResizing, setIsResizing] = useState(false);
  const [wasAutoExpanded, setWasAutoExpanded] = useState(false); // Track if expansion was automatic
  const containerRef = useRef<HTMLDivElement>(null);

  // Only enable regression finder if exactly 2 evaluations are visible
  const visibleEvaluationCount = state.evaluationCallIdsOrdered.filter(
    id => !hiddenEvaluationIds.has(id)
  ).length;
  const regressionFinderEnabled = visibleEvaluationCount === 2;

  // When peek drawer opens and we're in split view, automatically expand to detail view
  // When peek drawer closes and we're in detail view, automatically collapse back to split view
  useEffect(() => {
    if (isPeekDrawerOpen && viewMode === 'split') {
      setPreviousSidebarWidth(sidebarWidth);
      setViewMode('detail');
      setWasAutoExpanded(true);
    } else if (!isPeekDrawerOpen && viewMode === 'detail' && wasAutoExpanded) {
      // Only collapse back if we auto-expanded
      setViewMode('split');
      setSidebarWidth(previousSidebarWidth);
      setWasAutoExpanded(false);
    }
  }, [
    isPeekDrawerOpen,
    viewMode,
    sidebarWidth,
    previousSidebarWidth,
    wasAutoExpanded,
  ]);

  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (isResizing && containerRef.current) {
        e.preventDefault();
        const containerRect = containerRef.current.getBoundingClientRect();
        const newWidthPx = containerRect.right - e.clientX;
        setSidebarWidth(
          Math.min(Math.max(newWidthPx, 200), containerRect.width - 160)
        ); // Constrain between 200px and container width - 2
      }
    },
    [isResizing]
  );

  const handleMouseUp = useCallback(() => {
    setIsResizing(false);
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
  }, []);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, []);

  useEffect(() => {
    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      return () => {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
      };
    }
    return undefined;
  }, [isResizing, handleMouseMove, handleMouseUp]);

  return (
    <div
      ref={containerRef}
      style={{
        height: '100%',
        width: '100%',
        overflow: 'auto',
        position: 'relative',
      }}>
      {regressionFinderEnabled && <ExampleFilterSection state={state} />}
      <Box
        style={{
          display: 'flex',
          flexDirection: 'row',
          height: height,
          borderTop: '1px solid #e0e0e0',
          position: 'relative',
        }}>
        <Box
          style={{
            flex: 1,
            width: '100%',
          }}>
          <ExampleCompareSectionTable
            state={state}
            shouldHighlightSelectedRow={
              viewMode === 'split' || viewMode === 'detail'
            }
            onShowSplitView={() => setViewMode('split')}
          />
        </Box>

        {viewMode !== 'table' && (
          <Box
            style={{
              position: 'absolute',
              top: 0,
              right: 0,
              width:
                viewMode === 'detail'
                  ? '100%'
                  : sidebarWidth !== null
                  ? `${sidebarWidth}px`
                  : 'calc(100% - 160px)',
              height: '100%',
              backgroundColor: 'white',
              boxShadow:
                '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
              display: 'flex',
              flexDirection: 'row',
              zIndex: 1000,
            }}>
            {viewMode !== 'detail' && (
              <div
                style={{
                  position: 'absolute',
                  left: -3,
                  top: 0,
                  bottom: 0,
                  width: 5,
                  cursor: 'col-resize',
                  backgroundColor: isResizing ? '#13A9BA' : 'transparent',
                  transition: isResizing ? 'none' : 'background-color 0.2s',
                  zIndex: 1001,
                }}
                onMouseDown={handleMouseDown}
                onMouseEnter={e => {
                  if (!isResizing) {
                    e.currentTarget.style.backgroundColor =
                      'rgba(169, 237, 242, 0.5)';
                  }
                }}
                onMouseLeave={e => {
                  if (!isResizing) {
                    e.currentTarget.style.backgroundColor = 'transparent';
                  }
                }}
              />
            )}
            <Box style={{flex: 1, overflow: 'hidden'}}>
              <ExampleCompareSectionDetail
                state={state}
                onClose={() => setViewMode('table')}
                onExpandToggle={() => {
                  if (viewMode === 'detail') {
                    // Collapsing from detail mode back to split mode
                    setViewMode('split');
                    // Restore the previous width
                    setSidebarWidth(previousSidebarWidth);
                    setWasAutoExpanded(false); // Clear auto-expanded flag
                  } else {
                    // Expanding to detail mode
                    setPreviousSidebarWidth(sidebarWidth);
                    setViewMode('detail');
                    setWasAutoExpanded(false); // This was manual expansion
                  }
                }}
                isExpanded={viewMode === 'detail'}
                isPeekDrawerOpen={isPeekDrawerOpen}
              />
            </Box>
          </Box>
        )}
      </Box>
    </div>
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
