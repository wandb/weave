/**
 * This is the entrypoint for the Evaluation Comparison Page.
 */

import {Box} from '@material-ui/core';
import {Alert} from '@mui/material';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {maybePluralizeWord} from '@wandb/weave/core/util/string';
import React, {FC, useCallback, useContext, useMemo, useState} from 'react';
import {useHistory} from 'react-router-dom';

import {Button} from '../../../../../Button';
import {
  useWeaveflowCurrentRouteContext,
  WeaveflowPeekContext,
} from '../../context';
import {useEvaluationsFilter} from '../CallsPage/evaluationsFilter';
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
      title="Compare Evaluations"
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
  const showExampleFilter =
    Object.keys(state.data.evaluationCalls).length === 2;
  const showExamples = Object.keys(state.data.resultRows).length > 0;
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
        <InvalidEvaluationBanner
          evaluationCalls={Object.values(state.data.evaluationCalls)}
        />
        <ComparisonDefinitionSection state={state} />
        <SummaryPlots state={state} />
        <ScorecardSection state={state} />
        {showExamples ? (
          <>
            {showExampleFilter && <ExampleFilterSection state={state} />}
            <ResultExplorer state={state} />
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
          height: 'calc(100vh - 114px)',
          overflow: 'auto',
        }}>
        <ExampleCompareSection state={state} />
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
