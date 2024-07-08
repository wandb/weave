/**
 * This is the entrypoint for the Evaluation Comparison Page.
 *
 * Remaining TODO:
 * - [ ] (probably) find all cases of the `_raw*` cases and remove them, this is an example of insufficient data model
 * - [ ] (probably) find all cases of the `_legacy_*` cases and remove them, this is an example of insufficient data model
 * - [ ] Code Cleanup: There is a lot of dead / messy code (commnts, knip, etc...)
 * - [ ] Code Cleanup: Pill logic should be shared now between scorecard and viewer
 *
 * Quick Followups:
 * - [ ] Shareability: Retain filter / row selection in URL. Probably want to let the feature bake a bit before committing to a data model in the URL.
 * - [ ] Performance Audit: Audit the queries to determine areas of improvement and parallelization
 * - [ ] UX: Hover tooltips on all plots
 * - [ ] UX: Use user-defined call names for evaluation calls
 * - [ ] UX: Binary scores should be "confusion matrix" style
 * - [ ] UX: Consider making all filter plots 1-1 aspect ratio
 * - [ ] UX: Scatter plots should have dimension units
 * - [ ] UX: Expand top-level refs (e.g. when a model prompt is a ref, see /wandb-designers/signal-maven)
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
import {ComparisonDimensionsType} from './ecpTypes';
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

  const [comparisonDimensions, setComparisonDimensions] =
    React.useState<ComparisonDimensionsType | null>(null);

  const [selectedInputDigest, setSelectedInputDigest] = React.useState<
    string | null
  >(null);

  // Wow this cascading state is getting out of hand

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
              comparisonDimensions={comparisonDimensions ?? undefined}
              setBaselineEvaluationCallId={setBaselineEvaluationCallId}
              setComparisonDimensions={
                setComparisonDimensionsAndClearInputDigest
              }
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
