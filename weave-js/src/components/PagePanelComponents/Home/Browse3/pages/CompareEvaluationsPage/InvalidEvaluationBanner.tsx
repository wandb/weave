import {Box} from '@material-ui/core';
import {Alert} from '@mui/material';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {maybePluralizeWord} from '@wandb/weave/core/util/string';
import React, {useMemo, useState} from 'react';

import {Button} from '../../../../../Button';
import {STANDARD_PADDING} from './ecpConstants';
import {EvaluationCall} from './ecpTypes';
import {EVALUATION_NAME_DEFAULT} from './ecpUtil';

/*
 * Returns true if the evaluation call has summary metrics.
 */
const isValidEval = (evalCall: EvaluationCall) => {
  return Object.keys(evalCall.summaryMetrics).length > 0;
};

export const InvalidEvaluationBanner: React.FC<{
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
