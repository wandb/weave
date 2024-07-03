/**
 * This is the entrypoint for the Evaluation Comparison Page.
 *
 * TODO:
 * Data Model:
 * - [ ] (MUST) Audit the data model to correctly reflect ScoreDimensions (this is too loose right now)
 * - [ ] (MUST) Latency, Tokens, and Cost are should "feel" like first class ScoringDimensions
 * - [ ] (probably) find all cases of the `_raw*` cases and remove them, this is an example of insufficient data model
 * - [ ] (probably) find all cases of the `_legacy_*` cases and remove them, this is an example of insufficient data model
 * - [ ] (probably) Change "Target Metric" to an ordered list of metrics. Default to first metric + latency
 * - [ ] (maybe) Verify that nested scorers are supported
 * - [ ] (maybe) "Comparison Table" should use Baseline model input for input fields, NOT the dataset input
 * Bugs:
 * - [ ] (MUST) Lots of Warning: Each child in a list should have a unique "key" prop.
 * - [ ] (MUST) Total Tokens is empty
 * - [ ] (MUST) Bug: https://app.wandb.test/shawn/weave-hooman1/weave/compare-evaluations?evaluationCallIds=%5B%228e207ad2-272c-4a6b-851a-fecb0049eec2%22%2C%228dd66257-df66-471f-92ab-bf97ce9662e5%22%5D
 * - [ ] (MUST) Empty selection filter causes crash
 * - [ ] (MUST)`isProbablyXCall` is incorrect - at least the predict one (eg. for infer_method_names in ("predict", "infer", "forward"):)
 * - [ ] (Probably) Selection Filter seems to reset periodically? on data refresh - also on page resize?
 * Bigger Features:
 * Comparison Table:
 * - [ ] (MUST) Need to finalize how to handle the comparison table - I have a few options, settle on one
 * - [ ] (MUST) Add a trace link
 * - [ ] (MUST) Add link to scorer in the compare table
 * - [ ] (MUST) Evaluation pinning pushes summary off screen
 * Smaller Features:
 * - [ ] (MUST) Move toggle to the properties section similar to run comparer
 * - [ ] (MUST) Reflect local state in URL (dimension, range, & selection)
 * - [ ] (MUST) Sort example results to be absolute value of difference of primary metric
 * - [ ] (maybe) Refs in Model Property table should be expanded. Example:  https://app.wandb.test/wandb-designers/signal-maven/weave/compare-evaluations?evaluationCallIds=%5B%22bf5188ba-48cd-4c6d-91ea-e25464570c13%22%2C%222f4544f3-9649-487e-b083-df6985e21b12%22%2C%228cbeccd6-6ff7-4eac-a305-6fb6450530f1%22%5D
 * - [ ] (maybe) Arrays are not supported well in the model property table or the call table. Example: https://app.wandb.test/wandb-smle/weave-rag-lc-demo/weave/compare-evaluations?evaluationCallIds=%5B%2221e8ea02-3109-434c-95d0-cb2c7c542f74%22%5D&peekPath=%2Fwandb-smle%2Fweave-rag-lc-demo%2Fcalls%2F21e8ea02-3109-434c-95d0-cb2c7c542f74
 * Performance:
 * - [ ] (probably) Audit the queries to determine areas of improvement and parallelization
 * Styling / UX:
 * - [ ] (probably) Hover tooltip on charts to show values
 * - [ ] (maybe) Should pull in EvaluationCall display name if it exists
 * - Scatterplot Filter UX
 *    - [ ] (MUST) Scatterplot Scale dot to number of points
 *    - [ ] (MUST) Axis dimension needs unit
 *    - [ ] (MUST) Axis Labels
 *    - [ ] (MUST) Half Width (and add latency as a second)
 *    - [ ] (probably) Scatterplot Filter dimensions are not quite obvious
 *    - [ ] (probably) Scatterplot filter would benefit from a title / help text
 *    - [ ] (maybe) Scatterplot filter should have 1-1 aspect ratio
 *    - [ ] Double click does not clear the box boudnary
 * Implementation Tasks:
 * - [ ] (MUST) Code Cleanup: There is a lot of dead / messy code
 * - [ ] (MUST) Code Cleanup: Pill logic should be shared now
 */

import {Box} from '@material-ui/core';
import React, {FC, useCallback, useContext} from 'react';
import {useHistory} from 'react-router-dom';

import {Button} from '../../../../../Button';
import {
  useWeaveflowCurrentRouteContext,
  WeaveflowPeekContext,
} from '../../context';
import {useEvaluationsFilter} from '../CallsPage/CallsPage';
import {SimplePageLayout} from '../common/SimplePageLayout';
import {
  CompareEvaluationsProvider,
  useCompareEvaluationsState,
} from './compareEvaluationsContext';
import {STANDARD_PADDING} from './ecpConstants';
import {RangeSelection} from './ecpTypes';
import {EvaluationMetricDimension} from './ecpTypes';
import {EvaluationComparisonState} from './ecpTypes';
import {HorizontalBox, VerticalBox} from './Layout';
import {ComparisonDefinitionSection} from './sections/ComparisonDefinitionSection/ComparisonDefinitionSection';
import {ExampleCompareSection} from './sections/ExampleCompareSection/ExampleCompareSection';
import {ExampleFilterSection} from './sections/ExampleFilterSection/ExampleFilterSection';
import {ScorecardSection} from './sections/ScorecardSection/ScorecardSection';
import {SummaryPlots} from './sections/SummaryPlotsSection/SummaryPlotsSection';

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

  const [comparisonDimension, setComparisonDimension] =
    React.useState<EvaluationMetricDimension | null>(null);

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
        | EvaluationMetricDimension
        | null
        | ((
            prev: EvaluationMetricDimension | null
          ) => EvaluationMetricDimension | null)
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
          gridGap: STANDARD_PADDING * 2,
        }}>
        <ComparisonDefinitionSection state={state} />
        <SummaryPlots state={state} />
        <ScorecardSection state={state} />
        {Object.keys(state.data.models).length === 2 && (
          <ExampleFilterSection state={state} />
        )}
        {/* <ResultsSection state={state} /> */}
        <ResultExplorer state={state} />
      </VerticalBox>
    </Box>
  );
};

const ResultExplorer: React.FC<{state: EvaluationComparisonState}> = ({
  state,
}) => {
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
          // marginBottom: '8px',
        }}>
        <Box
          sx={{
            fontSize: '1.5em',
            fontWeight: 'bold',
          }}>
          Browse Model Outputs on Examples
        </Box>
      </HorizontalBox>
      <Box
        sx={{
          height: 'calc(100vh - 114px)',
          overflow: 'auto',
        }}>
        <ExampleCompareSection state={state} />
      </Box>
    </VerticalBox>
  );
};
