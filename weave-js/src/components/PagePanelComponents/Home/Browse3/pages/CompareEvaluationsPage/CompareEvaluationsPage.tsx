/**
 * This is the entrypoint for the Evaluation Comparison Page.
 *
 * TODO:
 * - [ ] Reflect local state in URL (dimension, range, & selection)
 * - [ ] Code Cleanup: There is a lot of dead / messy code
 * - [ ] Refs in Model Property table should be expanded. Example:  https://app.wandb.test/wandb-designers/signal-maven/weave/compare-evaluations?evaluationCallIds=%5B%22bf5188ba-48cd-4c6d-91ea-e25464570c13%22%2C%222f4544f3-9649-487e-b083-df6985e21b12%22%2C%228cbeccd6-6ff7-4eac-a305-6fb6450530f1%22%5D
 * - [ ] Refs in Call Table should be links
 * - [ ] Arrays are not supported well in the model property table or the call table. Example: https://app.wandb.test/wandb-smle/weave-rag-lc-demo/weave/compare-evaluations?evaluationCallIds=%5B%2221e8ea02-3109-434c-95d0-cb2c7c542f74%22%5D&peekPath=%2Fwandb-smle%2Fweave-rag-lc-demo%2Fcalls%2F21e8ea02-3109-434c-95d0-cb2c7c542f74
 * - [ ] "Comparison Table" should use Baseline model input for input fields, NOT the dataset input
 * - [ ] Comparison table needs more vertical space allocated to focus on text (look at langsmith)
 * Bugs:
 * - [ ] Empty selection filter causes crash
 * - [ ] Selection Filter seems to reset periodically? on data refresh
 * - [ ] Plots do not respect the evaluation ordering
 * - [ ] `isProbablyXCall` is incorrect - at least the predict one (eg. for infer_method_names in ("predict", "infer", "forward"):)
 * Performance:
 * - [ ] Audit the queries to determine areas of improvement and parallelization
 * Data Model:
 * - [ ] Audit the data model to correctly reflect ScoreDimensions (this is too loose right now)
 * - [ ] find all cases of the `_raw*` cases and remove them, this is an example of insufficient data model
 * - [ ] Latency, Tokens, and Cost are should "feel" like first class ScoringDimensions
 * - [ ] Verify that nested scorers are supported
 * - [ ] Change "Target Metric" to an ordered list of metrics. Default to first metric + latency
 * Styling / UX:
 * - [ ] Add a better loading state
 * - [ ] Header controls don't scale well to smaller sized
 * - [ ] Use Shawn's color Pallet
 * - [ ] Should pull in EvaluationCall display name if it exists
 * - [ ] Hover tooltip on charts to show values
 * - Scatterplot Filter UX
 *    - [ ] Move the dimension selector closer to the plot of interest
 *    - [ ] Scatterplot filter should have 1-1 aspect ratio
 *    - [ ] Scatterplot Filter dimensions are not quite obvious
 *    - [ ] Scatterplot filter would benefit from a title / help text
 *    - [ ] Scatterplot Filter should not zoom, just show selection range
 */

import {Box} from '@material-ui/core';
import React, {FC, useCallback, useContext, useMemo} from 'react';
import {useHistory} from 'react-router-dom';

import {Button} from '../../../../../Button';
import {
  useWeaveflowCurrentRouteContext,
  WeaveflowPeekContext,
} from '../../context';
import {useEvaluationsFilter} from '../CallsPage/CallsPage';
import {CallsTable} from '../CallsPage/CallsTable';
import {SimplePageLayout} from '../common/SimplePageLayout';
import {
  CompareEvaluationsProvider,
  EvaluationComparisonState,
  useCompareEvaluationsState,
} from './compareEvaluationsContext';
import {ComparisonDefinition} from './ComparisonDefinitionHeader';
import {STANDARD_PADDING} from './constants';
import {ScoreDimension} from './evaluations';
import {CompareEvaluationsCallsTable} from './ExampleComparisonTable';
import {RangeSelection} from './initialize';
import {VerticalBox} from './Layout';
import {ScatterFilter} from './ScatterFilter';
import {ScoreCard} from './Scorecard';
import {SummaryPlots} from './SummaryPlots';

type CompareEvaluationsPageProps = {
  entity: string;
  project: string;
  evaluationCallIds: string[];
};

export const CompareEvaluationsPage: React.FC<
  CompareEvaluationsPageProps
> = props => {
  const [baselineEvaluationCallId, setBaselineEvaluationCallId] =
    React.useState(
      props.evaluationCallIds.length > 0 ? props.evaluationCallIds[0] : null
    );
  // console.log(baselineEvaluationCallId);
  const [comparisonDimension, setComparisonDimension] =
    React.useState<ScoreDimension | null>(null);

  const [selectedInputDigest, setSelectedInputDigest] = React.useState<
    string | null
  >(null);

  const [rangeSelection, setRangeSelection] = React.useState<RangeSelection>(
    {}
  );

  // Wow this cascading state is getting out of hand

  const setRangeSelectionAndClearSelectedInputDigest = useCallback(
    (
      newRangeSelection:
        | RangeSelection
        | ((prev: RangeSelection) => RangeSelection)
    ) => {
      if (typeof newRangeSelection === 'function') {
        newRangeSelection = newRangeSelection(rangeSelection);
      }
      setRangeSelection(newRangeSelection);
      setSelectedInputDigest(null);
    },
    [rangeSelection]
  );

  const setComparisonDimensionAndClearRange = useCallback(
    (
      dim:
        | ScoreDimension
        | null
        | ((prev: ScoreDimension | null) => ScoreDimension | null)
    ) => {
      if (typeof dim === 'function') {
        dim = dim(comparisonDimension);
      }
      setComparisonDimension(dim);
      setRangeSelectionAndClearSelectedInputDigest({});
    },
    [comparisonDimension, setRangeSelectionAndClearSelectedInputDigest]
  );

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
              baselineEvaluationCallId={baselineEvaluationCallId ?? undefined}
              comparisonDimension={comparisonDimension ?? undefined}
              rangeSelection={rangeSelection}
              setBaselineEvaluationCallId={setBaselineEvaluationCallId}
              setComparisonDimension={setComparisonDimensionAndClearRange}
              setRangeSelection={setRangeSelectionAndClearSelectedInputDigest}
              selectedInputDigest={selectedInputDigest ?? undefined}
              setSelectedInputDigest={setSelectedInputDigest}>
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
  const {state} = useCompareEvaluationsState();

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
        <RowComparison state={state} />
      </VerticalBox>
    </Box>
  );
};

const RowComparison: React.FC<{state: EvaluationComparisonState}> = props => {
  const selectedCallIds = useMemo(() => {
    if (props.state.selectedInputDigest == null) {
      return [];
    }
    const selectedRow =
      props.state.data.resultRows[props.state.selectedInputDigest];
    if (selectedRow == null) {
      return [];
    }
    return Object.values(selectedRow.evaluations)
      .map(evaluation => Object.keys(evaluation.predictAndScores))
      .flat();
  }, [props.state.data.resultRows, props.state.selectedInputDigest]);

  if (props.state.selectedInputDigest == null) {
    return null;
  }

  return (
    <CallsTable
      entity={props.state.data.entity}
      project={props.state.data.project}
      frozenFilter={{
        callIds: selectedCallIds,
      }}
      hideControls
    />
  );
};
