/**
 * This is the entrypoint for the Evaluation Comparison Page.
 */

import {Box} from '@material-ui/core';
import {Alert} from '@mui/material';
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
  useWeaveflowCurrentRouteContext,
  WeaveflowPeekContext,
} from '../../context';
import {CustomWeaveTypeProjectContext} from '../../typeViews/CustomWeaveTypeDispatcher';
import {SimplePageLayout} from '../common/SimplePageLayout';
import {
  CompareEvaluationsProvider,
  useCompareEvaluationsState,
} from './compareEvaluationsContext';
import {STANDARD_PADDING} from './ecpConstants';
import {EvaluationComparisonState} from './ecpState';
import {ComparisonDimensionsType} from './ecpState';
import {EvaluationCall} from './ecpTypes';
import {EVALUATION_NAME_DEFAULT} from './ecpUtil';
import {HorizontalBox, VerticalBox} from './Layout';
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
  const showExampleFilter =
    Object.keys(state.summary.evaluationCalls).length === 2;
  const showExamples =
    Object.keys(state.loadableComparisonResults.result?.resultRows ?? {})
      .length > 0;
  const resultsLoading = state.loadableComparisonResults.loading;
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
              // alignItems: '',
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
  const [viewMode, setViewMode] = useState<'detail' | 'table' | 'split'>(
    'detail'
  );

  return (
    <VerticalBox
      sx={{
        height: '100%',
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
          paddingTop: 15,
        }}>
        <Box
          sx={{
            fontSize: '16px',
            fontWeight: 'bold',
          }}>
          Output Comparison
        </Box>
      </HorizontalBox>
      <AdaptiveHeightParent maxHeight={height}>
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
      </AdaptiveHeightParent>
    </VerticalBox>
  );
};

/**
 * This component should behave as follows:
 * 1. It accepts a maxHeight prop which is the maximum height of the component.
 * 2. It accepts children to display inside the component.
 * 3. The children component's parent element should be no taller than the maxHeight, BUT
 *    IMPORTANTLY: should be contrainted to the visible bounding region.
 *
 * In other words: the parent's height is:
 *    * > 0
 *    * <= maxHeight
 *    * <= the visible height of the parent's parent element (bounded by the window or the next visible parent with a height constraint and overflow: hidden)
 */
const AdaptiveHeightParent: React.FC<{
  maxHeight: number;
  children: React.ReactNode;
  style?: React.CSSProperties;
  className?: string;
}> = ({maxHeight, children, style, className}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [height, setHeight] = useState(maxHeight);

  useEffect(() => {
    const updateHeight = () => {
      if (!containerRef.current) return;

      // Get the container's bounding rect
      const containerRect = containerRef.current.getBoundingClientRect();

      // Find the visible height (distance from top of element to bottom of viewport)
      const visibleHeight = Math.min(
        window.innerHeight - containerRect.top,
        containerRef.current.parentElement?.getBoundingClientRect().height ||
          Infinity
      );

      // Set the height to the minimum of maxHeight and visibleHeight
      const newHeight = Math.max(0, Math.min(maxHeight, visibleHeight));
      setHeight(newHeight);
    };

    const interval = setInterval(updateHeight, 100);

    return () => clearInterval(interval);
  }, [maxHeight]);

  return (
    <div
      ref={containerRef}
      style={{
        height: maxHeight,
        overflow: 'hidden',
      }}
      className={className}>
      <div style={{height, ...style}}>{children}</div>
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
