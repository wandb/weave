import * as _ from 'lodash';
import React, {FC} from 'react';
import * as globals from '@wandb/weave/common/css/globals.styles';
import {Call} from './callTree';
import {
  OpenAIChatInputView,
  OpenAIChatOutputView,
  isOpenAIChatInput,
  isOpenAIChatOutput,
} from './openai';
import {Button, Typography, Box, Chip} from '@mui/material';

export const SpanDetails: FC<{call: Call}> = ({call}) => {
  const actualInputs = Object.entries(call.inputs).filter(
    ([k, c]) => c != null && !k.startsWith('_')
  );
  const inputs = _.fromPairs(actualInputs);
  return (
    <div style={{width: '100%'}}>
      <div style={{marginBottom: 24}}>
        <Box mb={2}>
          <Box display="flex" justifyContent="space-between">
            <Typography variant="h5" gutterBottom>
              Function
            </Typography>
            {isOpenAIChatInput(inputs) && (
              <Button
                variant="outlined"
                sx={{backgroundColor: globals.lightYellow}}>
                Open in LLM Playground
              </Button>
            )}
          </Box>
          <Chip label={call.name} />
        </Box>
        <Typography variant="body2" gutterBottom>
          Status: {call.status_code}
        </Typography>
        {call.exception != null && (
          <Typography variant="body2" gutterBottom>
            {call.exception}
          </Typography>
        )}
      </div>
      <div style={{marginBottom: 24}}>
        <Typography variant="h5" gutterBottom>
          Inputs
        </Typography>
        {isOpenAIChatInput(inputs) ? (
          <OpenAIChatInputView chatInput={inputs} />
        ) : (
          <pre style={{fontSize: 12}}>
            {JSON.stringify(inputs, undefined, 2)}
          </pre>
        )}
      </div>
      <div style={{marginBottom: 24}}>
        <Typography variant="h6" gutterBottom>
          Output
        </Typography>
        {isOpenAIChatOutput(call.output) ? (
          <OpenAIChatOutputView chatOutput={call.output} />
        ) : (
          <pre style={{fontSize: 12}}>
            {JSON.stringify(call.output, undefined, 2)}
          </pre>
        )}
      </div>
      {call.attributes != null && (
        <div style={{marginBottom: 12}}>
          <div>
            <b>Attributes</b>
          </div>
          <pre style={{fontSize: 12}}>
            {JSON.stringify(call.attributes, undefined, 2)}
          </pre>
        </div>
      )}
      <div style={{marginBottom: 12}}>
        <Typography variant="h6" gutterBottom>
          Summary
        </Typography>
        <pre style={{fontSize: 12}}>
          {JSON.stringify(call.summary, undefined, 2)}
        </pre>
      </div>
    </div>
  );
};
