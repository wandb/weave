import {Box, Button, Grid, Typography} from '@mui/material';
import Paper from '@mui/material/Paper';
import * as globals from '@wandb/weave/common/css/globals.styles';
import * as _ from 'lodash';
import React, {FC} from 'react';

import {StatusChip} from '../Browse3/pages/common/StatusChip';
import {Call} from './callTree';
import {DisplayControlChars} from './CommonLib';
import {
  isOpenAIChatInput,
  isOpenAIChatOutput,
  OpenAIChatInputView,
  OpenAIChatOutputView,
} from './openai';
import {parseRefMaybe, SmallRef} from './SmallRef';

const ObjectView: FC<{obj: any}> = ({obj}) => {
  if (_.isPlainObject(obj)) {
    return (
      <Grid container spacing={1}>
        {Object.entries(obj).flatMap(([key, value]) => {
          const singleRow = !_.isPlainObject(value);
          return [
            <Grid
              item
              key={key + '-key'}
              xs={singleRow ? 2 : 12}
              sx={{
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}>
              <Typography>{key}</Typography>
            </Grid>,
            <Grid item key={key + '-value'} xs={singleRow ? 10 : 12}>
              <Box ml={singleRow ? 0 : 2}>
                <ObjectView obj={value} />
              </Box>
            </Grid>,
          ];
        })}
      </Grid>
    );
  }
  if (typeof obj === 'string') {
    const ref = parseRefMaybe(obj);
    if (ref != null) {
      return <SmallRef objRef={ref} />;
    }
    return <DisplayControlChars text={obj} />;
  }
  if (_.isArray(obj)) {
    return (
      <Grid container spacing={1}>
        {obj.map((value, i) => (
          <Grid item key={i} xs={12}>
            <Paper style={{margin: 10, wordWrap: 'break-word', padding: 10}}>
              <ObjectView obj={value} />
            </Paper>
          </Grid>
        ))}
      </Grid>
    );
  }
  return <Typography>{JSON.stringify(obj)}</Typography>;
};

export const SpanDetails: FC<{
  call: Call;
  hackyInjectionBelowFunction?: React.ReactNode;
}> = ({call, hackyInjectionBelowFunction}) => {
  const inputKeys =
    call.inputs._keys ??
    Object.entries(call.inputs)
      .filter(([k, c]) => c != null && !k.startsWith('_'))
      .map(([k, c]) => k);
  const inputs = _.fromPairs(inputKeys.map(k => [k, call.inputs[k]]));

  const callOutput = call.output ?? {};
  const outputKeys =
    callOutput._keys ??
    Object.entries(call.inputs)
      .filter(([k, c]) => c != null && (k === '_result' || !k.startsWith('_')))
      .map(([k, c]) => k);
  const output = _.fromPairs(outputKeys.map(k => [k, callOutput[k]]));

  const attributes = _.fromPairs(
    Object.entries(call.attributes ?? {}).filter(([k, a]) => !k.startsWith('_'))
  );

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
          {parseRefMaybe(call.name) != null ? (
            <SmallRef objRef={parseRefMaybe(call.name)!} wfTable="OpVersion" />
          ) : (
            call.name
          )}
        </Box>
        <Box display="flex" alignItems="center" gap={1}>
          <Typography variant="body2">Status:</Typography>
          <StatusChip value={call.status_code} />
        </Box>
        {hackyInjectionBelowFunction}
        {call.exception != null && (
          <Typography variant="body2" gutterBottom>
            {call.exception}
          </Typography>
        )}
      </div>
      {Object.keys(attributes).length > 0 && (
        <div style={{marginBottom: 12}}>
          <Typography variant="h6" gutterBottom>
            Attributes
          </Typography>
          <Box pl={2} pr={2}>
            <ObjectView
              obj={_.fromPairs(
                Object.entries(attributes).filter(([k, v]) => v != null)
              )}
            />
          </Box>
        </div>
      )}
      <div style={{marginBottom: 12}}>
        <Typography variant="h6" gutterBottom>
          Summary
        </Typography>
        <Box pl={2} pr={2}>
          <ObjectView
            obj={_.fromPairs(
              Object.entries(call.summary).filter(([k, v]) => v != null)
            )}
          />
        </Box>
      </div>
      <div style={{marginBottom: 24}}>
        <Typography variant="h5" gutterBottom>
          Inputs
        </Typography>
        <Box pl={2} pr={2}>
          {isOpenAIChatInput(inputs) ? (
            <OpenAIChatInputView chatInput={inputs} />
          ) : (
            <ObjectView obj={inputs} />
          )}
        </Box>
      </div>
      <div style={{marginBottom: 24}}>
        <Typography variant="h6" gutterBottom>
          Output
        </Typography>
        <Box pl={2} pr={2}>
          {output == null ? (
            <div>null</div>
          ) : isOpenAIChatOutput(call.output) ? (
            <OpenAIChatOutputView chatOutput={call.output} />
          ) : (
            <ObjectView
              obj={_.fromPairs(
                Object.entries(output).filter(
                  ([k, v]) =>
                    (k === '_result' || !k.startsWith('_')) && v != null
                )
              )}
            />
          )}
        </Box>
      </div>
    </div>
  );
};
