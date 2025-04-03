import {Box} from '@material-ui/core';
import {Alert} from '@mui/material';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {maybePluralizeWord} from '@wandb/weave/core/util/string';
import React, {useMemo, useState} from 'react';

import {Button} from '../../../../../Button';
import {CustomWeaveTypeProjectContext} from '../../typeViews/CustomWeaveTypeDispatcher';
import {STANDARD_PADDING} from './ecpConstants';
import {EvaluationComparisonState} from './ecpState';
import {EvaluationCall} from './ecpTypes';
import {EVALUATION_NAME_DEFAULT} from './ecpUtil';
import {HorizontalBox, VerticalBox} from './Layout';
import {TraceCallsSection} from './TraceCallsSection';

// Inlined from InvalidEvaluationBanner.tsx to avoid import issues
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

interface TraceCallsCompareEvaluationsPageProps {
  height: number;
  traceCalls: Array<{callId: string; traceCall: any}>;
  state: EvaluationComparisonState;
}

export const TraceCallsCompareEvaluationsPage: React.FC<
  TraceCallsCompareEvaluationsPageProps
> = ({height, traceCalls, state}) => {
  const projectContext = React.useContext(CustomWeaveTypeProjectContext);

  return (
    <Box
      sx={{
        height,
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
              Trace Call Outputs
            </Box>
          </HorizontalBox>
          <Box
            sx={{
              height,
              overflow: 'auto',
            }}>
            <TraceCallsSection
              traceCalls={traceCalls}
              entity={projectContext?.entity}
              project={projectContext?.project}
              state={state}
            />
          </Box>
        </VerticalBox>
      </VerticalBox>
    </Box>
  );
};
